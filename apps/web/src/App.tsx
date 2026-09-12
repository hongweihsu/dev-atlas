import { DragEvent, FormEvent, useEffect, useState } from 'react'

import {
  AnswerResponse,
  ApiRequestError,
  DocumentSummary,
  DocumentVersionSummary,
  IngestDocumentResponse,
  activateDocumentVersion,
  answerQuestion,
  archiveDocument,
  checkHealth,
  listDocuments,
  listDocumentVersions,
  restoreDocument,
  uploadDocument,
  uploadDocumentVersion,
} from './api'

type ApiState = 'checking' | 'healthy' | 'unavailable'
type RequestState = 'idle' | 'submitting' | 'success' | 'error'
type DocumentSort = 'updated' | 'name'
type DocumentView = 'active' | 'archived'
type UploadTab = 'add' | 'update'

export default function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [fileInputKey, setFileInputKey] = useState(0)
  const [uploadState, setUploadState] = useState<RequestState>('idle')
  const [uploadResult, setUploadResult] = useState<IngestDocumentResponse | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [documentList, setDocumentList] = useState<DocumentSummary[]>([])
  const [documentListError, setDocumentListError] = useState('')
  const [documentSort, setDocumentSort] = useState<DocumentSort>('updated')
  const [documentView, setDocumentView] = useState<DocumentView>('active')
  const [archivedDocument, setArchivedDocument] = useState<DocumentSummary | null>(
    null,
  )
  const [lifecycleState, setLifecycleState] = useState<RequestState>('idle')
  const [lifecycleError, setLifecycleError] = useState('')
  const [uploadTab, setUploadTab] = useState<UploadTab>('add')
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null)
  const [versionFile, setVersionFile] = useState<File | null>(null)
  const [versionState, setVersionState] = useState<RequestState>('idle')
  const [versionError, setVersionError] = useState('')
  const [versionHistory, setVersionHistory] = useState<DocumentVersionSummary[]>([])
  const [versionHistoryState, setVersionHistoryState] =
    useState<RequestState>('idle')
  const [question, setQuestion] = useState('')
  const [answerState, setAnswerState] = useState<RequestState>('idle')
  const [answerResult, setAnswerResult] = useState<AnswerResponse | null>(null)
  const [answerError, setAnswerError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    void checkHealth(controller.signal)
      .then(async () => {
        setApiState('healthy')
        try {
          const loaded = await listDocuments()
          setDocumentList(loaded)
          setSelectedDocumentId((current) => current ?? loaded[0]?.document_id ?? null)
        } catch (error) {
          setDocumentListError(
            error instanceof Error ? error.message : 'Document list failed',
          )
        }
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setApiState('unavailable')
        }
      })
    return () => controller.abort()
  }, [])

  async function handleRetryConnection() {
    setApiState('checking')
    try {
      await checkHealth()
      setApiState('healthy')
      await refreshDocuments()
    } catch {
      setApiState('unavailable')
    }
  }

  async function loadVersionHistory(documentId: string) {
    setVersionHistoryState('submitting')
    setVersionError('')
    try {
      setVersionHistory(await listDocumentVersions(documentId))
      setVersionHistoryState('success')
    } catch (error) {
      setVersionError(
        error instanceof Error ? error.message : 'Version history failed',
      )
      setVersionHistoryState('error')
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return

    setUploadState('submitting')
    setUploadError('')
    setUploadResult(null)
    try {
      const result = await uploadDocument(file, title.trim())
      setUploadResult(result)
      await refreshDocuments(result.document_id)
      setFile(null)
      setFileInputKey((current) => current + 1)
      setVersionFile(null)
      setVersionError('')
      setVersionState('idle')
      setUploadState('success')
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed')
      if (
        error instanceof ApiRequestError &&
        error.code === 'duplicate_document_content' &&
        error.documentId
      ) {
        const view = error.documentArchived ? 'archived' : 'active'
        setDocumentView(view)
        if (error.documentArchived) {
          setUploadError(
            'This content belongs to an archived document. Restore the existing document to use it again.',
          )
        }
        await refreshDocuments(error.documentId, view)
      }
      setUploadState('error')
    }
  }

  async function handleVersionUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedDocumentId || !versionFile) return

    setVersionState('submitting')
    setVersionError('')
    try {
      const result = await uploadDocumentVersion(
        selectedDocumentId,
        versionFile,
      )
      setUploadResult(result)
      await refreshDocuments(result.document_id)
      setVersionFile(null)
      setVersionState('success')
      setVersionHistory(await listDocumentVersions(result.document_id))
    } catch (error) {
      setVersionError(error instanceof Error ? error.message : 'Version upload failed')
      setVersionState('error')
    }
  }

  async function handleActivateVersion(version: DocumentVersionSummary) {
    if (!selectedDocumentId || version.is_active) return
    setVersionHistoryState('submitting')
    setVersionError('')
    try {
      await activateDocumentVersion(selectedDocumentId, version.version_id)
      await refreshDocuments(selectedDocumentId)
      setVersionHistory(await listDocumentVersions(selectedDocumentId))
      setVersionHistoryState('success')
    } catch (error) {
      setVersionError(
        error instanceof Error ? error.message : 'Version activation failed',
      )
      setVersionHistoryState('error')
    }
  }

  async function refreshDocuments(
    preferredDocumentId?: string,
    view: DocumentView = documentView,
  ) {
    try {
      const loaded = await listDocuments(view)
      setDocumentList(loaded)
      setDocumentListError('')
      setSelectedDocumentId((current) => {
        const preferred = preferredDocumentId ?? current
        return loaded.some((document) => document.document_id === preferred)
          ? preferred ?? null
          : loaded[0]?.document_id ?? null
      })
    } catch (error) {
      setDocumentListError(
        error instanceof Error ? error.message : 'Document list failed',
      )
    }
  }

  async function handleDocumentView(view: DocumentView) {
    setDocumentView(view)
    setDocumentListError('')
    await refreshDocuments(undefined, view)
  }

  const visibleDocumentList =
    documentSort === 'name'
      ? [...documentList].sort((left, right) =>
          left.title.localeCompare(right.title, undefined, { sensitivity: 'base' }),
        )
      : documentList

  const selectedDocument = documentList.find(
    (document) => document.document_id === selectedDocumentId,
  )

  async function handleArchive(document: DocumentSummary) {
    const confirmed = window.confirm(
      `Archive “${document.title}”? It will leave search and the active list, but its versions can be restored.`,
    )
    if (!confirmed) return

    setLifecycleState('submitting')
    setLifecycleError('')
    try {
      await archiveDocument(document.document_id)
      setArchivedDocument(document)
      setDocumentList((current) =>
        current.filter((item) => item.document_id !== document.document_id),
      )
      if (selectedDocumentId === document.document_id) {
        const nextDocument = documentList.find(
          (item) => item.document_id !== document.document_id,
        )
        setSelectedDocumentId(nextDocument?.document_id ?? null)
      }
      setLifecycleState('success')
    } catch (error) {
      setLifecycleError(
        error instanceof Error ? error.message : 'Document archive failed',
      )
      setLifecycleState('error')
    }
  }

  async function handleRestore() {
    if (!archivedDocument) return
    setLifecycleState('submitting')
    setLifecycleError('')
    try {
      await restoreDocument(archivedDocument.document_id)
      setDocumentView('active')
      await refreshDocuments(archivedDocument.document_id, 'active')
      setArchivedDocument(null)
      setLifecycleState('success')
    } catch (error) {
      setLifecycleError(
        error instanceof Error ? error.message : 'Document restore failed',
      )
      setLifecycleState('error')
    }
  }

  async function handleRestoreDocument(document: DocumentSummary) {
    setLifecycleState('submitting')
    setLifecycleError('')
    try {
      await restoreDocument(document.document_id)
      setDocumentList((current) =>
        current.filter((item) => item.document_id !== document.document_id),
      )
      setLifecycleState('success')
    } catch (error) {
      setLifecycleError(
        error instanceof Error ? error.message : 'Document restore failed',
      )
      setLifecycleState('error')
    }
  }

  async function handleQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!question.trim()) return

    setAnswerState('submitting')
    setAnswerError('')
    setAnswerResult(null)
    try {
      const result = await answerQuestion(question.trim())
      setAnswerResult(result)
      setAnswerState('success')
    } catch (error) {
      setAnswerError(error instanceof Error ? error.message : 'Answer request failed')
      setAnswerState('error')
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="DevAtlas home">
          <span className="brand__mark">DA</span>
          <span>DevAtlas</span>
        </a>
        {apiState === 'checking' && (
          <div className="status" role="status">
            <span className="status__dot" aria-hidden="true" />
            Connecting…
          </div>
        )}
      </header>

      {apiState === 'unavailable' && (
        <div className="service-banner" role="alert">
          <div>
            <strong>Service temporarily unavailable</strong>
            <span>Check that the local API is running, then try again.</span>
          </div>
          <button type="button" onClick={() => void handleRetryConnection()}>
            Retry connection
          </button>
        </div>
      )}

      <section className="hero" id="top" aria-labelledby="title">
        <p className="eyebrow">Grounded technical research</p>
        <h1 id="title">
          Ask your documents.
          <br />
          Trace every answer.
        </h1>
        <p className="subtitle">
          Turn technical notes into answers backed by exact versions, chunks,
          and source offsets.
        </p>
      </section>

      <section className="workspace" aria-label="Document research workspace">
        <article className="panel panel--upload">
          <PanelHeading step="01" kicker="Knowledge source" title="Index a document" />
          <section className="document-list" aria-labelledby="documents-title">
            <div className="document-list__views" role="group" aria-label="Document status">
              <button
                type="button"
                aria-pressed={documentView === 'active'}
                onClick={() => void handleDocumentView('active')}
              >
                Active
              </button>
              <button
                type="button"
                aria-pressed={documentView === 'archived'}
                onClick={() => void handleDocumentView('archived')}
              >
                Archived
              </button>
            </div>
            <div className="document-list__heading">
              <h3 id="documents-title">Documents</h3>
              <div>
                <label htmlFor="document-sort">Sort</label>
                <select
                  id="document-sort"
                  value={documentSort}
                  onChange={(event) =>
                    setDocumentSort(event.target.value as DocumentSort)
                  }
                >
                  <option value="updated">Recently updated</option>
                  <option value="name">Name</option>
                </select>
                <span>{documentList.length}</span>
              </div>
            </div>
            {documentList.length === 0 ? (
              <p className="document-list__empty">
                {documentView === 'active'
                  ? 'No indexed documents yet.'
                  : 'No archived documents.'}
              </p>
            ) : (
              <div className="document-list__items">
                {visibleDocumentList.map((document) => (
                  <div className="document-list__row" key={document.document_id}>
                    {documentView === 'active' ? (
                      <button
                        className={
                          document.document_id === selectedDocumentId
                            ? 'document-list__item document-list__item--selected'
                            : 'document-list__item'
                        }
                        type="button"
                        aria-label={`Select ${document.title}, version ${document.active_version_number}`}
                        aria-pressed={document.document_id === selectedDocumentId}
                        onClick={() => {
                          setSelectedDocumentId(document.document_id)
                          setUploadTab('update')
                          setUploadResult(null)
                          setVersionError('')
                          void loadVersionHistory(document.document_id)
                        }}
                      >
                        <strong>{document.title}</strong>
                        <span>
                          Version {document.active_version_number} ·{' '}
                          {document.source_filename}
                        </span>
                      </button>
                    ) : (
                      <div className="document-list__item document-list__item--archived">
                        <strong>{document.title}</strong>
                        <span>
                          Version {document.active_version_number} ·{' '}
                          {document.source_filename}
                        </span>
                      </div>
                    )}
                    <button
                      className="document-list__archive"
                      type="button"
                      aria-label={`${documentView === 'active' ? 'Archive' : 'Restore'} ${document.title}`}
                      disabled={lifecycleState === 'submitting'}
                      onClick={() =>
                        void (documentView === 'active'
                          ? handleArchive(document)
                          : handleRestoreDocument(document))
                      }
                    >
                      {documentView === 'active' ? 'Archive' : 'Restore'}
                    </button>
                  </div>
                ))}
              </div>
            )}
            {documentListError && (
              <p className="notice notice--error">{documentListError}</p>
            )}
            {archivedDocument && (
              <div className="notice notice--success document-lifecycle" role="status">
                <span>“{archivedDocument.title}” archived and removed from search.</span>
                <button
                  type="button"
                  disabled={lifecycleState === 'submitting'}
                  onClick={() => void handleRestore()}
                >
                  Undo
                </button>
              </div>
            )}
            {lifecycleError && (
              <p className="notice notice--error" role="alert">
                {lifecycleError}
              </p>
            )}
          </section>

          <div className="upload-tabs" role="tablist" aria-label="Document action">
            <button
              type="button"
              role="tab"
              aria-selected={uploadTab === 'add'}
              aria-controls="add-document-panel"
              id="add-document-tab"
              onClick={() => setUploadTab('add')}
            >
              Add document
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={uploadTab === 'update'}
              aria-controls="update-document-panel"
              id="update-document-tab"
              onClick={() => {
                setUploadTab('update')
                if (selectedDocumentId) {
                  void loadVersionHistory(selectedDocumentId)
                }
              }}
            >
              Update document
            </button>
          </div>

          {uploadTab === 'add' && (
            <div
              className="upload-tab-panel"
              role="tabpanel"
              id="add-document-panel"
              aria-labelledby="add-document-tab"
            >
              <form onSubmit={handleUpload} className="form-stack">
                <label>
                  <span>Display title <small>Optional</small></span>
                  <input
                    type="text"
                    value={title}
                    maxLength={255}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="Defaults to the filename"
                  />
                </label>

                <FileDropField
                  inputKey={fileInputKey}
                  label="Plain-text file"
                  file={file}
                  onFile={setFile}
                />

                <button
                  type="submit"
                  disabled={
                    apiState !== 'healthy' ||
                    !file ||
                    uploadState === 'submitting'
                  }
                >
                  {uploadState === 'submitting' ? 'Indexing…' : 'Index document'}
                </button>
              </form>
              {uploadResult && <UploadSuccess result={uploadResult} />}
              {uploadError && (
                <p className="notice notice--error" role="alert">{uploadError}</p>
              )}
            </div>
          )}

          {uploadTab === 'update' && (
            <div
              className="upload-tab-panel"
              role="tabpanel"
              id="update-document-panel"
              aria-labelledby="update-document-tab"
            >
              {selectedDocument ? (
                <>
              <div className="selected-document">
                <span>Selected document</span>
                <strong>{selectedDocument.title}</strong>
              </div>
              <form className="version-form" onSubmit={handleVersionUpload}>
                <div>
                  <strong>Update this document</strong>
                  <span>Keep its identity and source history.</span>
                </div>
                <FileDropField
                  inputKey={selectedDocument.active_version_id}
                  label="New version file"
                  file={versionFile}
                  onFile={setVersionFile}
                />
                <button
                  type="submit"
                  disabled={
                    apiState !== 'healthy' ||
                    !versionFile ||
                    versionState === 'submitting'
                  }
                >
                  {versionState === 'submitting'
                    ? 'Indexing new version…'
                    : `Upload Version ${selectedDocument.active_version_number + 1}`}
                </button>
              </form>
                  <section className="version-history" aria-labelledby="version-history-title">
                    <div className="version-history__heading">
                      <strong id="version-history-title">Version history</strong>
                      <span>{versionHistory.length}</span>
                    </div>
                    {versionHistoryState === 'submitting' &&
                    versionHistory.length === 0 ? (
                      <p>Loading versions…</p>
                    ) : (
                      <div className="version-history__items">
                        {versionHistory.map((version) => (
                          <div className="version-history__item" key={version.version_id}>
                            <div>
                              <strong>Version {version.version_number}</strong>
                              <span>{version.source_filename}</span>
                              <small>
                                {version.chunk_count} chunks ·{' '}
                                {new Date(version.created_at).toLocaleString()}
                              </small>
                            </div>
                            {version.is_active ? (
                              <span className="version-history__current">Current</span>
                            ) : (
                              <button
                                type="button"
                                disabled={versionHistoryState === 'submitting'}
                                onClick={() => void handleActivateVersion(version)}
                              >
                                Make current
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                  {uploadResult && <UploadSuccess result={uploadResult} />}
                  {versionError && (
                    <p className="notice notice--error" role="alert">
                      {versionError}
                    </p>
                  )}
                </>
              ) : (
                <p className="upload-tab-panel__empty">
                  Select a document above before uploading a new version.
                </p>
              )}
            </div>
          )}
        </article>

        <article className="panel panel--answer">
          <PanelHeading step="02" kicker="Grounded answer" title="Ask the knowledge base" />
          <form onSubmit={handleQuestion} className="question-form">
            <label htmlFor="question">Question</label>
            <textarea
              id="question"
              value={question}
              maxLength={2000}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="How does this system preserve source provenance?"
              rows={4}
              required
            />
            <div className="question-form__footer">
              <span>{question.length} / 2,000</span>
              <button
                type="submit"
                disabled={
                  apiState !== 'healthy' ||
                  !question.trim() ||
                  answerState === 'submitting'
                }
              >
                {answerState === 'submitting' ? 'Researching…' : 'Generate answer'}
              </button>
            </div>
          </form>

          {answerError && (
            <p className="notice notice--error" role="alert">{answerError}</p>
          )}
          {answerResult && <Answer result={answerResult} />}
        </article>
      </section>

      <footer>Single-user learning build · Answers are limited to indexed evidence</footer>
    </main>
  )
}

function PanelHeading(props: { step: string; kicker: string; title: string }) {
  return (
    <div className="panel__heading">
      <span className="step">{props.step}</span>
      <div>
        <p className="kicker">{props.kicker}</p>
        <h2>{props.title}</h2>
      </div>
    </div>
  )
}

function FileDropField(props: {
  inputKey: string | number
  label: string
  file: File | null
  onFile: (file: File | null) => void
}) {
  const [isDragging, setIsDragging] = useState(false)

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setIsDragging(false)
    props.onFile(event.dataTransfer.files[0] ?? null)
  }

  return (
    <label
      className={isDragging ? 'file-field file-field--dragging' : 'file-field'}
      onDragEnter={(event) => {
        event.preventDefault()
        setIsDragging(true)
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <span>{props.label}</span>
      <input
        key={props.inputKey}
        type="file"
        accept=".txt,text/plain"
        onChange={(event) => props.onFile(event.target.files?.[0] ?? null)}
        required
      />
      <span className="file-field__surface">
        <span className="file-field__icon" aria-hidden="true">↑</span>
        <span>{props.file ? props.file.name : 'Choose a .txt file'}</span>
        <small>
          {props.file ? 'Ready to upload' : 'or drop it here'} · UTF-8 · maximum 1 MiB
        </small>
      </span>
    </label>
  )
}

function UploadSuccess({ result }: { result: IngestDocumentResponse }) {
  return (
    <div className="notice notice--success" role="status">
      <strong>Version {result.version_number}: {result.filename}</strong>
      <span>{result.chunk_count} chunk indexed and ready</span>
    </div>
  )
}

function Answer({ result }: { result: AnswerResponse }) {
  return (
    <section className="answer" aria-live="polite">
      <div className="answer__meta">
        <span className={result.has_sufficient_evidence ? 'grounded' : 'insufficient'}>
          {result.has_sufficient_evidence ? 'Evidence grounded' : 'Insufficient evidence'}
        </span>
        <span>{result.citations.length} sources</span>
      </div>
      <p className="answer__text">{result.answer}</p>

      {result.citations.length > 0 && (
        <div className="sources">
          <h3>Sources</h3>
          {result.citations.map((citation) => (
            <details key={citation.citation_id}>
              <summary>
                <span>{citation.citation_id}</span>
                <strong>{citation.document_title}</strong>
                <small>v{citation.version_number} · chunk {citation.ordinal}</small>
              </summary>
              <blockquote>{citation.text}</blockquote>
              <p>Characters {citation.start_offset}–{citation.end_offset}</p>
            </details>
          ))}
        </div>
      )}
    </section>
  )
}
