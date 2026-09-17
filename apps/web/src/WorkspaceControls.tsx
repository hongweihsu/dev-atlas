import { FormEvent, useState } from 'react'

import {
  SessionResponse,
  WorkspaceInvitationSummary,
  WorkspaceMember,
  listWorkspaceInvitations,
  listWorkspaceMembers,
  removeWorkspaceMember,
  revokeWorkspaceInvitation,
  updateWorkspaceMemberRole,
} from './api'

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
  const [action, setAction] = useState<'create' | 'invite' | 'manage' | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'editor' | 'viewer'>('viewer')
  const [inviteLink, setInviteLink] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [invitations, setInvitations] = useState<WorkspaceInvitationSummary[]>([])

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

  async function openManagement() {
    if (action === 'manage') {
      setAction(null)
      return
    }
    setAction('manage')
    setSubmitting(true)
    setError('')
    try {
      const [loadedMembers, loadedInvitations] = await Promise.all([
        listWorkspaceMembers(session.workspace_id),
        listWorkspaceInvitations(session.workspace_id),
      ])
      setMembers(loadedMembers)
      setInvitations(loadedInvitations)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Member list failed')
    } finally {
      setSubmitting(false)
    }
  }

  async function changeRole(member: WorkspaceMember, role: 'editor' | 'viewer') {
    setError('')
    try {
      const updated = await updateWorkspaceMemberRole(
        session.workspace_id,
        member.user_id,
        role,
      )
      setMembers((current) =>
        current.map((item) => item.user_id === updated.user_id ? updated : item),
      )
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Role update failed')
    }
  }

  async function removeMember(member: WorkspaceMember) {
    const identity = member.email ?? member.display_name ?? member.user_id
    if (!window.confirm(`Remove ${identity} from this workspace?`)) return
    setError('')
    try {
      await removeWorkspaceMember(session.workspace_id, member.user_id)
      setMembers((current) => current.filter((item) => item.user_id !== member.user_id))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Member removal failed')
    }
  }

  async function revokeInvitation(invitation: WorkspaceInvitationSummary) {
    setError('')
    try {
      await revokeWorkspaceInvitation(
        session.workspace_id,
        invitation.invitation_id,
      )
      setInvitations((current) =>
        current.filter((item) => item.invitation_id !== invitation.invitation_id),
      )
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Invitation revocation failed')
    }
  }

  return (
    <div className="workspace-controls">
      <div className="workspace-controls__summary">
        <select
          aria-label="Current workspace"
          value={session.workspace_id}
          onChange={(event) => {
            setAction(null)
            void onSwitch(event.target.value)
          }}
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
          <>
            <button type="button" onClick={() => setAction(action === 'invite' ? null : 'invite')}>
              Invite
            </button>
            <button type="button" onClick={() => void openManagement()}>
              Members
            </button>
          </>
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

      {action === 'manage' && (
        <section className="workspace-members" aria-label="Workspace members">
          <div className="workspace-members__heading">
            <strong>Members</strong>
            <span>{members.length}</span>
          </div>
          {submitting && <p>Loading membership…</p>}
          {!submitting && members.map((member) => (
            <div className="workspace-members__row" key={member.user_id}>
              <div>
                <strong>{member.display_name ?? member.email ?? 'Workspace member'}</strong>
                {member.display_name && member.email && <span>{member.email}</span>}
              </div>
              {member.role === 'owner' ? (
                <span className="workspace-members__role">Owner</span>
              ) : (
                <>
                  <select
                    aria-label={`Role for ${member.email ?? member.user_id}`}
                    value={member.role}
                    onChange={(event) => void changeRole(
                      member,
                      event.target.value as 'editor' | 'viewer',
                    )}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="editor">Editor</option>
                  </select>
                  <button type="button" onClick={() => void removeMember(member)}>Remove</button>
                </>
              )}
            </div>
          ))}

          <div className="workspace-members__heading workspace-members__heading--invitations">
            <strong>Invitations</strong>
            <span>{invitations.length}</span>
          </div>
          {!submitting && invitations.length === 0 && <p>No invitations yet.</p>}
          {!submitting && invitations.map((invitation) => (
            <div className="workspace-members__row" key={invitation.invitation_id}>
              <div>
                <strong>{invitation.email}</strong>
                <span>{invitation.role} · {invitation.status}</span>
              </div>
              {invitation.status === 'pending' && (
                <button type="button" onClick={() => void revokeInvitation(invitation)}>
                  Revoke
                </button>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  )
}
