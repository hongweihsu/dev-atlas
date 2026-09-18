# ADR-016: Custom Cognito authentication UI

## Status

Accepted — 2026-09-17

## Context

Cognito managed login supplied secure OAuth and PKCE quickly, but its appearance
was disconnected from Retrieval Works and made registration feel like leaving the
product. Reimplementing Cognito's SRP protocol or storing passwords in the
Retrieval Works API would create unnecessary security risk.

## Decision

Use the official AWS Amplify Auth browser library against the existing
Terraform-managed Cognito User Pool. Retrieval Works renders its own sign-in, sign-up,
email-confirmation, forgot-password, and reset-password states. Amplify performs
SRP authentication and sends credentials directly to Cognito; Retrieval Works receives
only the resulting access token and submits it to `/session/bootstrap`.

Store Amplify tokens in `sessionStorage`, matching the previous tab-scoped
session boundary. Configure the existing public app client with
`ALLOW_USER_SRP_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH`. Do not introduce an
Identity Pool, client secret, or password endpoint in the API.

## Consequences

- Authentication now visually belongs to Retrieval Works while Cognito retains password
  policy, verification codes, recovery, token issuance, and credential storage.
- The frontend bundle grows because it includes the supported SRP implementation.
- Closing the browser tab ends its local session; refresh inside the tab restores
  valid Cognito tokens and reruns idempotent workspace bootstrap.
- Advanced challenges such as MFA and administrator temporary-password changes
  are not yet represented in the custom UI and fail with an explicit next-step
  message.
- Public signup still needs abuse controls and provider-usage limits before this
  low-traffic portfolio deployment is treated as a public production service.
