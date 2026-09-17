import { FormEvent, useState } from 'react'

import { SessionResponse } from './api'

interface WorkspaceControlsProps {
  session: SessionResponse
  workspaces: SessionResponse[]
  onSwitch: (workspaceId: string) => Promise<void>
  onCreate: (name: string) => Promise<void>
  onInvite: (email: string, role: 'editor' | 'viewer') => Promise<string>
}

export function WorkspaceControls({
  session,
  workspaces,
  onSwitch,
  onCreate,
  onInvite,
}: WorkspaceControlsProps) {
  const [action, setAction] = useState<'create' | 'invite' | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'editor' | 'viewer'>('viewer')
  const [inviteLink, setInviteLink] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function create(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    setError('')
    try {
      await onCreate(name.trim())
      setName('')
      setAction(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Workspace creation failed')
    } finally {
      setSubmitting(false)
    }
  }

  async function invite(event: FormEvent) {
    event.preventDefault()
    if (!email.trim()) return
    setSubmitting(true)
    setError('')
    try {
      setInviteLink(await onInvite(email.trim(), role))
      setEmail('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Invitation creation failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="workspace-controls">
      <div className="workspace-controls__summary">
        <select
          aria-label="Current workspace"
          value={session.workspace_id}
          onChange={(event) => void onSwitch(event.target.value)}
        >
          {workspaces.map((workspace) => (
            <option key={workspace.workspace_id} value={workspace.workspace_id}>
              {workspace.workspace_name}
            </option>
          ))}
        </select>
        <strong>{session.role}</strong>
        <button type="button" onClick={() => setAction(action === 'create' ? null : 'create')}>
          New workspace
        </button>
        {session.role === 'owner' && (
          <button type="button" onClick={() => setAction(action === 'invite' ? null : 'invite')}>
            Invite
          </button>
        )}
      </div>

      {action === 'create' && (
        <form className="workspace-controls__form" onSubmit={(event) => void create(event)}>
          <label>
            Workspace name
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={255} autoFocus />
          </label>
          <button type="submit" disabled={submitting || !name.trim()}>Create</button>
        </form>
      )}

      {action === 'invite' && (
        <form className="workspace-controls__form" onSubmit={(event) => void invite(event)}>
          <label>
            Member email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoFocus />
          </label>
          <label>
            Role
            <select value={role} onChange={(event) => setRole(event.target.value as 'editor' | 'viewer')}>
              <option value="viewer">Viewer</option>
              <option value="editor">Editor</option>
            </select>
          </label>
          <button type="submit" disabled={submitting || !email.trim()}>Create link</button>
        </form>
      )}

      {error && <p className="workspace-controls__error" role="alert">{error}</p>}
      {inviteLink && action === 'invite' && (
        <div className="workspace-controls__link">
          <input aria-label="Invitation link" value={inviteLink} readOnly />
          <button type="button" onClick={() => void navigator.clipboard.writeText(inviteLink)}>Copy</button>
        </div>
      )}
    </div>
  )
}
