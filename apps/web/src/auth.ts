import { Amplify } from 'aws-amplify'
import {
  confirmResetPassword,
  confirmSignUp,
  fetchAuthSession,
  resendSignUpCode,
  resetPassword,
  signIn,
  signOut as amplifySignOut,
  signUp,
} from 'aws-amplify/auth'
import { cognitoUserPoolsTokenProvider } from 'aws-amplify/auth/cognito'

import { bootstrapSession } from './api'

const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID as string | undefined
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined

export const usesCognitoAuthentication = Boolean(userPoolId && clientId)

if (usesCognitoAuthentication) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: userPoolId!,
        userPoolClientId: clientId!,
        loginWith: { email: true },
        signUpVerificationMethod: 'code',
        userAttributes: { email: { required: true } },
        passwordFormat: {
          minLength: 12,
          requireLowercase: true,
          requireUppercase: true,
          requireNumbers: true,
          requireSpecialCharacters: true,
        },
      },
    },
  })
  cognitoUserPoolsTokenProvider.setKeyValueStorage({
    async setItem(key, value) {
      window.sessionStorage.setItem(key, value)
    },
    async getItem(key) {
      return window.sessionStorage.getItem(key)
    },
    async removeItem(key) {
      window.sessionStorage.removeItem(key)
    },
    async clear() {
      window.sessionStorage.clear()
    },
  })
}

export async function restoreCognitoSession(): Promise<boolean> {
  if (!usesCognitoAuthentication) return false
  const session = await fetchAuthSession()
  const accessToken = session.tokens?.accessToken.toString()
  const identityToken = session.tokens?.idToken?.toString()
  if (!accessToken || !identityToken) return false
  await bootstrapSession(accessToken, identityToken)
  return true
}

export async function signInWithPassword(email: string, password: string) {
  const result = await signIn({ username: email, password })
  if (!result.isSignedIn) {
    throw new Error(`Additional sign-in step required: ${result.nextStep.signInStep}`)
  }
  await bootstrapAuthenticatedSession()
}

export async function registerUser(email: string, password: string) {
  await signUp({
    username: email,
    password,
    options: { userAttributes: { email } },
  })
}

export async function confirmRegistration(email: string, code: string) {
  await confirmSignUp({ username: email, confirmationCode: code })
}

export async function resendRegistrationCode(email: string) {
  await resendSignUpCode({ username: email })
}

export async function requestPasswordReset(email: string) {
  const result = await resetPassword({ username: email })
  if (result.nextStep.resetPasswordStep !== 'CONFIRM_RESET_PASSWORD_WITH_CODE') {
    throw new Error('Password reset is not available for this account')
  }
}

export async function completePasswordReset(
  email: string,
  code: string,
  newPassword: string,
) {
  await confirmResetPassword({
    username: email,
    confirmationCode: code,
    newPassword,
  })
}

export async function signOut(): Promise<void> {
  await amplifySignOut()
  window.location.assign('/')
}

async function bootstrapAuthenticatedSession() {
  const session = await fetchAuthSession()
  const accessToken = session.tokens?.accessToken.toString()
  const identityToken = session.tokens?.idToken?.toString()
  if (!accessToken || !identityToken) throw new Error('Cognito returned incomplete tokens')
  await bootstrapSession(accessToken, identityToken)
}

export function authenticationErrorMessage(error: unknown): string {
  if (!(error instanceof Error)) return 'Authentication failed. Please try again.'
  const messages: Record<string, string> = {
    CodeMismatchException: 'The verification code is incorrect.',
    ExpiredCodeException: 'The verification code has expired. Request a new code.',
    InvalidPasswordException:
      'Use at least 12 characters with uppercase, lowercase, number, and symbol.',
    NotAuthorizedException: 'The email or password is incorrect.',
    UsernameExistsException: 'An account already exists for this email.',
    UserNotConfirmedException: 'Confirm your email before signing in.',
  }
  return messages[error.name] ?? error.message
}
