import { DragEvent, FormEvent, useEffect, useState } from 'react'

import {
  AnswerResponse,
  ApiRequestError,
  ConversationSummary,
  ConversationTurn,
  CorrectiveAnswerResponse,
  DocumentSummary,
  DocumentVersionSummary,
  IngestDocumentResponse,
  IngestionJob,
  KnowledgeBaseSummary,
  ResearchResponse,
  SessionResponse,
  WorkspaceQuestionResponse,
  acceptWorkspaceInvitation,
  activateDocumentVersion,
  askConversation,
  askCorrectiveQuestion,
  askWorkspaceQuestion,
  archiveDocument,
  checkHealth,
  createDevelopmentSession,
  createConversation,
  createWorkspace,
  createWorkspaceInvitation,
  createKnowledgeBase,
  getIngestionJob,
  getSession,
  listDocuments,
  listConversations,
  listConversationTurns,
  listKnowledgeBases,
  listWorkspaces,
  listDocumentVersions,
  restoreDocument,
  runResearch,
  submitIngestionJob,
  selectWorkspace,
  uploadDocumentVersion,
} from './api'
import { AuthPanel } from './AuthPanel'
import { WorkspaceControls } from './WorkspaceControls'
import {
  restoreCognitoSession,
  signOut,
  usesCognitoAuthentication,
} from './auth'

type ApiState = 'checking' | 'healthy' | 'unavailable'
type RequestState = 'idle' | 'submitting' | 'success' | 'error'
type DocumentSort = 'updated' | 'name'
type DocumentView = 'active' | 'archived'
type UploadTab = 'add' | 'update'
type AuthenticationState = 'checking' | 'signed-in' | 'signed-out'

async function loadAccessibleWorkspaces(
  currentSession: SessionResponse,
): Promise<SessionResponse[]> {
  const listed = await listWorkspaces()
  const valid = Array.isArray(listed)
    ? listed.filter(
        (item) =>
          typeof item?.workspace_id === 'string' &&
          typeof item?.workspace_name === 'string',
      )
    : []
  return valid.some((item) => item.workspace_id === currentSession.workspace_id)
    ? valid
    : [currentSession, ...valid]
}

