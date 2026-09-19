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
let resolvedSession: SessionResponse | null = null

export interface SessionResponse {
  user_id: string
  workspace_id: string
  workspace_name: string
  role: 'owner' | 'editor' | 'viewer'
}

export interface WorkspaceInvitationResponse {
  invitation_id: string
  token: string
  workspace_name: string
  email: string
  role: 'editor' | 'viewer'
}

export interface WorkspaceMember {
  user_id: string
  email: string | null
  display_name: string | null
  role: 'owner' | 'editor' | 'viewer'
  joined_at: string
}

export interface WorkspaceInvitationSummary {
  invitation_id: string
  email: string
  role: 'editor' | 'viewer'
  status: 'pending' | 'accepted' | 'expired'
  expires_at: string
  accepted_at: string | null
  created_at: string
}

export function configureApiSession(
  accessToken: string,
  workspaceId: string,
  session: SessionResponse | null = null,
): void {
  apiSession = {
    access_token: accessToken,
    token_type: 'bearer',
    workspace_id: workspaceId,
    expires_at: '',
  }
  resolvedSession = session
}

export function selectWorkspace(workspace: SessionResponse): void {
  if (apiSession === null) throw new Error('No authenticated API session')
  apiSession.workspace_id = workspace.workspace_id
  resolvedSession = workspace
}

export async function bootstrapSession(
  accessToken: string,
  identityToken: string,
): Promise<SessionResponse> {
  const response = await parseResponse<SessionResponse>(
    await fetch('/api/session/bootstrap', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'X-Identity-Token': identityToken,
      },
    }),
  )
  configureApiSession(accessToken, response.workspace_id, response)
  return response
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
  knowledge_base_id: string
  knowledge_base_name: string
}

export interface KnowledgeBaseSummary {
  id: string
  name: string
  is_default: boolean
  document_count: number
}

export interface IngestionJob {
  id: string
  status: 'queued' | 'processing' | 'succeeded' | 'failed'
  attempt_count: number
  document_id: string | null
  version_id: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
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
  page_start: number | null
  page_end: number | null
}

export interface AnswerResponse {
  answer: string
  has_sufficient_evidence: boolean
  citations: AnswerCitation[]
}

export interface ConversationSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ConversationTurn extends AnswerResponse {
  id: string
  conversation_id: string
  ordinal: number
  question: string
  standalone_question: string
  created_at: string
}

export interface WorkspaceQuestionResponse {
  answer: string
  tools: { name: string }[]
}

export interface ResearchResponse extends AnswerResponse {
  stop_reason: 'completed' | 'tool_budget_reached'
  steps: {
    ordinal: number
    tool_name: string
    summary: string
  }[]
}

export interface CorrectiveAnswerResponse extends AnswerResponse {
  correction_applied: boolean
  corrective_query: string | null
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

export async function getSession(): Promise<SessionResponse> {
  if (resolvedSession !== null) return resolvedSession
  const session = await parseResponse<SessionResponse>(
    await authorizedFetch('/api/session'),
  )
  resolvedSession = session
  return session
}

export async function listWorkspaces(): Promise<SessionResponse[]> {
  return parseResponse(await authorizedFetch('/api/workspaces'))
}

export async function createWorkspace(name: string): Promise<SessionResponse> {
  return parseResponse(
    await authorizedFetch('/api/workspaces', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  )
}

export async function createWorkspaceInvitation(
  workspaceId: string,
  email: string,
  role: 'editor' | 'viewer',
): Promise<WorkspaceInvitationResponse> {
  return parseResponse(
    await authorizedFetch(`/api/workspaces/${workspaceId}/invitations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, role }),
    }),
  )
}

export async function acceptWorkspaceInvitation(token: string): Promise<SessionResponse> {
  return parseResponse(
    await authorizedFetch('/api/workspaces/invitations/accept', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    }),
  )
}

export async function listWorkspaceMembers(
  workspaceId: string,
): Promise<WorkspaceMember[]> {
  return parseResponse(
    await authorizedFetch(`/api/workspaces/${workspaceId}/members`),
  )
}

export async function updateWorkspaceMemberRole(
  workspaceId: string,
  userId: string,
  role: 'editor' | 'viewer',
): Promise<WorkspaceMember> {
  return parseResponse(
    await authorizedFetch(`/api/workspaces/${workspaceId}/members/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    }),
  )
}

export async function removeWorkspaceMember(
  workspaceId: string,
  userId: string,
): Promise<void> {
  await parseNoContent(
    await authorizedFetch(`/api/workspaces/${workspaceId}/members/${userId}`, {
      method: 'DELETE',
    }),
  )
}

export async function transferWorkspaceOwnership(
  workspaceId: string,
  newOwnerUserId: string,
): Promise<SessionResponse> {
  return parseResponse(
    await authorizedFetch(`/api/workspaces/${workspaceId}/ownership`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_owner_user_id: newOwnerUserId }),
    }),
  )
}

