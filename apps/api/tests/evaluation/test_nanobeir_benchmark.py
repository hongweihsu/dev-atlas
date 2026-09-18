import numpy as np

from retrieval_works.evaluation.nanobeir_benchmark import (
    dense_rankings,
    reciprocal_rank_fusion_ids,
)


def test_dense_ranking_preserves_vector_to_official_id_mapping() -> None:
    rankings = dense_rankings(
        document_ids=["doc-a", "doc-b", "doc-c"],
        query_ids=["query"],
        document_vectors=np.asarray([[1, 0], [0, 1], [-1, 0]], dtype=np.float32),
        query_vectors=np.asarray([[0, 1]], dtype=np.float32),
        limit=3,
    )

    assert rankings["query"] == ["doc-b", "doc-a", "doc-c"]


def test_hybrid_fusion_rewards_a_document_found_by_both_rankers() -> None:
    ranking = reciprocal_rank_fusion_ids(
        ["dense-only", "shared"],
        ["lexical-only", "shared"],
        limit=3,
    )

    assert ranking == ["shared", "dense-only", "lexical-only"]
