import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import App from './App'
import { configureApiSession } from './api'

afterEach(() => vi.restoreAllMocks())
beforeEach(() =>
  configureApiSession('test-access-token', 'test-workspace-id', {
    user_id: 'test-user-id',
    workspace_id: 'test-workspace-id',
    workspace_name: 'Engineering Notes',
    role: 'owner',
  }),
)

function jsonResponse(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function documentSummary(versionNumber = 1, filename = 'notes.txt') {
  return {
    document_id: 'document-id',
    title: 'Architecture notes',
    active_version_id: `version-${versionNumber}-id`,
    active_version_number: versionNumber,
    source_filename: filename,
    chunk_count: versionNumber,
    updated_at: '2026-09-09T00:00:00Z',
    archived_at: null,
    knowledge_base_id: 'general-id',
    knowledge_base_name: 'General',
  }
}

const knowledgeBases = [
  { id: 'general-id', name: 'General', is_default: true, document_count: 1 },
]

function isKnowledgeBaseListRequest(input: RequestInfo | URL, init?: RequestInit) {
  return input === '/api/knowledge-bases' && init?.method !== 'POST'
}

function versionSummary(versionNumber: number, isActive: boolean) {
  return {
    version_id: `version-${versionNumber}-id`,
    version_number: versionNumber,
    source_filename: versionNumber === 1 ? 'notes.txt' : 'notes-v2.txt',
    media_type: 'text/plain',
    content_checksum: `checksum-${versionNumber}`,
    character_count: 10,
    chunk_count: versionNumber,
    embedding_model: 'text-embedding-3-small',
    embedding_dimension: 1536,
    is_active: isActive,
    created_at: `2026-09-0${versionNumber}T00:00:00Z`,
  }
}

function isDocumentListRequest(input: RequestInfo | URL, init?: RequestInit) {
  return input === '/api/documents' && init?.method !== 'POST'
}

test('shows the product identity and hides healthy API status', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input)) return jsonResponse(knowledgeBases)
    return jsonResponse([])
  })

  render(<App />)

  expect(
    screen.getByRole('heading', { name: /Ask your documents/i }),
  ).toBeInTheDocument()
  expect(screen.getByText('Grounded technical research')).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByText('Connecting…')).not.toBeInTheDocument())
  expect(screen.queryByText('API connected')).not.toBeInTheDocument()
  expect(screen.getByText('Engineering Notes')).toBeInTheDocument()
  expect(screen.getByText('owner')).toBeInTheDocument()
})

test('shows viewer access as read-only while keeping research available', async () => {
  configureApiSession('viewer-token', 'test-workspace-id', {
    user_id: 'viewer-id',
    workspace_id: 'test-workspace-id',
    workspace_name: 'Shared Research',
    role: 'viewer',
  })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input)) return jsonResponse(knowledgeBases)
    return jsonResponse([documentSummary()])
  })

  render(<App />)

  expect(await screen.findByText('Viewer access is read-only.', { exact: false }))
    .toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Archive Architecture notes' }))
    .toBeDisabled()
  expect(screen.getByRole('tab', { name: 'Add document' })).toBeDisabled()
  expect(screen.getByRole('textbox', { name: 'Question' })).toBeEnabled()
})

test('shows an unavailable banner and retries the health check', async () => {
  const fetchMock = vi
    .spyOn(globalThis, 'fetch')
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce(jsonResponse({ status: 'ok', service: 'devatlas-api' }))
    .mockResolvedValueOnce(jsonResponse([]))

  render(<App />)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Service temporarily unavailable',
  )
  fireEvent.click(screen.getByRole('button', { name: 'Retry connection' }))

  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  expect(fetchMock).toHaveBeenCalledTimes(3)
})

test('uploads a dropped text document without a custom title', async () => {
  let created = false
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input, init)) return jsonResponse(knowledgeBases)
    if (isDocumentListRequest(input, init)) {
      return jsonResponse(created ? [documentSummary()] : [])
    }
    created = true
    return jsonResponse(
      {
        document_id: 'document-id',
        version_id: 'version-id',
        filename: 'notes.txt',
        checksum: 'checksum',
        chunk_count: 2,
        version_number: 1,
        status: 'ready',
      },
      201,
    )
  })
  render(<App />)
  await waitFor(() => expect(screen.queryByText('Connecting…')).not.toBeInTheDocument())

  const droppedFile = new File(['source'], 'notes.txt', { type: 'text/plain' })
  fireEvent.drop(screen.getByText('Choose a .txt file').closest('label')!, {
    dataTransfer: { files: [droppedFile] },
  })
  const uploadButton = screen.getByRole('button', { name: 'Index document' })
  const uploadForm = uploadButton.closest('form')
  expect(uploadForm).not.toBeNull()
  fireEvent.submit(uploadForm!)

  expect(await screen.findByText('2 chunk indexed and ready')).toBeInTheDocument()
  expect(screen.getByText('Choose a .txt file')).toBeInTheDocument()
  expect(screen.getByLabelText(/Plain-text file/)).toHaveValue('')
  const uploadCall = fetchMock.mock.calls.find(
    ([input, init]) => input === '/api/documents' && init?.method === 'POST',
  )
  expect(uploadCall?.[1]?.method).toBe('POST')
  expect(uploadCall?.[1]?.body).toBeInstanceOf(FormData)
  expect((uploadCall?.[1]?.body as FormData).get('title')).toBe('')
})

