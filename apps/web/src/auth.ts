import { UserManager, WebStorageStateStore } from 'oidc-client-ts'

import { bootstrapSession } from './api'

const authority = import.meta.env.VITE_COGNITO_AUTHORITY as string | undefined
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined
const cognitoDomain = import.meta.env.VITE_COGNITO_DOMAIN as string | undefined

export const usesHostedAuthentication = Boolean(
  authority && clientId && cognitoDomain,
)

const userManager = usesHostedAuthentication
  ? new UserManager({
      authority: authority!,
      client_id: clientId!,
      redirect_uri: `${window.location.origin}/auth/callback`,
      post_logout_redirect_uri: `${window.location.origin}/`,
      response_type: 'code',
      scope: 'openid email profile',
      userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    })
  : null

export async function restoreHostedSession(): Promise<boolean> {
  if (!userManager) return false

  if (window.location.pathname === '/auth/callback') {
    await userManager.signinRedirectCallback()
    window.history.replaceState({}, document.title, '/')
  }

  const user = await userManager.getUser()
  if (!user || user.expired || !user.access_token) return false
  await bootstrapSession(user.access_token)
  return true
}

export async function signIn(): Promise<void> {
  if (!userManager) throw new Error('Hosted authentication is not configured')
  await userManager.signinRedirect()
}

export async function signOut(): Promise<void> {
  if (!userManager || !cognitoDomain || !clientId) return
  await userManager.removeUser()
  const parameters = new URLSearchParams({
    client_id: clientId,
    logout_uri: `${window.location.origin}/`,
  })
  window.location.assign(`${cognitoDomain}/logout?${parameters}`)
}
