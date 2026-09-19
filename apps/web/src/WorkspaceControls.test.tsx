import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { WorkspaceControls } from './WorkspaceControls'
import { SessionResponse, configureApiSession } from './api'

const session: SessionResponse = {
  user_id: 'owner-id',
  workspace_id: 'workspace-id',
  workspace_name: 'Engineering',
  role: 'owner',
}

function jsonResponse(body: object) {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => configureApiSession('token', session.workspace_id, session))
afterEach(() => vi.restoreAllMocks())

test('owner manages member roles and revokes pending invitations', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(
    async (input, init) => {
      if (input === '/api/workspaces/workspace-id/members' && !init?.method) {
        return jsonResponse([
          {
            user_id: 'owner-id',
            email: 'owner@example.com',
            display_name: 'Owner',
            role: 'owner',
            joined_at: '2026-09-18T00:00:00Z',
          },
          {
            user_id: 'reader-id',
            email: 'reader@example.com',
            display_name: null,
            role: 'viewer',
            joined_at: '2026-09-18T00:01:00Z',
          },
        ])
      }
      if (input === '/api/workspaces/workspace-id/invitations' && !init?.method) {
        return jsonResponse([
          {
            invitation_id: 'invitation-id',
            email: 'pending@example.com',
            role: 'viewer',
            status: 'pending',
            expires_at: '2026-09-25T00:00:00Z',
            accepted_at: null,
            created_at: '2026-09-18T00:00:00Z',
          },
        ])
      }
      if (
        input === '/api/workspaces/workspace-id/members/reader-id' &&
        init?.method === 'PATCH'
      ) {
        return jsonResponse({
          user_id: 'reader-id',
          email: 'reader@example.com',
          display_name: null,
          role: 'editor',
          joined_at: '2026-09-18T00:01:00Z',
        })
      }
      if (
        input === '/api/workspaces/workspace-id/invitations/invitation-id' &&
        init?.method === 'DELETE'
      ) {
        return new Response(null, { status: 204 })
      }
      if (
        input === '/api/workspaces/workspace-id/ownership' &&
        init?.method === 'POST'
      ) {
        return jsonResponse({ ...session, role: 'editor' })
      }
      throw new Error(`Unexpected request: ${String(input)}`)
    },
  )

  const onOwnershipTransferred = vi.fn()
  vi.spyOn(window, 'confirm').mockReturnValue(true)

  render(
    <WorkspaceControls
      session={session}
      workspaces={[session]}
      onSwitch={vi.fn()}
      onCreate={vi.fn()}
      onInvite={vi.fn()}
      onOwnershipTransferred={onOwnershipTransferred}
      onLeave={vi.fn()}
      onDelete={vi.fn()}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Members' }))
  expect(await screen.findByText('reader@example.com')).toBeInTheDocument()
  expect(screen.getByText('pending@example.com')).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Role for reader@example.com'), {
    target: { value: 'editor' },
  })
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/workspaces/workspace-id/members/reader-id',
      expect.objectContaining({ method: 'PATCH' }),
    ),
  )
  expect(screen.getByLabelText('Role for reader@example.com')).toHaveValue('editor')

  fireEvent.click(screen.getByRole('button', { name: 'Revoke' }))
  await waitFor(() =>
    expect(screen.queryByText('pending@example.com')).not.toBeInTheDocument(),
  )

  fireEvent.click(screen.getByRole('button', { name: 'Transfer ownership' }))
  await waitFor(() => expect(onOwnershipTransferred).toHaveBeenCalledWith({
    ...session,
    role: 'editor',
  }))
})