export default function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')
  const [authenticationState, setAuthenticationState] =
    useState<AuthenticationState>('checking')
  const [session, setSession] = useState<SessionResponse | null>(null)
  const [workspaces, setWorkspaces] = useState<SessionResponse[]>([])
  const [workspaceNotice, setWorkspaceNotice] = useState('')
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [fileInputKey, setFileInputKey] = useState(0)
  const [uploadState, setUploadState] = useState<RequestState>('idle')
  const [uploadResult, setUploadResult] = useState<IngestDocumentResponse | null>(null)
  const [ingestionJob, setIngestionJob] = useState<IngestionJob | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [documentList, setDocumentList] = useState<DocumentSummary[]>([])
  const [documentListError, setDocumentListError] = useState('')
  const [documentSort, setDocumentSort] = useState<DocumentSort>('updated')
  const [documentView, setDocumentView] = useState<DocumentView>('active')
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseSummary[]>([])
  const [knowledgeBaseName, setKnowledgeBaseName] = useState('')
  const [knowledgeBaseError, setKnowledgeBaseError] = useState('')
  const [uploadKnowledgeBaseId, setUploadKnowledgeBaseId] = useState('')
  const [documentKnowledgeBaseId, setDocumentKnowledgeBaseId] = useState('')
  const [searchKnowledgeBaseIds, setSearchKnowledgeBaseIds] = useState<string[]>([])
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
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [conversationTurns, setConversationTurns] = useState<ConversationTurn[]>([])
  const [answerError, setAnswerError] = useState('')
  const [workspaceQuestion, setWorkspaceQuestion] = useState('')
  const [workspaceAnswer, setWorkspaceAnswer] =
    useState<WorkspaceQuestionResponse | null>(null)
  const [workspaceAnswerState, setWorkspaceAnswerState] =
    useState<RequestState>('idle')
  const [workspaceAnswerError, setWorkspaceAnswerError] = useState('')
  const [researchQuestion, setResearchQuestion] = useState('')
  const [researchResult, setResearchResult] = useState<ResearchResponse | null>(null)
  const [researchState, setResearchState] = useState<RequestState>('idle')
  const [researchError, setResearchError] = useState('')
  const [correctiveQuestion, setCorrectiveQuestion] = useState('')
  const [correctiveResult, setCorrectiveResult] =
    useState<CorrectiveAnswerResponse | null>(null)
  const [correctiveState, setCorrectiveState] = useState<RequestState>('idle')
  const [correctiveError, setCorrectiveError] = useState('')
  const canWrite = session?.role === 'owner' || session?.role === 'editor'

  useEffect(() => {
    const controller = new AbortController()
    void checkHealth(controller.signal)
      .then(async () => {
        if (usesCognitoAuthentication) {
          const restored = await restoreCognitoSession()
          if (!restored) {
            setAuthenticationState('signed-out')
            setApiState('healthy')
            return
          }
        } else {
          await createDevelopmentSession()
        }
        let currentSession = await getSession()
        const invitationToken = new URLSearchParams(window.location.search).get('invite')
        if (invitationToken) {
          currentSession = await acceptWorkspaceInvitation(invitationToken)
          selectWorkspace(currentSession)
          window.history.replaceState({}, document.title, '/')
          setWorkspaceNotice(`Joined ${currentSession.workspace_name}.`)
        }
        setSession(currentSession)
        setWorkspaces(await loadAccessibleWorkspaces(currentSession))
        setAuthenticationState('signed-in')
        setApiState('healthy')
        try {
          const loadedKnowledgeBases = await listKnowledgeBases()
          setKnowledgeBases(loadedKnowledgeBases)
          setUploadKnowledgeBaseId(
            loadedKnowledgeBases.find((item) => item.is_default)?.id ??
              loadedKnowledgeBases[0]?.id ??
              '',
          )
          setSearchKnowledgeBaseIds(loadedKnowledgeBases.map((item) => item.id))
          const loaded = await listDocuments()
          setDocumentList(loaded)
          setSelectedDocumentId((current) => current ?? loaded[0]?.document_id ?? null)
          const loadedConversations = await listConversations()
          setConversations(loadedConversations)
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
      if (usesCognitoAuthentication && !(await restoreCognitoSession())) {
        setAuthenticationState('signed-out')
        setApiState('healthy')
        return
      }
      if (!usesCognitoAuthentication) await createDevelopmentSession()
      setSession(await getSession())
      setAuthenticationState('signed-in')
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

  async function handleAuthenticated() {
    let currentSession = await getSession()
    const invitationToken = new URLSearchParams(window.location.search).get('invite')
    if (invitationToken) {
      currentSession = await acceptWorkspaceInvitation(invitationToken)
      selectWorkspace(currentSession)
      window.history.replaceState({}, document.title, '/')
      setWorkspaceNotice(`Joined ${currentSession.workspace_name}.`)
    }
    setSession(currentSession)
    setWorkspaces(await loadAccessibleWorkspaces(currentSession))
    setAuthenticationState('signed-in')
    const loadedKnowledgeBases = await listKnowledgeBases()
    setKnowledgeBases(loadedKnowledgeBases)
    setUploadKnowledgeBaseId(
      loadedKnowledgeBases.find((item) => item.is_default)?.id ??
        loadedKnowledgeBases[0]?.id ??
        '',
    )
    setSearchKnowledgeBaseIds(loadedKnowledgeBases.map((item) => item.id))
    const loadedDocuments = await listDocuments()
    setDocumentList(loadedDocuments)
    setSelectedDocumentId(loadedDocuments[0]?.document_id ?? null)
    setConversations(await listConversations())
  }

  async function handleWorkspaceSwitch(workspaceId: string) {
    const workspace = workspaces.find((item) => item.workspace_id === workspaceId)
    if (!workspace) return
    selectWorkspace(workspace)
    setSession(workspace)
    const loadedKnowledgeBases = await listKnowledgeBases()
    setKnowledgeBases(loadedKnowledgeBases)
    setUploadKnowledgeBaseId(loadedKnowledgeBases.find((item) => item.is_default)?.id ?? '')
    setSearchKnowledgeBaseIds(loadedKnowledgeBases.map((item) => item.id))
    setDocumentKnowledgeBaseId('')
    setDocumentList(await listDocuments())
    setConversations(await listConversations())
    setSelectedDocumentId(null)
    setWorkspaceNotice(`Switched to ${workspace.workspace_name}.`)
  }

  async function handleCreateWorkspace(name: string) {
    const created = await createWorkspace(name)
    setWorkspaces((current) => [...current, created])
    selectWorkspace(created)
    setSession(created)
    const loadedKnowledgeBases = await listKnowledgeBases()
    setKnowledgeBases(loadedKnowledgeBases)
    setUploadKnowledgeBaseId(loadedKnowledgeBases[0]?.id ?? '')
    setSearchKnowledgeBaseIds(loadedKnowledgeBases.map((item) => item.id))
    setDocumentList([])
    setConversations([])
    setSelectedDocumentId(null)
    setWorkspaceNotice(`Created ${created.workspace_name}.`)
  }

  async function handleInviteMember(
    email: string,
    requestedRole: 'editor' | 'viewer',
  ): Promise<string> {
    if (!session || session.role !== 'owner') {
      throw new Error('Only workspace owners can create invitations.')
    }
    const invitation = await createWorkspaceInvitation(
      session.workspace_id,
      email,
      requestedRole,
    )
    const link = `${window.location.origin}/?invite=${encodeURIComponent(invitation.token)}`
    setWorkspaceNotice('Invitation link created. It expires in 7 days.')
    return link
  }

  function handleOwnershipTransferred(updatedSession: SessionResponse) {
    selectWorkspace(updatedSession)
    setSession(updatedSession)
    setWorkspaces((current) => current.map((workspace) =>
      workspace.workspace_id === updatedSession.workspace_id
        ? updatedSession
        : workspace,
    ))
    setWorkspaceNotice('Workspace ownership transferred. Your role is now editor.')
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return

    setUploadState('submitting')
    setUploadError('')
    setUploadResult(null)
    setIngestionJob(null)
    try {
      let job = await submitIngestionJob(
        file,
        title.trim(),
        uploadKnowledgeBaseId,
        crypto.randomUUID(),
      )
      setIngestionJob(job)
      for (
        let pollCount = 0;
        pollCount < 80 &&
        (job.status === 'queued' || job.status === 'processing');
        pollCount += 1
      ) {
        await new Promise((resolve) => window.setTimeout(resolve, 750))
        job = await getIngestionJob(job.id)
        setIngestionJob(job)
      }
      if (job.status === 'queued' || job.status === 'processing') {
        throw new Error(
          `Ingestion is still running. Job ${job.id} can be checked again later.`,
        )
      }
      if (job.status === 'failed') {
        throw new Error(job.error_message ?? 'Background ingestion failed')
      }
      await refreshDocuments(job.document_id ?? undefined)
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
      const loaded = await listDocuments(view, documentKnowledgeBaseId || undefined)
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
  const nextVersionNumber = selectedDocument
    ? Math.max(
        selectedDocument.active_version_number,
        ...versionHistory.map((version) => version.version_number),
      ) + 1
    : 1

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
    if (!question.trim() || searchKnowledgeBaseIds.length === 0) return

    setAnswerState('submitting')
    setAnswerError('')
    try {
      const submittedQuestion = question.trim()
      let conversationId = activeConversationId
      if (!conversationId) {
        const created = await createConversation(submittedQuestion.slice(0, 120))
        conversationId = created.id
        setActiveConversationId(created.id)
        setConversations((current) => [created, ...current])
      }
      const turn = await askConversation(
        conversationId,
        submittedQuestion,
        searchKnowledgeBaseIds,
      )
      setConversationTurns((current) => [...current, turn])
      setQuestion('')
      setConversations((current) => {
        const active = current.find((item) => item.id === conversationId)
        return active
          ? [active, ...current.filter((item) => item.id !== conversationId)]
          : current
      })
      setAnswerState('success')
    } catch (error) {
      setAnswerError(error instanceof Error ? error.message : 'Answer request failed')
      setAnswerState('error')
    }
  }

  async function handleSelectConversation(conversationId: string) {
    setActiveConversationId(conversationId)
    setAnswerError('')
    setAnswerState('submitting')
    try {
      setConversationTurns(await listConversationTurns(conversationId))
      setAnswerState('success')
    } catch (error) {
      setAnswerError(
        error instanceof Error ? error.message : 'Conversation history failed',
      )
      setAnswerState('error')
    }
  }

  function handleNewConversation() {
    setActiveConversationId(null)
    setConversationTurns([])
    setQuestion('')
    setAnswerError('')
    setAnswerState('idle')
  }

  async function handleWorkspaceQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const submittedQuestion = workspaceQuestion.trim()
    if (!submittedQuestion) return
    setWorkspaceAnswerState('submitting')
    setWorkspaceAnswerError('')
    setWorkspaceAnswer(null)
    try {
      setWorkspaceAnswer(await askWorkspaceQuestion(submittedQuestion))
      setWorkspaceAnswerState('success')
    } catch (error) {
      setWorkspaceAnswerError(
        error instanceof Error ? error.message : 'Workspace question failed',
      )
      setWorkspaceAnswerState('error')
    }
  }

  async function handleResearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const submittedQuestion = researchQuestion.trim()
    if (!submittedQuestion) return
    setResearchState('submitting')
    setResearchError('')
    setResearchResult(null)
    try {
      setResearchResult(await runResearch(submittedQuestion))
      setResearchState('success')
    } catch (error) {
      setResearchError(
        error instanceof Error ? error.message : 'Research request failed',
      )
      setResearchState('error')
    }
  }

  async function handleCorrectiveQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const submittedQuestion = correctiveQuestion.trim()
    if (!submittedQuestion || searchKnowledgeBaseIds.length === 0) return
    setCorrectiveState('submitting')
    setCorrectiveError('')
    setCorrectiveResult(null)
    try {
      setCorrectiveResult(
        await askCorrectiveQuestion(submittedQuestion, searchKnowledgeBaseIds),
      )
      setCorrectiveState('success')
    } catch (error) {
      setCorrectiveError(
        error instanceof Error ? error.message : 'Corrective answer failed',
      )
      setCorrectiveState('error')
    }
  }

  async function handleCreateKnowledgeBase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = knowledgeBaseName.trim()
    if (!name) return
    setKnowledgeBaseError('')
    try {
      const created = await createKnowledgeBase(name)
      setKnowledgeBases((current) => [...current, created])
      setSearchKnowledgeBaseIds((current) => [...current, created.id])
      setUploadKnowledgeBaseId(created.id)
      setKnowledgeBaseName('')
    } catch (error) {
      setKnowledgeBaseError(
        error instanceof Error ? error.message : 'Knowledge base creation failed',
      )
    }
  }

  function toggleSearchKnowledgeBase(id: string) {
    setSearchKnowledgeBaseIds((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    )
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Retrieval Works home">
          <span className="brand__mark" aria-hidden="true">
            RW
          </span>
          <span>Retrieval Works</span>
        </a>
        {apiState === 'checking' && (
          <div className="status" role="status">
            <span className="status__dot" aria-hidden="true" />
            Connecting…
          </div>
        )}
        {apiState === 'healthy' && session && (
          <div className="session-context" aria-label="Current workspace and role">
            <WorkspaceControls
              session={session}
              workspaces={workspaces}
              onSwitch={handleWorkspaceSwitch}
              onCreate={handleCreateWorkspace}
              onInvite={handleInviteMember}
              onOwnershipTransferred={handleOwnershipTransferred}
            />
            {usesCognitoAuthentication && (
              <button type="button" onClick={() => void signOut()}>Sign out</button>
            )}
          </div>
        )}
      </header>

      {workspaceNotice && <div className="workspace-notice" role="status">{workspaceNotice}</div>}

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

      {apiState === 'healthy' && authenticationState === 'signed-out' && (
        <AuthPanel onAuthenticated={handleAuthenticated} />
      )}

      {authenticationState === 'signed-in' && <section className="workspace" aria-label="Document research workspace">
        <article className="panel panel--upload">
          <PanelHeading step="01" kicker="Knowledge source" title="Index a document" />
          <section className="knowledge-bases" aria-labelledby="knowledge-bases-title">
            <div className="document-list__heading">
              <h3 id="knowledge-bases-title">Knowledge bases</h3>
              <span>{knowledgeBases.length}</span>
            </div>
            {canWrite && (
              <form className="knowledge-bases__create" onSubmit={handleCreateKnowledgeBase}>
                <input
                  type="text"
                  aria-label="New knowledge base name"
                  placeholder="New knowledge base"
                  maxLength={255}
                  value={knowledgeBaseName}
                  onChange={(event) => setKnowledgeBaseName(event.target.value)}
                />
                <button type="submit" disabled={!knowledgeBaseName.trim()}>Create</button>
              </form>
            )}
            {knowledgeBaseError && <p className="notice notice--error">{knowledgeBaseError}</p>}
          </section>
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
            <label className="scope-select">
              <span>Show documents from</span>
              <select
                value={documentKnowledgeBaseId}
                onChange={(event) => {
                  setDocumentKnowledgeBaseId(event.target.value)
                  void listDocuments(documentView, event.target.value || undefined).then(
                    setDocumentList,
                  )
                }}
              >
                <option value="">All knowledge bases</option>
                {knowledgeBases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
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
                          setVersionHistory([])
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
                        <small>{document.knowledge_base_name}</small>
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
                      disabled={!canWrite || lifecycleState === 'submitting'}
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

          {!canWrite && session && (
            <p className="read-only-notice" role="status">
              Viewer access is read-only. You can search and inspect documents,
              but only an Editor or Owner can change them.
            </p>
          )}

          <div className="upload-tabs" role="tablist" aria-label="Document action">
            <button
              type="button"
              role="tab"
              aria-selected={uploadTab === 'add'}
              aria-controls="add-document-panel"
              id="add-document-tab"
              disabled={!canWrite}
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
              disabled={!canWrite}
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
                  <span>Knowledge base</span>
                  <select
                    value={uploadKnowledgeBaseId}
                    disabled={!canWrite}
                    onChange={(event) => setUploadKnowledgeBaseId(event.target.value)}
                    required
                  >
                    {knowledgeBases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>
                  <span>Display title <small>Optional</small></span>
                  <input
                    type="text"
                    value={title}
                    maxLength={255}
                    disabled={!canWrite}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="Defaults to the filename"
                  />
                </label>

                <FileDropField
                  inputKey={fileInputKey}
                  label="Document file"
                  file={file}
                  onFile={setFile}
                  disabled={!canWrite}
                />

                <button
                  type="submit"
                  disabled={
                    apiState !== 'healthy' ||
                    !canWrite ||
                    !file ||
                    uploadState === 'submitting'
                  }
                >
                  {uploadState === 'submitting' ? 'Indexing…' : 'Index document'}
                </button>
              </form>
              {uploadResult && <UploadSuccess result={uploadResult} />}
              {ingestionJob && (
                <div className={`notice notice--${ingestionJob.status === 'failed' ? 'error' : 'success'}`} role="status">
                  <strong>Ingestion {ingestionJob.status}</strong>
                  <span>Attempt {ingestionJob.attempt_count} · Job {ingestionJob.id}</span>
                </div>
              )}
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
                  disabled={!canWrite}
                />
                <button
                  type="submit"
                  disabled={
                    apiState !== 'healthy' ||
                    !canWrite ||
                    !versionFile ||
                    versionState === 'submitting'
                  }
                >
                  {versionState === 'submitting'
                    ? 'Indexing new version…'
                    : `Upload Version ${nextVersionNumber}`}
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
                                disabled={
                                  !canWrite || versionHistoryState === 'submitting'
                                }
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
          <section className="workspace-tools" aria-labelledby="workspace-tools-title">
            <div>
              <p className="kicker">Tool calling</p>
              <h3 id="workspace-tools-title">Ask about this workspace</h3>
              <p>Uses live workspace metadata, not document chunks.</p>
            </div>
            <form onSubmit={handleWorkspaceQuestion}>
              <label htmlFor="workspace-question">Workspace question</label>
              <input
                id="workspace-question"
                type="text"
                value={workspaceQuestion}
                maxLength={2000}
                onChange={(event) => setWorkspaceQuestion(event.target.value)}
                placeholder="Which knowledge base has the most documents?"
                required
              />
              <button
                type="submit"
                disabled={
                  apiState !== 'healthy' ||
                  !workspaceQuestion.trim() ||
                  workspaceAnswerState === 'submitting'
                }
              >
                {workspaceAnswerState === 'submitting' ? 'Calling tool…' : 'Ask workspace'}
              </button>
            </form>
            {workspaceAnswer && (
              <div className="workspace-tools__answer" aria-live="polite">
                <p>{workspaceAnswer.answer}</p>
                <span>
                  Tool used: {workspaceAnswer.tools.map((tool) => tool.name).join(', ')}
                </span>
              </div>
            )}
            {workspaceAnswerError && (
              <p className="notice notice--error" role="alert">
                {workspaceAnswerError}
              </p>
            )}
          </section>
          <section className="research-agent" aria-labelledby="research-agent-title">
            <div>
              <p className="kicker">Bounded agent</p>
              <h3 id="research-agent-title">Research across knowledge bases</h3>
              <p>The model may choose up to three read-only tool calls.</p>
            </div>
            <form className="question-form" onSubmit={handleResearch}>
              <label htmlFor="research-question">Research question</label>
              <textarea
                id="research-question"
                value={researchQuestion}
                maxLength={2000}
                onChange={(event) => setResearchQuestion(event.target.value)}
                placeholder="Compare how the indexed notes describe authorization and transaction boundaries."
                rows={3}
                required
              />
              <div className="question-form__footer">
                <span>{researchQuestion.length} / 2,000</span>
                <button
                  type="submit"
                  disabled={
                    apiState !== 'healthy' ||
                    !researchQuestion.trim() ||
                    researchState === 'submitting'
                  }
                >
                  {researchState === 'submitting' ? 'Researching…' : 'Run research'}
                </button>
              </div>
            </form>
            {researchResult && (
              <div aria-live="polite">
                <ol className="research-agent__steps">
                  {researchResult.steps.map((step) => (
                    <li key={`${step.ordinal}-${step.tool_name}`}>
                      <strong>{step.tool_name}</strong>
                      <span>{step.summary}</span>
                    </li>
                  ))}
                </ol>
                <p className="research-agent__stop">
                  Stop reason: {researchResult.stop_reason}
                </p>
                <Answer result={researchResult} />
              </div>
            )}
            {researchError && (
              <p className="notice notice--error" role="alert">
                {researchError}
              </p>
            )}
          </section>
          <section className="corrective-rag" aria-labelledby="corrective-rag-title">
            <div>
              <p className="kicker">Corrective RAG</p>
              <h3 id="corrective-rag-title">Retry only when evidence is insufficient</h3>
              <p>At most one alternative retrieval query is generated.</p>
            </div>
            <form className="question-form" onSubmit={handleCorrectiveQuestion}>
              <label htmlFor="corrective-question">Corrective RAG question</label>
              <textarea
                id="corrective-question"
                value={correctiveQuestion}
                maxLength={2000}
                onChange={(event) => setCorrectiveQuestion(event.target.value)}
                rows={3}
                required
              />
              <div className="question-form__footer">
                <span>{correctiveQuestion.length} / 2,000</span>
                <button
                  type="submit"
                  disabled={
                    apiState !== 'healthy' ||
                    !correctiveQuestion.trim() ||
                    searchKnowledgeBaseIds.length === 0 ||
                    correctiveState === 'submitting'
                  }
                >
                  {correctiveState === 'submitting'
                    ? 'Checking evidence…'
                    : 'Run corrective answer'}
                </button>
              </div>
            </form>
            {correctiveResult && (
              <div aria-live="polite">
                <p className="corrective-rag__status">
                  {correctiveResult.correction_applied
                    ? `Correction applied: ${correctiveResult.corrective_query}`
                    : 'Correction not needed'}
                </p>
                <Answer result={correctiveResult} />
              </div>
            )}
            {correctiveError && (
              <p className="notice notice--error" role="alert">
                {correctiveError}
              </p>
            )}
          </section>
          <section className="conversation-list" aria-labelledby="conversations-title">
            <div className="conversation-list__heading">
              <h3 id="conversations-title">Conversations</h3>
              <button type="button" onClick={handleNewConversation}>New conversation</button>
            </div>
            {conversations.length > 0 && (
              <div className="conversation-list__items">
                {conversations.map((conversation) => (
                  <button
                    type="button"
                    key={conversation.id}
                    aria-pressed={conversation.id === activeConversationId}
                    onClick={() => void handleSelectConversation(conversation.id)}
                  >
                    <strong>{conversation.title}</strong>
                    <span>{new Date(conversation.updated_at).toLocaleString()}</span>
                  </button>
                ))}
              </div>
            )}
          </section>
          <div className="conversation-transcript" aria-live="polite">
            {conversationTurns.map((turn) => (
              <article className="conversation-turn" key={turn.id}>
                <p className="conversation-turn__question">{turn.question}</p>
                {turn.standalone_question !== turn.question && (
                  <details className="conversation-turn__rewrite">
                    <summary>Resolved follow-up</summary>
                    <p>{turn.standalone_question}</p>
                  </details>
                )}
                <Answer result={turn} />
              </article>
            ))}
          </div>
          <form onSubmit={handleQuestion} className="question-form">
            <fieldset className="scope-picker">
              <legend>Search scope</legend>
              {knowledgeBases.map((item) => (
                <label key={item.id}>
                  <input
                    type="checkbox"
                    checked={searchKnowledgeBaseIds.includes(item.id)}
                    onChange={() => toggleSearchKnowledgeBase(item.id)}
                  />
                  <span>{item.name} <small>{item.document_count} docs</small></span>
                </label>
              ))}
            </fieldset>
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
                  searchKnowledgeBaseIds.length === 0 ||
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
        </article>
      </section>}

      <footer>Private workspace build · Answers are limited to indexed evidence</footer>
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
  disabled?: boolean
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
        if (!props.disabled) setIsDragging(true)
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => {
        if (!props.disabled) setIsDragging(false)
      }}
      onDrop={props.disabled ? undefined : handleDrop}
    >
      <span>{props.label}</span>
      <input
        key={props.inputKey}
        type="file"
        accept=".txt,.pdf,text/plain,application/pdf"
        disabled={props.disabled}
        onChange={(event) => props.onFile(event.target.files?.[0] ?? null)}
        required
      />
      <span className="file-field__surface">
        <span className="file-field__icon" aria-hidden="true">↑</span>
        <span>{props.file ? props.file.name : 'Choose a .txt or .pdf file'}</span>
        <small>
          {props.file ? 'Ready to upload' : 'or drop it here'} · TXT 1 MiB · PDF 10 MiB
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
                <small>
                  v{citation.version_number} · chunk {citation.ordinal}
                  {citation.page_start !== null && (
                    <> · page {citation.page_start}{citation.page_end !== citation.page_start ? `–${citation.page_end}` : ''}</>
                  )}
                </small>
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
