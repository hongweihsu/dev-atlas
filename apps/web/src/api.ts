interface ApiErrorBody {
  detail?: string | { message?: string }
}

interface HealthResponse {
  status: 'ok'
  service: string
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
  try {
    const body = (await response.json()) as ApiErrorBody
    if (typeof body.detail === 'string') message = body.detail
    if (typeof body.detail === 'object' && body.detail?.message) {
      message = body.detail.message
    }
  } catch {
    // Keep the status-based message when the response is not JSON.
  }
  throw new Error(message)
}

export async function checkHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return parseResponse(await fetch('/api/health', { signal }))
}

export async function uploadDocument(
  file: File,
  title: string,
): Promise<IngestDocumentResponse> {
  const body = new FormData()
  body.append('title', title)
  body.append('file', file)
  return parseResponse(await fetch('/api/documents', { method: 'POST', body }))
}

export async function uploadDocumentVersion(
  documentId: string,
  file: File,
): Promise<IngestDocumentResponse> {
  const body = new FormData()
  body.append('file', file)
  return parseResponse(
    await fetch(`/api/documents/${documentId}/versions`, {
      method: 'POST',
      body,
    }),
  )
}

export async function answerQuestion(question: string): Promise<AnswerResponse> {
  return parseResponse(
    await fetch('/api/answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, limit: 5 }),
    }),
  )
}
