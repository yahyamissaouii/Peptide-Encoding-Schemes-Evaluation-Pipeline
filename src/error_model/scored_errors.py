import csv
import os
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import re
from uuid import uuid4
import random

import requests

from src.error_model.drop import drop_amino_acids, drop_peptides
from src.error_model.mutate import mutate_peptides
from src.error_model.insert import insert_aa_random_position
from src.error_model.shuffle import shuffle_amino_acids

BASE_URL = "https://tools.iedb.org"
FORM_URL = f"{BASE_URL}/pepsysco/"
CSV_URL = f"{FORM_URL}result_in_csv/"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

DEFAULT_ALPHABET = "AVLSTFYE"
SCORE_REPORT_DIR = Path("reports/pepsysco")
DEFAULT_SCORE_BATCH_SIZE = max(1, int(os.environ.get("PEPSYSCO_BATCH_SIZE", "5000")))
DEFAULT_SCORE_BATCH_MAX_PAYLOAD_BYTES = max(
    1024,
    int(os.environ.get("PEPSYSCO_BATCH_MAX_PAYLOAD_BYTES", "200000")),
)
_LAST_SCORE_STATS: Optional[Dict[str, float]] = None


def get_last_score_stats() -> Optional[Dict[str, float]]:
    return _LAST_SCORE_STATS


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return float("nan")
    if pct <= 0:
        return min(values)
    if pct >= 1:
        return max(values)
    values = sorted(values)
    pos = (len(values) - 1) * pct
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    if lo == hi:
        return values[lo]
    frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac


def _parse_score_rows(
    csv_text: str,
    score_column: Optional[str],
) -> Tuple[Optional[str], str, List[Tuple[str, float]]]:
    reader = csv.DictReader(StringIO(csv_text))
    rows = list(reader)
    if not rows:
        raise RuntimeError("Score CSV returned no rows.")

    header = reader.fieldnames or []
    peptide_column = None
    for candidate in ("peptide", "sequence", "seq"):
        if candidate in header:
            peptide_column = candidate
            break

    if score_column is None:
        if "score" in header:
            score_column = "score"
        else:
            candidates = []
            for name in header:
                try:
                    fval = float(rows[0][name])
                except (TypeError, ValueError):
                    continue
                if 0.0 <= fval <= 1.0:
                    candidates.append(name)
            if not candidates:
                raise RuntimeError("No numeric score column in [0, 1] found in CSV.")
            if len(candidates) > 1:
                raise RuntimeError(
                    f"Multiple candidate score columns found: {candidates}. "
                    "Pass score_column explicitly."
                )
            score_column = candidates[0]

    parsed: List[Tuple[str, float]] = []
    for row in rows:
        pep = row.get(peptide_column) if peptide_column else ""
        if score_column not in row:
            raise RuntimeError(f"Score column '{score_column}' not found in CSV.")
        parsed.append((pep or "", float(row[score_column])))

    return peptide_column, score_column, parsed


def _safe_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_")
    return cleaned or "pepsysco"


def _save_score_csv(csv_text: str, label: Optional[str]) -> Path:
    SCORE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    prefix = _safe_label(label) if label else "pepsysco"
    filename = f"{prefix}_{timestamp}_{uuid4().hex}.csv"
    path = SCORE_REPORT_DIR / filename
    path.write_text(csv_text, encoding="utf-8")
    return path


def _split_score_batches(
    sequences: Sequence[str],
    max_sequences_per_batch: int,
    max_payload_bytes: int,
) -> List[List[str]]:
    """
    Split peptide sequences into upload-sized chunks.

    `max_payload_bytes` approximates the bytes of the newline-joined
    `sequence_file` text body (without multipart/form-data overhead).
    """
    if max_sequences_per_batch <= 0:
        raise ValueError("max_sequences_per_batch must be > 0")
    if max_payload_bytes <= 0:
        raise ValueError("max_payload_bytes must be > 0")

    batches: List[List[str]] = []
    current: List[str] = []
    current_payload_bytes = 0

    for seq in sequences:
        seq_bytes = len(seq.encode("utf-8"))
        added_bytes = seq_bytes if not current else seq_bytes + 1  # newline separator

        if current and (
            len(current) >= max_sequences_per_batch
            or current_payload_bytes + added_bytes > max_payload_bytes
        ):
            batches.append(current)
            current = [seq]
            current_payload_bytes = seq_bytes
            continue

        current.append(seq)
        current_payload_bytes += added_bytes

    if current:
        batches.append(current)
    return batches


