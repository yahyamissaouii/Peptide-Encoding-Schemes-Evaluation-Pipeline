from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from src.utils.file_utils import add_suffix_to_top_level, suffix_filename

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}

REPORT_COLUMNS = [
    "input_path",
    "status",
    "original_size_bytes",
    "decoded_size_bytes",
    "size_delta_bytes",
    "success",
    "byte_errors",
    "bit_errors",
    "bit_error_rate",
]


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


def _expected_decoded_path(input_file: Path, input_root: Path, output_root: Path) -> Path:
    rel_path = input_file.relative_to(input_root)
    rel_root = rel_path.parent

    decoded_rel_dir = add_suffix_to_top_level(rel_root, "_decoded")
    decoded_rel_file = suffix_filename(Path(rel_path.name), "_decoded")
    decoded_path = output_root / "out_decoded" / decoded_rel_dir / decoded_rel_file.name

    if not decoded_path.exists() and input_file.suffix.lower() in IMAGE_EXTS:
        ppm_candidate = decoded_path.with_suffix(".ppm")
        if ppm_candidate.exists():
            decoded_path = ppm_candidate

    return decoded_path


def _iter_files(root: Path) -> Iterable[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def _format_csv_value(value: object) -> object:
    if value is None:
        return ""
    return value


def generate_report(
    input_root: Path,
    output_root: Path,
    report_dir: Path,
    formats: Sequence[str] = ("csv", "json"),
) -> Dict[str, object]:
    input_root = input_root.resolve()
    output_root = output_root.resolve()
    report_dir = report_dir.resolve()

    rows: List[Dict[str, object]] = []
    total_original_bytes = 0
    total_decoded_bytes = 0
    decoded_present = 0
    success_count = 0
    bit_error_rates: List[float] = []

    for input_file in _iter_files(input_root):
        decoded_path = _expected_decoded_path(input_file, input_root, output_root)
        rel_path = input_file.relative_to(input_root)
        row: Dict[str, object] = {
            "input_path": str(rel_path),
            "status": "ok",
        }

        original_bytes = input_file.read_bytes()
        original_size = len(original_bytes)
        total_original_bytes += original_size
        row["original_size_bytes"] = original_size

        decoded_bytes: Optional[bytes] = None
        if decoded_path.exists():
            decoded_bytes = decoded_path.read_bytes()
            decoded_present += 1
            total_decoded_bytes += len(decoded_bytes)
            row["decoded_size_bytes"] = len(decoded_bytes)
            row["size_delta_bytes"] = len(decoded_bytes) - original_size

            success = decoded_bytes == original_bytes
            row["success"] = success
            if success:
                success_count += 1

            byte_errors = _byte_error_count(original_bytes, decoded_bytes)
            bit_errors = _bit_error_count(original_bytes, decoded_bytes)
            row["byte_errors"] = byte_errors
            row["bit_errors"] = bit_errors
            if original_size:
                bit_error_rate = bit_errors / (original_size * 8)
                row["bit_error_rate"] = bit_error_rate
                bit_error_rates.append(bit_error_rate)
            else:
                row["bit_error_rate"] = 0.0 if bit_errors == 0 else None
        else:
            row["decoded_size_bytes"] = None
            row["size_delta_bytes"] = None
            row["success"] = False
            row["byte_errors"] = None
            row["bit_errors"] = None
            row["bit_error_rate"] = None
            row["status"] = "missing_decoded"

        rows.append(row)

    report_dir.mkdir(parents=True, exist_ok=True)
    formats = [fmt.lower() for fmt in formats]

    summary = {
        "total_files": len(rows),
        "decoded_present": decoded_present,
        "success_count": success_count,
        "success_rate": (success_count / len(rows)) if rows else 0.0,
        "total_original_bytes": total_original_bytes,
        "total_decoded_bytes": total_decoded_bytes,
        "avg_bit_error_rate": statistics.mean(bit_error_rates) if bit_error_rates else 0.0,
        "median_bit_error_rate": statistics.median(bit_error_rates) if bit_error_rates else 0.0,
    }

    meta = {
        "input_root": str(input_root),
        "output_root": str(output_root),
        "report_dir": str(report_dir),
        "generated_at_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if "csv" in formats:
        csv_path = report_dir / "report.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=REPORT_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: _format_csv_value(row.get(k)) for k in REPORT_COLUMNS})

    if "json" in formats:
        json_path = report_dir / "report.json"
        report_payload = {"meta": meta, "summary": summary, "files": rows}
        json_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

    return {"meta": meta, "summary": summary, "files": rows}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate comparison reports for decoded outputs.",
    )
    parser.add_argument("--input-root", required=True, help="Path to original input data root.")
    parser.add_argument("--output-root", required=True, help="Path to pipeline output root.")
    parser.add_argument(
        "--report-dir",
        default="",
        help="Output directory for reports (default: <output-root>/report).",
    )
    parser.add_argument(
        "--formats",
        default="csv,json",
        help="Comma-separated list of formats: csv,json (default: csv,json).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    report_dir = Path(args.report_dir) if args.report_dir else output_root / "report"
    formats = [fmt.strip() for fmt in args.formats.split(",") if fmt.strip()]
    generate_report(
        input_root=input_root,
        output_root=output_root,
        report_dir=report_dir,
        formats=formats,
    )
    print(f"Report written to {report_dir}")


if __name__ == "__main__":
    main()
