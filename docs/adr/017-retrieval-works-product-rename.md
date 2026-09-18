# ADR 017: Rename the product through a verified parallel deployment

## Status

Accepted on 2026-09-19.

## Context

The project began under the DevAtlas name. Before the demo accumulated durable
production data, the product name changed to Retrieval Works. The old name had
already become a Python package, service identifier, metrics namespace, runtime
path, SSM parameter path, and prefix for multiple Terraform-managed resources.

A read-only plan against the deployed stack reported 23 creates, eight in-place
updates, and 23 destroys when the Terraform prefix changed. Replacements
included the Cognito user pool and both S3 buckets. Applying that plan directly
would unnecessarily combine a brand migration with identity and storage
destruction.

## Decision

- Use **Retrieval Works** for the public product and documentation.
- Use `retrieval_works` for Python and PostgreSQL-compatible identifiers.
- Use `retrieval-works` for DNS, service, artifact, SSM, and AWS resource names.
- Retain the local AWS CLI profile and current GitHub repository identifier until
  those external identifiers are deliberately migrated.
- Create a separately named AWS stack, validate its authentication, ingestion,
  retrieval, backup, and readiness paths, and then move the custom hostname.
- Remove the old stack only after the new deployment passes the cutover checks
  and any required data has been copied.

## Consequences

The codebase and public presentation have one consistent product name without
making the current demo unavailable during migration. The two stacks may incur
a short period of overlapping infrastructure cost. Cognito identities are not
implicitly portable, so the low-volume demo accounts may need to register again
unless an explicit user migration is justified. Stable historical Git commits
and existing AWS state continue to show the former name as deployment history.