def _fetch_scores_batch(
    sequences: Sequence[str],
    score_column: Optional[str],
    score_label: Optional[str],
    retry_sleep: float = 1.0,
    max_sleep: float = 30.0,
    request_timeout: float = 30.0,
) -> Tuple[List[Tuple[str, float]], str]:
    base_sleep = max(0.1, float(retry_sleep))
    max_retry_window = max(base_sleep, float(max_sleep))
    timeout_s = max(1.0, float(request_timeout))
    deadline = time.monotonic() + max_retry_window
    attempt = 0
    sleep_s = base_sleep
    last_exc: Exception | None = None

    while time.monotonic() <= deadline:
        attempt += 1
        try:
            session = requests.Session()
            session.headers.update(REQUEST_HEADERS)
            r_get = session.get(FORM_URL, timeout=timeout_s)
            r_get.raise_for_status()

            csrf_token = session.cookies.get("csrftoken")
            if not csrf_token:
                raise RuntimeError("CSRF token not found")

            payload = "\n".join(sequences)
            data = {
                "csrfmiddlewaretoken": csrf_token,
                "sequence_text": "",
                "submit": "Submit",
            }
            files = {
                "sequence_file": ("sequences.txt", payload.encode("utf-8"), "text/plain"),
            }
            headers = {
                "Origin": BASE_URL,
                "Referer": FORM_URL,
            }

            r_post = session.post(
                FORM_URL,
                data=data,
                files=files,
                headers=headers,
                allow_redirects=False,
                timeout=timeout_s,
            )
            if r_post.status_code not in (200, 302):
                raise RuntimeError(f"Submission failed: {r_post.status_code}")

            r_csv = session.get(CSV_URL, timeout=timeout_s)
            r_csv.raise_for_status()

            if "text/csv" not in r_csv.headers.get("Content-Type", ""):
                raise RuntimeError("Did not receive CSV content.")

            _save_score_csv(r_csv.text, score_label)
            _, resolved_score_column, parsed = _parse_score_rows(r_csv.text, score_column)
            time.sleep(0.2)
            return parsed, resolved_score_column
        except Exception as exc:
            last_exc = exc
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            wait_s = min(sleep_s, remaining)
            print(
                f"[scored] batch request failed (attempt {attempt}): {exc} -> "
                f"retrying in {wait_s:.1f}s"
            )
            time.sleep(wait_s)
            sleep_s = min(sleep_s * 1.5, max_retry_window)

    raise RuntimeError(
        "Unable to fetch score data from Pepsysco within "
        f"{max_retry_window:.1f}s after {attempt} attempts. "
        f"Last error: {last_exc}"
    )


def _fetch_scores_chunked(
    sequences: Sequence[str],
    score_column: Optional[str],
    score_label: Optional[str],
    retry_sleep: float = 1.0,
    max_sleep: float = 30.0,
    request_timeout: float = 30.0,
    max_sequences_per_batch: int = DEFAULT_SCORE_BATCH_SIZE,
    max_payload_bytes: int = DEFAULT_SCORE_BATCH_MAX_PAYLOAD_BYTES,
) -> List[Tuple[str, float]]:
    if not sequences:
        return []

    batches = _split_score_batches(
        sequences,
        max_sequences_per_batch=max_sequences_per_batch,
        max_payload_bytes=max_payload_bytes,
    )
    total_batches = len(batches)
    resolved_score_column = score_column
    merged: List[Tuple[str, float]] = []

    for batch_idx, batch_sequences in enumerate(batches, start=1):
        print(
            f"[scored] submitting batch {batch_idx}/{total_batches} "
            f"({len(batch_sequences)} peptides)"
        )
        batch_label = score_label
        if score_label and total_batches > 1:
            batch_label = f"{score_label}_chunk{batch_idx:03d}"

        batch_rows, returned_score_column = _fetch_scores_batch(
            batch_sequences,
            score_column=resolved_score_column,
            score_label=batch_label,
            retry_sleep=retry_sleep,
            max_sleep=max_sleep,
            request_timeout=request_timeout,
        )
        if resolved_score_column is None:
            resolved_score_column = returned_score_column
        merged.extend(batch_rows)

    return merged


