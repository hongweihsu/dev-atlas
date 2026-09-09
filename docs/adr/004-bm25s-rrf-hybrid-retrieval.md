# ADR 004: BM25S and reciprocal-rank fusion for the first hybrid slice

- Status: accepted
- Date: 2026-09-10

## Context

DevAtlas must retrieve both semantic descriptions and exact technical tokens
such as error codes, configuration keys, incident IDs, and migration numbers.
Its first vector-only stratified baseline achieved perfect identifier results
but weaker rank-one results on two semantic cases. Hybrid retrieval is therefore
a product capability whose effect must be measured, not a presumed fix for a
fabricated vector-search failure.

Phase 3 needs a real BM25 implementation without turning the feature into a
second search-service or database-platform migration.

## Decision

Use `bm25s` for lexical candidate ranking and pgvector for semantic candidate
ranking. Fuse the two ordered candidate lists with reciprocal rank fusion (RRF),
which depends on rank positions rather than incomparable raw BM25 and cosine
scores.

Keep lexical retrieval and fusion behind application ports. DevAtlas-specific
code owns active-version filtering, stable chunk identity, bounded candidate
collection, deterministic tie-breaking, and result provenance; the package owns
BM25 token statistics and scoring.

For the initial single-user slice, build the lexical index from the current
active chunks and make its refresh behavior explicit. Record the cost before
claiming this design scales.

## Alternatives considered

### PostgreSQL full-text search

Native `tsvector`, `tsquery`, and `ts_rank` would keep indexing transactionally
close to source data and add no service. They do not provide BM25 scoring, so
they would not test the intended lexical approach.

### ParadeDB `pg_search`

ParadeDB provides PostgreSQL-native BM25 and automatically reflects table
changes. It is a stronger candidate once persistent, high-volume, or filtered
search is required. Adopting it now would replace the database image, add an
extension and index migration, and couple this experiment to an infrastructure
change before scale requires it.

### The high-level `BM25` package

The package wraps `bm25s` with a simpler API, but it was first released shortly
before this decision. DevAtlas uses the established lower-level package directly
so the index metadata and returned chunk identities remain under explicit
control.

## Consequences

- Hybrid ranking can be tested locally without another external service.
- RRF avoids arbitrary normalization between BM25 and cosine scores.
- The application must own index construction, refresh, memory use, and
  concurrency behavior.
- This implementation is intentionally bounded; persistent or distributed
  search requires revisiting this ADR.
- Evaluation must report vector-only and hybrid behavior by query category and
  preserve per-case diagnostics.
