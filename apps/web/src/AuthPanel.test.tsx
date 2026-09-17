import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { AuthPanel } from './AuthPanel'
import { confirmRegistration, registerUser, signInWithPassword } from './auth'

vi.mock('./auth', () => ({
  authenticationErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : 'Authentication failed',
  completePasswordReset: vi.fn(),
  confirmRegistration: vi.fn(),
  registerUser: vi.fn(),
  requestPasswordReset: vi.fn(),
  resendRegistrationCode: vi.fn(),
  signInWithPassword: vi.fn(),
}))

test('signs in and hands control back to the workspace', async () => {
  const onAuthenticated = vi.fn()
  render(<AuthPanel onAuthenticated={onAuthenticated} />)

  fireEvent.change(screen.getByLabelText('Email'), {
    target: { value: 'reader@example.com' },
  })
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'Correct-Horse-42!' },
  })
  fireEvent.submit(screen.getByRole('button', { name: 'Welcome back' }).closest('form')!)

  await waitFor(() =>
    expect(signInWithPassword).toHaveBeenCalledWith(
      'reader@example.com',
      'Correct-Horse-42!',
    ),
  )
  expect(onAuthenticated).toHaveBeenCalledOnce()
})

test('moves registration through email confirmation without retaining password', async () => {
  render(<AuthPanel onAuthenticated={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
  fireEvent.change(screen.getByLabelText('Email'), {
    target: { value: 'new@example.com' },
  })
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'Correct-Horse-42!' },
  })
  fireEvent.submit(
    screen.getByRole('button', { name: 'Create your workspace' }).closest('form')!,
  )

  expect(await screen.findByText('Check your email for a verification code.'))
    .toBeInTheDocument()
  expect(registerUser).toHaveBeenCalledWith('new@example.com', 'Correct-Horse-42!')
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Verification code'), {
    target: { value: '123456' },
  })
  fireEvent.submit(
    screen.getByRole('button', { name: 'Confirm your email' }).closest('form')!,
  )

  await waitFor(() =>
    expect(confirmRegistration).toHaveBeenCalledWith('new@example.com', '123456'),
  )
  expect(await screen.findByText('Email confirmed. You can now sign in.'))
    .toBeInTheDocument()
})
