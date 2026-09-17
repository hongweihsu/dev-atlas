import { FormEvent, useState } from 'react'

import {
  authenticationErrorMessage,
  completePasswordReset,
  confirmRegistration,
  registerUser,
  requestPasswordReset,
  resendRegistrationCode,
  signInWithPassword,
} from './auth'

type AuthView = 'sign-in' | 'sign-up' | 'confirm' | 'forgot' | 'reset'

export function AuthPanel({ onAuthenticated }: { onAuthenticated: () => Promise<void> }) {
  const [view, setView] = useState<AuthView>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setMessage('')
    try {
      if (view === 'sign-in') {
        await signInWithPassword(email.trim(), password)
        await onAuthenticated()
      } else if (view === 'sign-up') {
        await registerUser(email.trim(), password)
        setView('confirm')
        setPassword('')
        setMessage('Check your email for a verification code.')
      } else if (view === 'confirm') {
        await confirmRegistration(email.trim(), confirmation.trim())
        setView('sign-in')
        setConfirmation('')
        setMessage('Email confirmed. You can now sign in.')
      } else if (view === 'forgot') {
        await requestPasswordReset(email.trim())
        setView('reset')
        setMessage('Check your email for a password reset code.')
      } else {
        await completePasswordReset(email.trim(), confirmation.trim(), password)
        setView('sign-in')
        setConfirmation('')
        setPassword('')
        setMessage('Password updated. You can now sign in.')
      }
    } catch (caught) {
      setError(authenticationErrorMessage(caught))
    } finally {
      setSubmitting(false)
    }
  }

  function show(next: AuthView) {
    setView(next)
    setError('')
    setMessage('')
    setConfirmation('')
    setPassword('')
  }

  const needsPassword = view === 'sign-in' || view === 'sign-up' || view === 'reset'
  const needsCode = view === 'confirm' || view === 'reset'
  const title = {
    'sign-in': 'Welcome back',
    'sign-up': 'Create your workspace',
    confirm: 'Confirm your email',
    forgot: 'Reset your password',
    reset: 'Choose a new password',
  }[view]

  return (
    <section className="auth-card" aria-labelledby="auth-title">
      <p className="eyebrow">Private knowledge workspace</p>
      <h2 id="auth-title">{title}</h2>
      <p className="auth-card__intro">
        {view === 'sign-up'
          ? 'Your verified account receives an isolated Personal Workspace.'
          : 'Sign in to search, trace, and manage your own documents.'}
      </p>
      <form className="auth-form" onSubmit={submit}>
        <label>
          Email
          <input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        {needsCode && <label>Verification code<input type="text" inputMode="numeric" autoComplete="one-time-code" required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label>}
        {needsPassword && <label>{view === 'reset' ? 'New password' : 'Password'}<input type="password" autoComplete={view === 'sign-in' ? 'current-password' : 'new-password'} minLength={12} required value={password} onChange={(event) => setPassword(event.target.value)} /></label>}
        {message && <p className="auth-message auth-message--success">{message}</p>}
        {error && <p className="auth-message auth-message--error" role="alert">{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? 'Please wait…' : title}</button>
      </form>
      <div className="auth-actions">
        {view === 'sign-in' && <><button type="button" onClick={() => show('sign-up')}>Create account</button><button type="button" onClick={() => show('forgot')}>Forgot password?</button></>}
        {view === 'confirm' && <button type="button" onClick={() => void resendRegistrationCode(email.trim()).then(() => setMessage('A new code was sent.')).catch((caught) => setError(authenticationErrorMessage(caught)))}>Resend code</button>}
        {view !== 'sign-in' && <button type="button" onClick={() => show('sign-in')}>Back to sign in</button>}
      </div>
    </section>
  )
}
