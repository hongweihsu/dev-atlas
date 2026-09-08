import { FormEvent, useEffect, useState } from 'react'

import {
  AnswerResponse,
  IngestDocumentResponse,
  answerQuestion,
  checkHealth,
  uploadDocument,
} from './api'

type ApiState = 'checking' | 'healthy' | 'unavailable'
type RequestState = 'idle' | 'submitting' | 'success' | 'error'

export default function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploadState, setUploadState] = useState<RequestState>('idle')
  const [uploadResult, setUploadResult] = useState<IngestDocumentResponse | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [question, setQuestion] = useState('')
  const [answerState, setAnswerState] = useState<RequestState>('idle')
  const [answerResult, setAnswerResult] = useState<AnswerResponse | null>(null)
  const [answerError, setAnswerError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    void checkHealth(controller.signal)
      .then(() => setApiState('healthy'))
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
    } catch {
      setApiState('unavailable')
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file || !title.trim()) return

    setUploadState('submitting')
    setUploadError('')
    setUploadResult(null)
    try {
      const result = await uploadDocument(file, title.trim())
      setUploadResult(result)
      setUploadState('success')
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed')
      setUploadState('error')
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
          <form onSubmit={handleUpload} className="form-stack">
            <label>
              <span>Document title</span>
              <input
                type="text"
                value={title}
                maxLength={255}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Architecture notes"
                required
              />
            </label>

            <label className="file-field">
              <span>Plain-text file</span>
              <input
                type="file"
                accept=".txt,text/plain"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                required
              />
              <span className="file-field__surface">
                <span className="file-field__icon" aria-hidden="true">↑</span>
                <span>{file ? file.name : 'Choose a .txt file'}</span>
                <small>UTF-8 · maximum 1 MiB</small>
              </span>
            </label>

            <button
              type="submit"
              disabled={
                apiState !== 'healthy' ||
                !file ||
                !title.trim() ||
                uploadState === 'submitting'
              }
            >
              {uploadState === 'submitting' ? 'Indexing…' : 'Index document'}
            </button>
          </form>

          {uploadResult && (
            <div className="notice notice--success" role="status">
              <strong>{uploadResult.filename}</strong>
              <span>{uploadResult.chunk_count} chunk indexed and ready</span>
            </div>
          )}
          {uploadError && (
            <p className="notice notice--error" role="alert">{uploadError}</p>
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
