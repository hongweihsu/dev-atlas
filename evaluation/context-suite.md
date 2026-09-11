# Phase 4 adversarial context suite

This suite is separate from the Phase 2–3 retrieval regression set. It is a
small, human-reviewed diagnostic workload for candidate ranking and answer
context construction, not a public benchmark and not evidence of broad domain
generalization.

Each case records a `failure_mode` hypothesis. A hypothesis becomes an observed
failure only after a reproducible run shows that the answer-bearing passage is
missing, displaced, or surrounded by materially redundant context. Cases that
do not distinguish candidate/context policies should be revised or removed
rather than counted as successful evidence.

The corpus deliberately contains repeated vocabulary, policy exceptions,
negative rules, and exact identifiers. It should be loaded with its own ignored
manifest and preferably an isolated evaluation database. Running hybrid or
vector retrieval requires query and document embeddings and may incur provider
cost; review the corpus and cases before the first live run.

The existing retrieval evaluator accepts the files as-is because
`failure_mode` is explanatory metadata. A Phase 4 report must additionally
record context budget utilization, represented documents, same-document
concentration, neighboring offset overlap, and the position of the first
answer-bearing chunk.