def apply_peptide_errors_scored(
    peptides: Sequence[str],
    score_column: Optional[str] = None,
    score_label: Optional[str] = None,
    shuffle_passes: int = 1,
    alphabet: str = DEFAULT_ALPHABET,
    drop_empty: bool = True,
    seed: Optional[int] = None,
    loss_mode: str = "aa",
    retry_sleep: float = 1.0,
    max_sleep: float = 30.0,
    request_timeout: float = 30.0,
    score_batch_size: int = DEFAULT_SCORE_BATCH_SIZE,
    score_batch_max_payload_bytes: int = DEFAULT_SCORE_BATCH_MAX_PAYLOAD_BYTES,
) -> List[str]:
    """
    Apply peptide errors using a score-driven probability per peptide.

    For each peptide, fetch score Q in [0, 1], then:
      p(Q) = (1 - Q) * 0.02
      loss_prob = p(Q)
      mutation/insertion/shuffle prob = p(Q) / 2

    Large peptide sets are fetched in batches to avoid oversized requests.
    """
    global _LAST_SCORE_STATS
    rng = random.Random(seed)
    out: List[str] = []

    scored_peptides = [p for p in peptides if p]
    if not scored_peptides:
        _LAST_SCORE_STATS = None
        return [] if drop_empty else list(peptides)

    score_rows = _fetch_scores_chunked(
        scored_peptides,
        score_column=score_column,
        score_label=score_label,
        retry_sleep=retry_sleep,
        max_sleep=max_sleep,
        request_timeout=request_timeout,
        max_sequences_per_batch=score_batch_size,
        max_payload_bytes=score_batch_max_payload_bytes,
    )
    q_values = [score for _, score in score_rows]
    if q_values:
        p_values = [(1.0 - q) * 0.02 for q in q_values]
        avg_q = sum(q_values) / len(q_values)
        avg_p = sum(p_values) / len(p_values)
        _LAST_SCORE_STATS = {
            "avg_q": avg_q,
            "avg_loss_prob": avg_p,
            "avg_mutation_prob": avg_p / 2.0,
            "avg_insertion_prob": avg_p / 2.0,
            "avg_shuffle_prob": avg_p / 2.0,
            "score_mean": avg_q,
            "score_p10": _percentile(q_values, 0.10),
            "score_p90": _percentile(q_values, 0.90),
            "base_error_mean": avg_p,
            "base_error_p10": _percentile(p_values, 0.10),
            "base_error_p90": _percentile(p_values, 0.90),
        }
    else:
        _LAST_SCORE_STATS = None
    use_order = all(pep for pep, _ in score_rows)
    order_scores: Optional[List[float]] = None

    score_map: Dict[str, List[float]] = {}
    if use_order:
        for pep, score in score_rows:
            score_map.setdefault(pep, []).append(score)
    else:
        if len(score_rows) != len(scored_peptides):
            raise RuntimeError("Score row count does not match number of peptides.")
        order_scores = [score for _, score in score_rows]

    order_idx = 0

    for peptide in peptides:
        if peptide == "":
            if not drop_empty:
                out.append(peptide)
            continue

        if order_scores is not None:
            q = order_scores[order_idx]
            order_idx += 1
        else:
            if peptide not in score_map or not score_map[peptide]:
                raise RuntimeError(f"Score missing for peptide: {peptide}")
            q = score_map[peptide].pop(0)
        p_val = (1.0 - q) * 0.02
        loss_prob = p_val
        other_prob = p_val / 2.0

        print(f"[scored] seq={peptide} Q={q:.6f} p={p_val:.6f}")

        current = [peptide]
        if loss_prob > 0.0:
            if loss_mode == "peptide":
                current = drop_peptides(
                    current,
                    loss_prob=loss_prob,
                    rng=rng,
                    drop_empty=drop_empty,
                )
            else:
                current = drop_amino_acids(
                    current,
                    loss_prob=loss_prob,
                    rng=rng,
                    drop_empty=drop_empty,
                )
        if not current:
            print("[scored] -> dropped (empty after loss)")
            continue

        if other_prob > 0.0:
            current = mutate_peptides(
                current,
                mutation_prob=other_prob,
                alphabet=alphabet,
                rng=rng,
            )
            current = insert_aa_random_position(
                current,
                insertion_prob=other_prob,
                alphabet=alphabet,
                rng=rng,
            )
            current = shuffle_amino_acids(
                current,
                shuffle_prob=other_prob,
                rng=rng,
                passes=shuffle_passes,
            )

        print(f"[scored] with_errors={current}")
        if current == [peptide]:
            print("\x1b[32mMATCH\x1b[0m")
        else:
            print("\x1b[31mERROR\x1b[0m")

        out.extend(current)
        #time.sleep(1.0)
    return out