test('uploads a new version for the document that was just indexed', async () => {
  let activeVersion = 0
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input, init)) return jsonResponse(knowledgeBases)
    if (isDocumentListRequest(input, init)) {
      return jsonResponse(
        activeVersion === 0
          ? []
          : [documentSummary(activeVersion, activeVersion === 1 ? 'notes.txt' : 'notes-v2.txt')],
      )
    }
    if (input === '/api/documents' && init?.method === 'POST') {
      activeVersion = 1
      return jsonResponse(
        {
          document_id: 'document-id',
          version_id: 'version-1-id',
          filename: 'notes.txt',
          checksum: 'first-checksum',
          chunk_count: 1,
          version_number: 1,
          status: 'ready',
        },
        201,
      )
    }
    if (
      input === '/api/documents/document-id/versions' &&
      init?.method !== 'POST'
    ) {
      return jsonResponse(
        activeVersion === 1
          ? [versionSummary(1, true)]
          : [versionSummary(2, true), versionSummary(1, false)],
      )
    }
    activeVersion = 2
    return jsonResponse(
      {
        document_id: 'document-id',
        version_id: 'version-2-id',
        filename: 'notes-v2.txt',
        checksum: 'second-checksum',
        chunk_count: 2,
        version_number: 2,
        status: 'ready',
      },
      201,
    )
  })
  render(<App />)
  await waitFor(() => expect(screen.queryByText('Connecting…')).not.toBeInTheDocument())

  fireEvent.change(screen.getByLabelText(/Display title/), {
    target: { value: 'Architecture notes' },
  })
  fireEvent.change(screen.getByLabelText(/Plain-text file/), {
    target: { files: [new File(['first'], 'notes.txt', { type: 'text/plain' })] },
  })
  const createButton = screen.getByRole('button', { name: 'Index document' })
  fireEvent.submit(createButton.closest('form')!)
  expect(await screen.findByText('Version 1: notes.txt')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('tab', { name: 'Update document' }))

  fireEvent.change(screen.getByLabelText(/New version file/), {
    target: {
      files: [new File(['second'], 'notes-v2.txt', { type: 'text/plain' })],
    },
  })
  const versionButton = screen.getByRole('button', { name: 'Upload Version 2' })
  fireEvent.submit(versionButton.closest('form')!)

  expect(await screen.findByText('Version 2: notes-v2.txt')).toBeInTheDocument()
  const versionCall = fetchMock.mock.calls.find(
    ([input, init]) =>
      input === '/api/documents/document-id/versions' && init?.method === 'POST',
  )
  expect(versionCall?.[1]?.method).toBe('POST')
  expect(versionCall?.[1]?.body).toBeInstanceOf(FormData)
})

test('shows immutable history and makes an older version current', async () => {
  let activeVersion = 2
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(
    async (input, init) => {
      if (input === '/api/health') {
        return jsonResponse({ status: 'ok', service: 'devatlas-api' })
      }
      if (isKnowledgeBaseListRequest(input, init)) return jsonResponse(knowledgeBases)
      if (isDocumentListRequest(input, init)) {
        return jsonResponse([documentSummary(activeVersion)])
      }
      if (input === '/api/documents/document-id/versions') {
        return jsonResponse([
          versionSummary(2, activeVersion === 2),
          versionSummary(1, activeVersion === 1),
        ])
      }
      if (
        input ===
          '/api/documents/document-id/versions/version-1-id/activate' &&
        init?.method === 'POST'
      ) {
        activeVersion = 1
        return new Response(null, { status: 204 })
      }
      return jsonResponse({}, 404)
    },
  )

  render(<App />)
  await screen.findByText('Architecture notes')
  fireEvent.click(screen.getByRole('tab', { name: 'Update document' }))

  expect(await screen.findByText('Version history')).toBeInTheDocument()
  fireEvent.click(await screen.findByRole('button', { name: 'Make current' }))

  await waitFor(() =>
    expect(
      fetchMock,
    ).toHaveBeenCalledWith(
      '/api/documents/document-id/versions/version-1-id/activate',
      expect.objectContaining({ method: 'POST', headers: expect.any(Headers) }),
    ),
  )
  await waitFor(() =>
    expect(screen.getAllByText('Current')).toHaveLength(1),
  )
  expect(screen.getByRole('button', { name: 'Upload Version 3' })).toBeDisabled()
})

