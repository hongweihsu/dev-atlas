# DevAtlas engineering case study

## Problem

DevAtlas is a technical knowledge platform built to answer a harder engineering
question than “can an LLM answer a document?”: can ingestion, retrieval,
generation, authorization, lifecycle, evaluation, and operations remain
explainable and testable as the product grows?

The project therefore treats model calls as one dependency inside a typed
system. PostgreSQL owns durable truth, the API owns authorization, citations
must resolve to retrieved chunks, and quality claims require recorded evidence.

## Implemented architecture

```text
Browser / React / TypeScript
          |
          | Cognito access token + workspace scope
          v
CloudFront ----> FastAPI
                    |-- PostgreSQL + pgvector
                    |-- Redis / ARQ ingestion worker
                    |-- OpenAI embedding, generation, and PDF vision adapters
                    `-- request/workflow telemetry
```

The low-traffic AWS demo uses a private S3 frontend origin and one ARM EC2
Docker host in Sydney. This avoids the fixed cost of an ALB, NAT Gateway, RDS,
and Fargate, while openly accepting a single point of failure. PostgreSQL dumps
are retained in a private S3 bucket and administration uses Systems Manager
instead of inbound SSH.

## Engineering decisions

### Durable identity and provenance

A logical document has immutable versions; each version owns ordered chunks
with source offsets and optional PDF page spans. Only one version is active at a
time. Archive and historical-version activation preserve citations instead of
overwriting evidence.

### Retrieval is measured, not assumed

DevAtlas combines pgvector cosine retrieval and BM25S with reciprocal-rank
fusion because semantic concepts and exact technical identifiers fail in
different ways. Raw BM25 and cosine scores are never added because their scales
are incompatible.

On a reviewed, lexical-heavy 16-case project corpus, rank-one document/evidence
recall measured 0.875 for vector, 1.000 for BM25, and 0.938 for hybrid. This
supports hybrid over vector on that fixture but does not support claiming it
beats BM25 generally.

A broader 150-query NanoBEIR comparison showed the expected workload
dependence: dense retrieval led NanoSciFact and NanoNFCorpus, while hybrid RRF
led NanoHotpotQA at nDCG@10 (0.8444 versus 0.8098 BM25 and 0.7898 dense). The
benchmark intentionally evaluates retrieval methods rather than the complete
chunked product pipeline.

### Authorization is never delegated to the model

Cognito proves external identity; a database membership independently grants a
role in a workspace. Every document, KnowledgeBase, retrieval, answer,
conversation, and tool operation is scoped by server-resolved identity. Tool
schemas do not let the LLM choose a workspace, and model-selected KnowledgeBase
IDs are re-authorized before execution.

### Agent behavior is bounded

Conversation memory uses LangGraph to load a limited history, rewrite a
follow-up into a standalone retrieval query, answer through the existing RAG
path, and persist an immutable turn. Agentic research allows one sequential
tool call per turn and three per run. Corrective RAG permits only one query
rewrite and retry after validated insufficient evidence.

### Observability respects the knowledge boundary

HTTP and AI workflow events share a request ID, and Prometheus metrics expose
bounded status, latency, and outcome dimensions. Telemetry excludes raw paths,
questions, prompts, user/workspace identifiers, retrieved chunks, and answers.
CloudWatch watches EC2 health and CloudFront 5xx rate; service objectives remain
targets until enough continuously retained traffic exists to measure them.

### Native-first multimodal ingestion

PDF ingestion keeps deterministic `pypdf` text extraction as its default. A
fully scanned PDF or any PDF with a textless page is instead sent through a
structured OpenAI file-input adapter that returns every page in order, renders
tables as Markdown, and describes meaningful figures without answering or
following document instructions. The request uses high-detail PDF vision and
disables provider-side response storage. Page spans remain attached to chunks,
so retrieval citations still point back to their source pages.

This trigger controls cost but does not yet detect a malformed table on a page
that contains some native text. Phase 18 will evaluate that boundary before
expanding it.

A one-page image-only fixture exercised the live local worker. Structured
extraction preserved the `MM-731` table row and the four-step flow diagram;
hybrid retrieval returned that page, and the grounded answer identified
`AI Systems` / `Pilot` with a page-1 citation. This is vertical-slice evidence,
not a general PDF accuracy benchmark.

## Failure that changed the design

A live corrective-RAG request safely returned a provider-contract `502`; the
same request later succeeded. That transient incident became the Phase 16
requirement: distinguish provider availability, invalid provider output,
correction branches, and HTTP recovery without logging document content. An
automated regression now proves that a `503` followed by `200` is visible in
the application counters.

## Verification evidence

- Backend quality gate: Ruff, strict mypy, and 219 passing tests, with five
  environment-gated integration skips.
- Frontend quality gate: ESLint, TypeScript, 16 component tests, and production
  Vite build.
- Infrastructure gate: valid Terraform, renderable production Compose, checked
  shell syntax, cost constraints, encrypted runtime parameters, a deployed
  checksum-verified source artifact, successful migrations, post-reboot health,
  protected metrics, and an active backup timer.
- Retrieval evidence: reviewed project fixtures plus three public NanoBEIR
  tasks, with reports retaining configuration, limitations, and per-strategy
  results.
- PDF evidence: a visually inspected image-only table/flow fixture, successful
  queued ingestion in one attempt, exact-identifier retrieval, and a grounded
  page-1 citation.

## Intentional limitations

- The demo is single-node and not highly available.
- Prometheus metrics are exposed for operator snapshots but are not yet retained
  by a continuous scraper; SLO targets are not achievement claims.
- Scanned and partially textless PDFs have a multimodal fallback, but native
  pages with degraded layout are not yet automatically re-extracted or
  retrieval-benchmarked.
- Cognito users and workspace memberships are operator-provisioned; self-service
  invitations, workspace creation, and workspace selection are not implemented.
- Backup automation is installed, but a disposable restore rehearsal has not
  yet established a measured recovery time.
- LangSmith is not enabled. Before exporting detailed AI traces, the project
  needs an explicit redaction, sampling, retention, and environment policy.
- BM25 currently rebuilds from active chunks per request; a measured threshold,
  not speculation, controls when caching becomes justified.

## What this demonstrates

The portfolio evidence is not merely that DevAtlas calls an LLM. It demonstrates
typed application boundaries, transactional persistence, evaluated retrieval,
tenant authorization, bounded agent control, privacy-conscious observability,
cost-aware infrastructure, and the discipline to distinguish implemented and
measured behavior from future plans.
