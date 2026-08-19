import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from './App'

afterEach(() => vi.restoreAllMocks())

test('shows the product identity and healthy API state', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ status: 'ok', service: 'devatlas-api' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )

  render(<App />)

  expect(screen.getByRole('heading', { name: 'DevAtlas' })).toBeInTheDocument()
  expect(
    screen.getByText('AI Technical Research & Knowledge Platform'),
  ).toBeInTheDocument()
  expect(await screen.findByText('API connected')).toBeInTheDocument()
})
