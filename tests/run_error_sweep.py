from __future__ import annotations

import argparse
import csv
import sys
import time
from itertools import product
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.config import PipelineConfig
from src.encoding_schemes.peptide_mapping import (
    PeptideMappingResult,
    bits_to_peptides,
    peptides_to_bits,
    peptides_to_bits_fixed,
)
from src.error_correction import ecc_encode_peptides, ecc_decode_peptides
from src.error_model import apply_peptide_errors, apply_peptide_errors_scored
from src.error_correction.registry import FOUNTAIN_PROFILES, PEPTIDE_RS_PROFILES, get_fountain_overhead
from src.error_model.scored_errors import get_last_score_stats


def _iter_files(root: Path) -> Iterable[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def _byte_error_count(a: bytes, b: bytes) -> int:
    min_len = min(len(a), len(b))
    errors = sum(1 for i in range(min_len) if a[i] != b[i])
    errors += abs(len(a) - len(b))
    return errors


def _bit_error_count(a: bytes, b: bytes) -> int:
    min_len = min(len(a), len(b))
    errors = 0
    for i in range(min_len):
        if a[i] != b[i]:
            errors += (a[i] ^ b[i]).bit_count()
    errors += abs(len(a) - len(b)) * 8
    return errors


def _parse_prob_values(raw: str) -> List[float]:
    values = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.append(float(chunk) / 100.0)
    if not values:
        raise ValueError("No probability values provided.")
    return values


def _build_scenarios(prob_values: Sequence[float], mode: str) -> List[Dict[str, float]]:
    if mode == "grid":
        scenarios = []
        for loss, mutation, insertion, shuffle in product(prob_values, repeat=4):
            scenarios.append(
                {
                    "loss_prob": loss,
                    "mutation_prob": mutation,
                    "insertion_prob": insertion,
                    "shuffle_prob": shuffle,
                }
            )
        return scenarios

    return [
        {
            "loss_prob": value,
            "mutation_prob": value,
            "insertion_prob": value,
            "shuffle_prob": value,
        }
        for value in prob_values
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run error sweeps and export CSV metrics for plotting.",
    )
    parser.add_argument(
        "--input-root",
        default="resources/test/data_test",
        help="Path to input data root.",
    )
    parser.add_argument(
        "--output-csv",
        default="reports/error_sweep.csv",
        help="CSV output path.",
    )
    parser.add_argument(
        "--profiles",
        default="rs8,rs16,rs32,rs64,rs128,rs200",
        help="Comma-separated RS profiles.",
    )
    parser.add_argument(
        "--prob-values",
        default="0.5,1.0,1.5,2.0",
        help="Comma-separated probability values (percent).",
    )
    parser.add_argument(
        "--mode",
        choices=["equal", "grid"],
        default="equal",
        help="Scenario mode: equal uses the same prob for all error types.",
    )
    parser.add_argument(
        "--peptide-length",
        type=int,
        default=18,
        help="Peptide length.",
    )
    parser.add_argument(
        "--index-aa-length",
        type=int,
        default=0,
        help="Index prefix length in amino acids.",
    )
    parser.add_argument(
        "--shuffle-passes",
        type=int,
        default=1,
        help="Shuffle passes when shuffle_prob > 0.",
    )
    parser.add_argument(
        "--encoder",
        choices=["huffman", "yin_yang", "yinyang", "fountain"],
        default="huffman",
        help="Encoding scheme to evaluate.",
    )
    parser.add_argument(
        "--error-model",
        choices=["basic", "scored"],
        default="basic",
        help="Error model to use (basic or scored).",
    )
    parser.add_argument(
        "--score-column",
        default=None,
        help="Score column name for the scored error model.",
    )
    return parser.parse_args()


def _compute_failure_mode(
    success: bool,
    decoded_len: int,
    outer_failed: bool,
    source_failed: bool,
) -> str:
    if success:
        return "success"
    if outer_failed:
        return "outer_decoder_failure"
    if source_failed:
        return "source_codec_failure"
    if decoded_len == 0:
        return "empty_output"
    return "mismatch"


def main() -> None:
    args = _parse_args()
    input_root = Path(args.input_root)
    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    encoder = args.encoder.lower().strip()
    if encoder in {"yinyang", "yin-yang"}:
        encoder = "yin_yang"

    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    if encoder == "fountain":
        for profile in profiles:
            if profile.lower() not in FOUNTAIN_PROFILES:
                raise ValueError(
                    f"Unknown Fountain profile: {profile}. "
                    f"Expected one of: {', '.join(sorted(FOUNTAIN_PROFILES))}"
                )
    else:
        for profile in profiles:
            if profile not in PEPTIDE_RS_PROFILES:
                raise ValueError(f"Unknown ECC profile: {profile}")

    prob_values = _parse_prob_values(args.prob_values)
    scenarios = _build_scenarios(prob_values, args.mode)
    if args.error_model == "scored":
        scenarios = [
            {
                "loss_prob": 0.0,
                "mutation_prob": 0.0,
                "insertion_prob": 0.0,
                "shuffle_prob": 0.0,
            }
        ]


    rows: List[Dict[str, object]] = []
    run_id = 0

    for scenario in scenarios:
        for profile in profiles:
            cfg = PipelineConfig(
                peptide_length=args.peptide_length,
                ecc_profile=profile,
                loss_prob=scenario["loss_prob"],
                mutation_prob=scenario["mutation_prob"],
                insertion_prob=scenario["insertion_prob"],
                shuffle_prob=scenario["shuffle_prob"],
                shuffle_passes=args.shuffle_passes,
                encoder=encoder,
                index_aa_length=args.index_aa_length,
                error_model=args.error_model,
                score_column=args.score_column,
            )

            for input_file in _iter_files(input_root):
                cfg.score_label = input_file.name
                data = input_file.read_bytes()
                outer_failed = False
                source_failed = False
                useful_bits = 0
                mapping = None
                ecc_packet = None
                fountain_encoded = None
                total_peptides = 0
                yin_yang_original_size_bytes = len(data)
                decoded = b""
                score_stats = None

                encode_start = time.perf_counter()
                try:
                    if encoder == "huffman":
                        from src.encoding_schemes.huffman import huffman_encode

                        enc = huffman_encode(data)
                        useful_bits = len(enc.bits)  # bits
                        mapping = bits_to_peptides(
                            enc.bits,
                            peptide_length=cfg.peptide_length,
                            index_aa_length=cfg.index_aa_length,
                        )
                        ecc_packet = ecc_encode_peptides(mapping, profile=cfg.ecc_profile)
                        original_peptides = ecc_packet.peptides
                    elif encoder == "yin_yang":
                        from src.encoding_schemes.yin_yang import yin_yang_encode

                        yy = yin_yang_encode(data, cfg)
                        yin_yang_original_size_bytes = yy.original_size_bytes
                        useful_bits = len(data) * 8  # bits (no compression)
                        mapping = PeptideMappingResult(
                            peptides=yy.peptides,
                            pad_bits=yy.pad_bits,
                            peptide_length=cfg.peptide_length,
                            index_aa_length=cfg.index_aa_length,
                        )
                        ecc_packet = ecc_encode_peptides(mapping, profile=cfg.ecc_profile)
                        original_peptides = ecc_packet.peptides
                    elif encoder == "fountain":
                        from src.encoding_schemes.fountain import fountain_encode

                        overhead = get_fountain_overhead(cfg.ecc_profile, cfg.fountain_overhead)
                        fountain_encoded = fountain_encode(data, cfg, overhead=overhead)
                        useful_bits = len(data) * 8  # bits (original payload)
                        mapping = bits_to_peptides(
                            fountain_encoded.bits,
                            peptide_length=cfg.peptide_length,
                            index_aa_length=cfg.index_aa_length,
                            pad_to_full_peptide=True,
                        )
                        original_peptides = mapping.peptides
                        total_peptides = len(mapping.peptides)
                    else:
                        raise ValueError(f"Unsupported encoder: {encoder}")
                except Exception:
                    outer_failed = True
                    original_peptides = []
                encode_time_s = time.perf_counter() - encode_start  # seconds

                corrupted_peptides = []
                if not outer_failed:
                    try:
                        drop_empty = True
                        if encoder == "fountain":
                            # Without an index prefix, we must preserve peptide positions for alignment.
                            drop_empty = cfg.index_aa_length > 0

                        if cfg.error_model == "scored":
                            corrupted_peptides = apply_peptide_errors_scored(
                                original_peptides,
                                score_column=cfg.score_column,
                                score_label=cfg.score_label,
                                shuffle_passes=cfg.shuffle_passes,
                                drop_empty=drop_empty,
                                loss_mode="peptide" if encoder == "fountain" else "aa",
                                retry_sleep=cfg.score_retry_sleep,
                                max_sleep=cfg.score_max_sleep,
                                request_timeout=cfg.score_timeout,
                                score_batch_size=cfg.score_batch_size,
                                score_batch_max_payload_bytes=cfg.score_batch_max_payload_bytes,
                            )
                            score_stats = get_last_score_stats()
                        else:
                            corrupted_peptides = apply_peptide_errors(
                                original_peptides,
                                loss_prob=cfg.loss_prob,
                                mutation_prob=cfg.mutation_prob,
                                insertion_prob=cfg.insertion_prob,
                                shuffle_prob=cfg.shuffle_prob,
                                shuffle_passes=cfg.shuffle_passes,
                                drop_empty=drop_empty,
                                loss_mode="peptide" if encoder == "fountain" else "aa",
                            )
                    except Exception:
                        outer_failed = True

                decode_start = time.perf_counter()
                recovered_mapping = None

                if encoder in {"huffman", "yin_yang"}:
                    if not outer_failed and ecc_packet is not None:
                        try:
                            recovered_mapping = ecc_decode_peptides(
                                corrupted_peptides,
                                encoded=ecc_packet,
                                profile=cfg.ecc_profile,
                            )
                            if not recovered_mapping.peptides:
                                outer_failed = True
                        except Exception:
                            outer_failed = True
                            recovered_mapping = None

                    if not outer_failed and recovered_mapping is not None:
                        try:
                            if encoder == "huffman":
                                from src.encoding_schemes.huffman import huffman_decode

                                recovered_bits = peptides_to_bits(recovered_mapping)
                                enc.bits = recovered_bits
                                decoded = huffman_decode(enc)
                            else:
                                from src.encoding_schemes.yin_yang import YinYangEncoded, yin_yang_decode

                                recovered = YinYangEncoded(
                                    peptides=recovered_mapping.peptides,
                                    pad_bits=recovered_mapping.pad_bits,
                                    peptide_length=recovered_mapping.peptide_length,
                                    index_aa_length=recovered_mapping.index_aa_length,
                                    original_size_bytes=yin_yang_original_size_bytes,
                                )
                                decoded = yin_yang_decode(recovered)
                        except Exception:
                            source_failed = True
                            decoded = b""
                else:
                    if not outer_failed and fountain_encoded is not None and mapping is not None:
                        try:
                            recovered_bits = peptides_to_bits_fixed(
                                list(corrupted_peptides),
                                peptide_length=mapping.peptide_length,
                                index_aa_length=mapping.index_aa_length,
                                total_peptides=total_peptides,
                                pad_bits=mapping.pad_bits,
                            )
                            fountain_encoded.bits = recovered_bits
                            from src.encoding_schemes.fountain import fountain_decode

                            decoded = fountain_decode(fountain_encoded)
                            if not decoded and fountain_encoded.original_size > 0:
                                outer_failed = True
                        except Exception:
                            outer_failed = True
                            decoded = b""

                decode_time_s = time.perf_counter() - decode_start  # seconds

                loss_prob = score_stats["avg_loss_prob"] if score_stats else scenario["loss_prob"]
                mutation_prob = score_stats["avg_mutation_prob"] if score_stats else scenario["mutation_prob"]
                insertion_prob = score_stats["avg_insertion_prob"] if score_stats else scenario["insertion_prob"]
                shuffle_prob = score_stats["avg_shuffle_prob"] if score_stats else scenario["shuffle_prob"]
                prob_mean = (loss_prob + mutation_prob + insertion_prob + shuffle_prob) / 4.0

                byte_errors = _byte_error_count(data, decoded)
                bit_errors = _bit_error_count(data, decoded)
                total_bits = len(data) * 8
                bit_error_rate = (bit_errors / total_bits) if total_bits else 0.0

                success = decoded == data
                failure_mode = _compute_failure_mode(
                    success=success,
                    decoded_len=len(decoded),
                    outer_failed=outer_failed,
                    source_failed=source_failed,
                )

                payload_residues_per_peptide = cfg.peptide_length - cfg.index_aa_length
                tx_peptides = len(original_peptides)
                tx_residues_total = tx_peptides * cfg.peptide_length  # residues
                encoded_size_bytes = (tx_residues_total * 3 + 7) // 8  # bytes (3 bits per residue capacity)

                if encoder == "fountain":
                    data_units = fountain_encoded.k if fountain_encoded else 0  # source packets
                    parity_units = 0
                    tx_units = fountain_encoded.droplet_count if fountain_encoded else 0  # droplets
                    payload_bits_capacity = tx_peptides * payload_residues_per_peptide * 3  # bits
                    payload_bits_useful = useful_bits  # bits
                elif encoder == "yin_yang":
                    data_units = len(mapping.peptides) if mapping else 0  # data peptides
                    parity_units = (len(ecc_packet.peptides) - data_units) if ecc_packet else 0
                    tx_units = len(ecc_packet.peptides) if ecc_packet else 0  # transmitted peptides
                    payload_bits_capacity = data_units * payload_residues_per_peptide * 2  # bits (YY rate)
                    payload_bits_useful = useful_bits  # bits
                else:
                    data_units = len(mapping.peptides) if mapping else 0  # data peptides
                    parity_units = (len(ecc_packet.peptides) - data_units) if ecc_packet else 0
                    tx_units = len(ecc_packet.peptides) if ecc_packet else 0  # transmitted peptides
                    payload_bits_capacity = data_units * payload_residues_per_peptide * 3  # bits
                    payload_bits_useful = useful_bits  # bits

                rows.append(
                    {
                        "run_id": run_id,
                        "input_path": str(input_file),
                        "ecc_profile": profile,
                        "peptide_length": args.peptide_length,
                        "index_aa_length": args.index_aa_length,
                        "loss_prob": loss_prob,
                        "mutation_prob": mutation_prob,
                        "insertion_prob": insertion_prob,
                        "shuffle_prob": shuffle_prob,
                        "prob_mean": prob_mean,
                        "shuffle_passes": args.shuffle_passes,
                        "original_size_bytes": len(data),
                        "encoded_size_bytes": encoded_size_bytes,
                        "decoded_size_bytes": len(decoded),
                        "size_delta_bytes": len(decoded) - len(data),
                        "success": success,
                        "byte_errors": byte_errors,
                        "bit_errors": bit_errors,
                        "bit_error_rate": bit_error_rate,
                        "failure_mode": failure_mode,
                        "data_units": data_units,
                        "parity_units": parity_units,
                        "tx_units": tx_units,
                        "tx_residues_total": tx_residues_total,
                        "payload_bits_capacity": payload_bits_capacity,
                        "payload_bits_useful": payload_bits_useful,
                        "encode_time_s": encode_time_s,
                        "decode_time_s": decode_time_s,
                        "total_time_s": encode_time_s + decode_time_s,
                        "score_mean": score_stats["score_mean"] if score_stats else None,
                        "score_p10": score_stats["score_p10"] if score_stats else None,
                        "score_p90": score_stats["score_p90"] if score_stats else None,
                        "base_error_mean": score_stats["base_error_mean"] if score_stats else None,
                        "base_error_p10": score_stats["base_error_p10"] if score_stats else None,
                        "base_error_p90": score_stats["base_error_p90"] if score_stats else None,
                        "encoder": encoder,
                    }
                )
            run_id += 1

    fieldnames = [
        "run_id",
        "input_path",
        "ecc_profile",
        "peptide_length",
        "index_aa_length",
        "loss_prob",
        "mutation_prob",
        "insertion_prob",
        "shuffle_prob",
        "prob_mean",
        "shuffle_passes",
        "original_size_bytes",
        "encoded_size_bytes",
        "decoded_size_bytes",
        "size_delta_bytes",
        "success",
        "byte_errors",
        "bit_errors",
        "bit_error_rate",
        "failure_mode",
        "data_units",
        "parity_units",
        "tx_units",
        "tx_residues_total",
        "payload_bits_capacity",
        "payload_bits_useful",
        "encode_time_s",
        "decode_time_s",
        "total_time_s",
        "score_mean",
        "score_p10",
        "score_p90",
        "base_error_mean",
        "base_error_p10",
        "base_error_p90",
        "encoder",
    ]

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {output_csv}")


if __name__ == "__main__":
    main()