export async function listWorkspaceInvitations(
  workspaceId: string,
): Promise<WorkspaceInvitationSummary[]> {
  return parseResponse(
    await authorizedFetch(`/api/workspaces/${workspaceId}/invitations`),
  )
}

export async function revokeWorkspaceInvitation(
  workspaceId: string,
  invitationId: string,
): Promise<void> {
  await parseNoContent(
    await authorizedFetch(
      `/api/workspaces/${workspaceId}/invitations/${invitationId}`,
      { method: 'DELETE' },
    ),
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
  knowledgeBaseId?: string,
): Promise<IngestDocumentResponse> {
  const body = new FormData()
  body.append('title', title)
  body.append('file', file)
  if (knowledgeBaseId) body.append('knowledge_base_id', knowledgeBaseId)
  return parseResponse(
    await authorizedFetch('/api/documents', { method: 'POST', body }),
  )
}

export async function submitIngestionJob(
  file: File,
  title: string,
  knowledgeBaseId: string,
  idempotencyKey: string,
): Promise<IngestionJob> {
  const body = new FormData()
  body.append('title', title)
  body.append('knowledge_base_id', knowledgeBaseId)
  body.append('file', file)
  return parseResponse(
    await authorizedFetch('/api/ingestion-jobs', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body,
    }),
  )
}

export async function getIngestionJob(jobId: string): Promise<IngestionJob> {
  return parseResponse(await authorizedFetch(`/api/ingestion-jobs/${jobId}`))
}

export async function listDocuments(
  status: 'active' | 'archived' = 'active',
  knowledgeBaseId?: string,
): Promise<DocumentSummary[]> {
  const parameters = new URLSearchParams()
  if (status === 'archived') parameters.set('status', 'archived')
  if (knowledgeBaseId) parameters.set('knowledge_base_id', knowledgeBaseId)
  const query = parameters.toString()
  const url = `/api/documents${query ? `?${query}` : ''}`
  return parseResponse(await authorizedFetch(url))
}

export async function listKnowledgeBases(): Promise<KnowledgeBaseSummary[]> {
  return parseResponse(await authorizedFetch('/api/knowledge-bases'))
}

export async function createKnowledgeBase(
  name: string,
): Promise<KnowledgeBaseSummary> {
  return parseResponse(
    await authorizedFetch('/api/knowledge-bases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  )
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

export async function answerQuestion(
  question: string,
  knowledgeBaseIds: string[] = [],
): Promise<AnswerResponse> {
  return parseResponse(
    await authorizedFetch('/api/answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        limit: 5,
        knowledge_base_ids: knowledgeBaseIds,
      }),
    }),
  )
}

export async function createConversation(
  title: string,
): Promise<ConversationSummary> {
  return parseResponse(
    await authorizedFetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    }),
  )
}

export async function listConversations(): Promise<ConversationSummary[]> {
  return parseResponse(await authorizedFetch('/api/conversations'))
}

export async function listConversationTurns(
  conversationId: string,
): Promise<ConversationTurn[]> {
  return parseResponse(
    await authorizedFetch(`/api/conversations/${conversationId}/turns`),
  )
}

export async function askConversation(
  conversationId: string,
  question: string,
  knowledgeBaseIds: string[],
): Promise<ConversationTurn> {
  return parseResponse(
    await authorizedFetch(`/api/conversations/${conversationId}/turns`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        limit: 5,
        knowledge_base_ids: knowledgeBaseIds,
      }),
    }),
  )
}

export async function askWorkspaceQuestion(
  question: string,
): Promise<WorkspaceQuestionResponse> {
  return parseResponse(
    await authorizedFetch('/api/workspace-questions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    }),
  )
}

export async function runResearch(question: string): Promise<ResearchResponse> {
  return parseResponse(
    await authorizedFetch('/api/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    }),
  )
}

export async function askCorrectiveQuestion(
  question: string,
  knowledgeBaseIds: string[],
): Promise<CorrectiveAnswerResponse> {
  return parseResponse(
    await authorizedFetch('/api/corrective-answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        limit: 5,
        knowledge_base_ids: knowledgeBaseIds,
      }),
    }),
  )
}

async function parseNoContent(response: Response): Promise<void> {
  if (response.ok) return
  await parseResponse(response)
}