test('shows a duplicate-content error when a version is rejected', async () => {
  let created = false
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input, init)) return jsonResponse(knowledgeBases)
    if (isDocumentListRequest(input, init)) {
      return jsonResponse(created ? [documentSummary()] : [])
    }
    if (input === '/api/documents' && init?.method === 'POST') {
      created = true
      return jsonResponse(
        {
          document_id: 'document-id',
          version_id: 'version-1-id',
          filename: 'notes.txt',
          checksum: 'checksum',
          chunk_count: 1,
          version_number: 1,
          status: 'ready',
        },
        201,
      )
    }
    return jsonResponse(
      {
        detail: {
          code: 'duplicate_document_content',
          message: 'this document already has a version with the same content',
        },
      },
      409,
    )
  })
  render(<App />)
  await waitFor(() => expect(screen.queryByText('Connecting…')).not.toBeInTheDocument())

  fireEvent.change(screen.getByLabelText(/Display title/), {
    target: { value: 'Architecture notes' },
  })
  fireEvent.change(screen.getByLabelText(/Plain-text file/), {
    target: { files: [new File(['same'], 'notes.txt', { type: 'text/plain' })] },
  })
  const createButton = screen.getByRole('button', { name: 'Index document' })
  fireEvent.submit(createButton.closest('form')!)
  await screen.findByText('Version 1: notes.txt')

  fireEvent.click(screen.getByRole('tab', { name: 'Update document' }))

  fireEvent.change(screen.getByLabelText(/New version file/), {
    target: { files: [new File(['same'], 'notes-again.txt', { type: 'text/plain' })] },
  })
  const versionButton = screen.getByRole('button', { name: 'Upload Version 2' })
  fireEvent.submit(versionButton.closest('form')!)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'this document already has a version with the same content',
  )
  expect(screen.getByText('Version 1: notes.txt')).toBeInTheDocument()
})

test('asks a question and renders expandable citation provenance', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input, init)) return jsonResponse(knowledgeBases)
    if (isDocumentListRequest(input, init)) return jsonResponse([])
    return jsonResponse({
      answer: 'Offsets connect the chunk to normalized source text.',
      has_sufficient_evidence: true,
      citations: [
        {
          citation_id: 'S1',
          document_id: 'document-id',
          document_title: 'Architecture notes',
          version_id: 'version-id',
          version_number: 1,
          chunk_id: 'chunk-id',
          ordinal: 0,
          text: 'Each chunk keeps source offsets.',
          start_offset: 10,
          end_offset: 42,
        },
      ],
    })
  })
  render(<App />)
  await waitFor(() => expect(screen.queryByText('Connecting…')).not.toBeInTheDocument())

  fireEvent.change(screen.getByLabelText('Question'), {
    target: { value: 'How is evidence traced?' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Generate answer' }))

  expect(
    await screen.findByText('Offsets connect the chunk to normalized source text.'),
  ).toBeInTheDocument()
  expect(screen.getByText('Evidence grounded')).toBeInTheDocument()
  expect(screen.getByText('Architecture notes')).toBeInTheDocument()
  expect(screen.getByText('Characters 10–42')).toBeInTheDocument()
  const answerCall = fetchMock.mock.calls.find(([input]) => input === '/api/answers')
  expect(JSON.parse(String(answerCall?.[1]?.body))).toMatchObject({
    knowledge_base_ids: ['general-id'],
  })
})

test('shows the API error message without discarding the question', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input, init)) return jsonResponse(knowledgeBases)
    if (isDocumentListRequest(input, init)) return jsonResponse([])
    return jsonResponse({ detail: { message: 'answer provider request failed' } }, 503)
  })
  render(<App />)
  await waitFor(() => expect(screen.queryByText('Connecting…')).not.toBeInTheDocument())

  const question = screen.getByLabelText('Question')
  fireEvent.change(question, { target: { value: 'What happened?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate answer' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'answer provider request failed',
  )
  expect(question).toHaveValue('What happened?')
})

