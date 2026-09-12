interface ApiErrorBody {
  detail?:
    | string
    | {
        code?: string
        message?: string
        document_id?: string
        document_archived?: boolean
      }
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly code?: string,
    readonly documentId?: string,
    readonly documentArchived = false,
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

interface HealthResponse {
  status: 'ok'
  service: string
}

interface DevelopmentSessionResponse {
  access_token: string
  token_type: 'bearer'
  workspace_id: string
  expires_at: string
}

let apiSession: DevelopmentSessionResponse | null = null

export function configureApiSession(
  accessToken: string,
  workspaceId: string,
): void {
  apiSession = {
    access_token: accessToken,
    token_type: 'bearer',
    workspace_id: workspaceId,
    expires_at: '',
  }
}

export interface IngestDocumentResponse {
  document_id: string
  version_id: string
  filename: string
  checksum: string
  chunk_count: number
  version_number: number
  status: 'ready'
}

export interface DocumentSummary {
  document_id: string
  title: string
  active_version_id: string
  active_version_number: number
  source_filename: string
  chunk_count: number
  updated_at: string
  archived_at: string | null
}

export interface DocumentVersionSummary {
  version_id: string
  version_number: number
  source_filename: string
  media_type: string
  content_checksum: string
  character_count: number
  chunk_count: number
  embedding_model: string
  embedding_dimension: number
  is_active: boolean
  created_at: string
}

export interface AnswerCitation {
  citation_id: string
  document_id: string
  document_title: string
  version_id: string
  version_number: number
  chunk_id: string
  ordinal: number
  text: string
  start_offset: number
  end_offset: number
}

export interface AnswerResponse {
  answer: string
  has_sufficient_evidence: boolean
  citations: AnswerCitation[]
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>

  let message = `Request failed (${response.status})`
  let code: string | undefined
  let documentId: string | undefined
  let documentArchived = false
  try {
    const body = (await response.json()) as ApiErrorBody
    if (typeof body.detail === 'string') message = body.detail
    if (typeof body.detail === 'object' && body.detail?.message) {
      message = body.detail.message
      code = body.detail.code
      documentId = body.detail.document_id
      documentArchived = body.detail.document_archived ?? false
    }
  } catch {
    // Keep the status-based message when the response is not JSON.
  }
  throw new ApiRequestError(message, code, documentId, documentArchived)
}

export async function checkHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return parseResponse(await fetch('/api/health', { signal }))
}

export async function createDevelopmentSession(): Promise<void> {
  if (apiSession !== null) return
  apiSession = await parseResponse(
    await fetch('/api/auth/development-session', { method: 'POST' }),
  )
}

async function authorizedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  if (apiSession === null) throw new Error('No authenticated API session')
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${apiSession.access_token}`)
  headers.set('X-Workspace-ID', apiSession.workspace_id)
  return fetch(input, { ...init, headers })
}

export async function uploadDocument(
  file: File,
  title: string,
): Promise<IngestDocumentResponse> {
  const body = new FormData()
  body.append('title', title)
  body.append('file', file)
  return parseResponse(
    await authorizedFetch('/api/documents', { method: 'POST', body }),
  )
}

export async function listDocuments(
  status: 'active' | 'archived' = 'active',
): Promise<DocumentSummary[]> {
  const url = status === 'active' ? '/api/documents' : '/api/documents?status=archived'
  return parseResponse(await authorizedFetch(url))
}

export async function archiveDocument(documentId: string): Promise<void> {
  await parseNoContent(
    await authorizedFetch(`/api/documents/${documentId}`, { method: 'DELETE' }),
  )
}

export async function restoreDocument(documentId: string): Promise<void> {
  await parseNoContent(
    await authorizedFetch(`/api/documents/${documentId}/restore`, {
      method: 'POST',
    }),
  )
}

export async function uploadDocumentVersion(
  documentId: string,
  file: File,
): Promise<IngestDocumentResponse> {
  const body = new FormData()
  body.append('file', file)
  return parseResponse(
    await authorizedFetch(`/api/documents/${documentId}/versions`, {
      method: 'POST',
      body,
    }),
  )
}

export async function listDocumentVersions(
  documentId: string,
): Promise<DocumentVersionSummary[]> {
  return parseResponse(
    await authorizedFetch(`/api/documents/${documentId}/versions`),
  )
}

export async function activateDocumentVersion(
  documentId: string,
  versionId: string,
): Promise<void> {
  await parseNoContent(
    await authorizedFetch(
      `/api/documents/${documentId}/versions/${versionId}/activate`,
      { method: 'POST' },
    ),
  )
}

export async function answerQuestion(question: string): Promise<AnswerResponse> {
  return parseResponse(
    await authorizedFetch('/api/answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, limit: 5 }),
    }),
  )
}

async function parseNoContent(response: Response): Promise<void> {
  if (response.ok) return
  await parseResponse(response)
}
