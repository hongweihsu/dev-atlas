import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from './App'

afterEach(() => vi.restoreAllMocks())

function jsonResponse(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

test('shows the product identity and healthy API state', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    jsonResponse({ status: 'ok', service: 'devatlas-api' }),
  )

  render(<App />)

  expect(
    screen.getByRole('heading', { name: /Ask your documents/i }),
  ).toBeInTheDocument()
  expect(screen.getByText('Grounded technical research')).toBeInTheDocument()
  expect(await screen.findByText('API connected')).toBeInTheDocument()
})

test('uploads a text document and reports the indexed chunk count', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    return jsonResponse(
      {
        document_id: 'document-id',
        version_id: 'version-id',
        filename: 'notes.txt',
        checksum: 'checksum',
        chunk_count: 2,
        status: 'ready',
      },
      201,
    )
  })
  render(<App />)

  fireEvent.change(screen.getByLabelText('Document title'), {
    target: { value: 'Architecture notes' },
  })
  fireEvent.change(screen.getByLabelText(/Plain-text file/), {
    target: { files: [new File(['source'], 'notes.txt', { type: 'text/plain' })] },
  })
  const uploadButton = screen.getByRole('button', { name: 'Index document' })
  const uploadForm = uploadButton.closest('form')
  expect(uploadForm).not.toBeNull()
  fireEvent.submit(uploadForm!)

  expect(await screen.findByText('2 chunk indexed and ready')).toBeInTheDocument()
  const uploadCall = fetchMock.mock.calls.find(([input]) => input === '/api/documents')
  expect(uploadCall?.[1]?.method).toBe('POST')
  expect(uploadCall?.[1]?.body).toBeInstanceOf(FormData)
})

test('asks a question and renders expandable citation provenance', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
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
})

test('shows the API error message without discarding the question', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    if (input === '/api/health') {
      return jsonResponse({ status: 'ok', service: 'devatlas-api' })
    }
    return jsonResponse({ detail: { message: 'answer provider request failed' } }, 503)
  })
  render(<App />)

  const question = screen.getByLabelText('Question')
  fireEvent.change(question, { target: { value: 'What happened?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate answer' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'answer provider request failed',
  )
  expect(question).toHaveValue('What happened?')
})