test('loads existing documents and lets the user select one for an update', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input)) return jsonResponse(knowledgeBases)
    return jsonResponse([
      {
        ...documentSummary(3, 'database-v3.txt'),
        document_id: 'database-document-id',
        title: 'Database notes',
      },
      documentSummary(),
    ])
  })

  render(<App />)

  expect(
    await screen.findByRole('button', { name: /Select Architecture notes/i }),
  ).toBeInTheDocument()
  fireEvent.click(
    screen.getByRole('button', { name: /Select Architecture notes/i }),
  )
  expect(screen.getByText('Selected document').nextSibling).toHaveTextContent(
    'Architecture notes',
  )
  expect(screen.getByRole('button', { name: 'Upload Version 2' })).toBeDisabled()

  fireEvent.change(screen.getByLabelText('Sort'), { target: { value: 'name' } })
  const documentButtons = screen.getAllByRole('button', {
    name: /Select (Architecture notes|Database notes)/i,
  })
  expect(documentButtons[0]).toHaveAccessibleName(/Architecture notes/i)
})

test('archives a document and restores it with undo', async () => {
  let archived = false
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(
    async (input, init) => {
      if (input === '/api/health') {
        return jsonResponse({ status: 'ok', service: 'devatlas-api' })
      }
      if (isKnowledgeBaseListRequest(input, init)) return jsonResponse(knowledgeBases)
      if (input === '/api/documents/document-id' && init?.method === 'DELETE') {
        archived = true
        return new Response(null, { status: 204 })
      }
      if (
        input === '/api/documents/document-id/restore' &&
        init?.method === 'POST'
      ) {
        archived = false
        return new Response(null, { status: 204 })
      }
      if (isDocumentListRequest(input, init)) {
        return jsonResponse(archived ? [] : [documentSummary()])
      }
      throw new Error(`Unexpected request: ${String(input)}`)
    },
  )

  render(<App />)
  fireEvent.click(
    await screen.findByRole('button', { name: 'Archive Architecture notes' }),
  )

  expect(
    await screen.findByText(/archived and removed from search/i),
  ).toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: 'Archive Architecture notes' }),
  ).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Undo' }))

  expect(
    await screen.findByRole('button', { name: 'Archive Architecture notes' }),
  ).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/documents/document-id/restore',
    expect.objectContaining({ method: 'POST', headers: expect.any(Headers) }),
  )
})

test('loads archived documents after a page-state change and restores one', async () => {
  let restored = false
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input, init)) return jsonResponse(knowledgeBases)
    if (input === '/api/documents') return jsonResponse([])
    if (input === '/api/documents?status=archived') {
      return jsonResponse(
        restored
          ? []
          : [
              {
                ...documentSummary(),
                archived_at: '2026-09-12T00:00:00Z',
              },
            ],
      )
    }
    if (
      input === '/api/documents/document-id/restore' &&
      init?.method === 'POST'
    ) {
      restored = true
      return new Response(null, { status: 204 })
    }
    throw new Error(`Unexpected request: ${String(input)}`)
  })

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Archived' }))
  fireEvent.click(
    await screen.findByRole('button', { name: 'Restore Architecture notes' }),
  )

  await waitFor(() =>
    expect(
      screen.queryByRole('button', { name: 'Restore Architecture notes' }),
    ).not.toBeInTheDocument(),
  )
})

test('selects the existing document when a new upload duplicates its content', async () => {
  let duplicateRejected = false
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    if (isKnowledgeBaseListRequest(input, init)) return jsonResponse(knowledgeBases)
    if (isDocumentListRequest(input, init)) {
      return jsonResponse(duplicateRejected ? [documentSummary()] : [])
    }
    duplicateRejected = true
    return jsonResponse(
      {
        detail: {
          code: 'duplicate_document_content',
          message: 'this content is already indexed',
          document_id: 'document-id',
        },
      },
      409,
    )
  })

  render(<App />)
  await waitFor(() => expect(screen.queryByText('Connecting…')).not.toBeInTheDocument())
  fireEvent.change(screen.getByLabelText(/Display title/), {
    target: { value: 'A duplicate title' },
  })
  fireEvent.change(screen.getByLabelText(/Plain-text file/), {
    target: { files: [new File(['same'], 'duplicate.txt', { type: 'text/plain' })] },
  })
  const uploadButton = screen.getByRole('button', { name: 'Index document' })
  fireEvent.submit(uploadButton.closest('form')!)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'this content is already indexed',
  )
  fireEvent.click(screen.getByRole('tab', { name: 'Update document' }))
  expect(screen.getByText('Selected document').nextSibling).toHaveTextContent(
    'Architecture notes',
  )
})
