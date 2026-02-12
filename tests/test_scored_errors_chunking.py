from src.error_model import scored_errors as se


def test_split_score_batches_respects_sequence_limit():
    peptides = [f"P{i}" for i in range(7)]
    batches = se._split_score_batches(
        peptides,
        max_sequences_per_batch=3,
        max_payload_bytes=10_000,
    )

    assert [len(batch) for batch in batches] == [3, 3, 1]
    assert [pep for batch in batches for pep in batch] == peptides


def test_split_score_batches_respects_payload_limit():
    peptides = ["A" * 10, "B" * 10, "C" * 10]
    # Two 10-aa peptides need 21 bytes in newline-joined payload.
    batches = se._split_score_batches(
        peptides,
        max_sequences_per_batch=10,
        max_payload_bytes=20,
    )

    assert [len(batch) for batch in batches] == [1, 1, 1]
    assert [pep for batch in batches for pep in batch] == peptides


def test_fetch_scores_chunked_preserves_order_and_reuses_score_column(monkeypatch):
    peptides = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    score_map = {pep: (idx + 1) / 10.0 for idx, pep in enumerate(peptides)}
    calls = []

    def fake_fetch_scores_batch(
        sequences,
        score_column,
        score_label,
        retry_sleep=1.0,
        max_sleep=30.0,
        request_timeout=30.0,
    ):
        calls.append(
            {
                "sequences": list(sequences),
                "score_column": score_column,
                "score_label": score_label,
            }
        )
        resolved_column = score_column or "score"
        return [(pep, score_map[pep]) for pep in sequences], resolved_column

    monkeypatch.setattr(se, "_fetch_scores_batch", fake_fetch_scores_batch)

    rows = se._fetch_scores_chunked(
        peptides,
        score_column=None,
        score_label="demo",
        max_sequences_per_batch=2,
        max_payload_bytes=10_000,
    )

    assert [call["sequences"] for call in calls] == [
        ["AAA", "BBB"],
        ["CCC", "DDD"],
        ["EEE"],
    ]
    assert calls[0]["score_column"] is None
    assert calls[1]["score_column"] == "score"
    assert calls[2]["score_column"] == "score"
    assert [call["score_label"] for call in calls] == [
        "demo_chunk001",
        "demo_chunk002",
        "demo_chunk003",
    ]
    assert rows == [(pep, score_map[pep]) for pep in peptides]
