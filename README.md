# Peptide Encoding Evaluation

This repository evaluates peptide-based storage pipelines with three encoders:

- `huffman`
- `yin_yang`
- `fountain`

It supports peptide-level error simulation, Reed-Solomon protection, batch runs over folders, and report generation.

## Project Structure

- `src/encoding_schemes/`: Huffman, Yin-Yang, Fountain, peptide mapping.
- `src/error_model/`: basic and score-driven error simulation.
- `src/error_correction/`: RS profiles and peptide-level RS encoding/decoding.
- `src/pipeline/`: pipeline config and encoder dispatch.
- `src/utils/batch.py`: batch folder processing (`run_batch_on_folder`).
- `src/reporting/report.py`: decoded-vs-original report generator (CSV/JSON).
- `tests/`: test scripts and runnable experiment scripts.
- `resources/test/data_test/`: default input dataset used by batch scripts.
- `resources/test/out_test_*`: example output folders from prior runs.
- `reports/`: saved sweep CSVs and score CSV dumps (`reports/pepsysco`).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install matplotlib
```

Notes:

- `matplotlib` is needed for `plot_error_sweep.py`.
- `requests` is required for scored error mode (already in `requirements.txt`).

## Where To Put Test Data

Default and recommended:

- Put files under `resources/test/data_test/`.

Additional sample corpora already in repo:

- `resources/test/reserve/text_files`
- `resources/test/reserve/pictures`
- `resources/test/reserve/dwd_weatherdata`
- `resources/test/reserve/output_uv_radiation_seq_generation`

Custom datasets:

- Use `run_batch_on_folder(input_root=...)`.
- Use `tests/run_error_sweep.py --input-root ...`.
- Use `src/reporting/report.py --input-root ...`.

## Main Commands (CMD)

### Run Tests

```bash
python3 tests/test_huffman_enc_dec.py
python3 tests/test_yin_yang_enc_dec.py
python3 tests/test_fountain.py
python3 tests/test_peptide_mapping.py
python3 tests/test_error_model.py
python3 tests/test_peptide.py
```

### Run Batch Test Script (`test_run_batch.py`)

Important: this script uses `../resources/...` relative paths, so run it from `tests/`.

```bash
cd tests
python3 test_run_batch.py
```

This writes outputs to:

- `resources/test/out_test_<encoder>_<ecc_profile>/out_encoded`
- `resources/test/out_test_<encoder>_<ecc_profile>/out_chunked`
- `resources/test/out_test_<encoder>_<ecc_profile>/out_decoded`

### Run Fountain Batch Script (`test_run_batch_fountain.py`)

Also run from `tests/`:

```bash
cd tests
python3 test_run_batch_fountain.py
```

### Run Error Sweep Experiments

```bash
python3 tests/run_error_sweep.py \
  --input-root resources/test/data_test \
  --output-csv reports/error_sweep.csv \
  --profiles rs8,rs16,rs32,rs64 \
  --prob-values 0.5,1.0,1.5,2.0 \
  --mode equal \
  --encoder huffman \
  --error-model basic
```

For Fountain:

```bash
python3 tests/run_error_sweep.py \
  --input-root resources/test/data_test \
  --output-csv reports/error_sweep_fountain.csv \
  --profiles fnt10,fnt20,fnt30,fnt50 \
  --encoder fountain
```

CLI options:

```bash
python3 tests/run_error_sweep.py --help
```



### Generate Decoded-vs-Original Reports

```bash
python3 src/reporting/report.py \
  --input-root resources/test/data_test \
  --output-root resources/test/out_test_huffman_rs64 \
  --formats csv,json
```

By default this writes to `<output-root>/report`.

### Optional Utility Scripts

```bash
python3 extract_score.py
python3 plot_error_sweep.py
python3 src/error_correction/reed_solomon.py
```

## PipelineConfig Reference

`src/pipeline/config.py` defines all config fields:

| Field | Default | What it controls |
|---|---:|---|
| `peptide_length` | `18` | Total residues per peptide. |
| `visualize_as_pgm` | `False` | Write `.pgm` visualization for decoded image bytes in batch mode. |
| `visualize_width` | `0` | Width for PGM output (`0` means auto/derived). |
| `convert_images_to_ppm` | `True` | Intended image conversion toggle. Current conversion block in `src/utils/batch.py` is commented out. |
| `embed_image_header` | `False` | Intended image metadata embedding. Effective only if conversion/header path is enabled. |
| `ecc_profile` | `"none"` | ECC profile string (RS profiles for Huffman/Yin-Yang, Fountain profiles for Fountain overhead). |
| `loss_prob` | `0.0` | Loss probability. Basic model: per-aa loss by default; Fountain uses peptide-level loss. |
| `mutation_prob` | `0.0` | Mutation probability. |
| `insertion_prob` | `0.0` | Insertion probability. |
| `shuffle_prob` | `0.0` | Neighbor-swap probability. |
| `shuffle_passes` | `1` | Number of shuffle passes. |
| `encoder` | `"huffman"` | One of `huffman`, `yin_yang`, `fountain`. |
| `index_aa_length` | `0` | Prefix residues used as index. Must be `<= peptide_length`. |
| `error_model` | `"basic"` | `basic` or `scored`. |
| `score_column` | `None` | Score column name for scored mode CSV parsing. |
| `score_label` | `None` | Label used in saved score CSV filename. Set per file in batch/sweep flows. |
| `score_retry_sleep` | `1.0` | Initial retry backoff (seconds) for Pepsysco scored requests. |
| `score_max_sleep` | `30.0` | Total retry window (seconds) per scored request batch. |
| `score_timeout` | `30.0` | HTTP timeout (seconds) per Pepsysco request. |
| `score_batch_size` | `5000` | Max number of peptides per scored request batch. |
| `score_batch_max_payload_bytes` | `200_000` | Approximate max bytes of newline-joined peptide payload per scored batch. |
| `fountain_symbol_size` | `17` | Desired source symbol size in bytes (may be clamped by packet capacity). |
| `fountain_overhead` | `0.1` | Fallback overhead when `ecc_profile` is not a recognized `fnt*` profile. |
| `fountain_seed_bytes` | `4` | Seed bytes in each droplet header. |
| `fountain_degree_bytes` | `2` | Degree bytes in each droplet header. |
| `fountain_crc_bytes` | `4` | CRC bytes per droplet. |
| `fountain_c` | `0.1` | Robust soliton distribution parameter `c`. |
| `fountain_delta` | `0.5` | Robust soliton distribution parameter `delta`. |
| `fountain_seed` | `None` | RNG seed for deterministic droplet generation. |
| `fountain_max_bytes` | `1_048_576` | Max input size currently supported by Fountain encoder. |

## ECC Profile Values

For Huffman / Yin-Yang (`ecc_profile` in RS registry):

- `none`
- `rs4`, `rs8`, `rs16`, `rs32`, `rs64`
- `rs64_int4`, `rs8_int4`
- `rs128`, `rs200`, `rs201`

For Fountain (`ecc_profile` interpreted as overhead profile):

- `fnt05`, `fnt10`, `fnt20`, `fnt30`, `fnt50`
- `fnt75`, `fnt100`, `fnt150`, `fnt200`

## Reports Explained

### 1) Batch Comparison Report (`report.csv`, `report.json`)

Generated by `src/reporting/report.py` into `<output-root>/report` (or `--report-dir`).

CSV columns:

- `input_path`
- `status` (`ok` or `missing_decoded`)
- `original_size_bytes`
- `decoded_size_bytes`
- `size_delta_bytes`
- `success`
- `byte_errors`
- `bit_errors`
- `bit_error_rate`

JSON includes:

- `meta`: roots + timestamp
- `summary`: totals, success rate, average/median BER
- `files`: per-file records

### 2) Error Sweep CSV (`reports/error_sweep*.csv`)

Generated by `tests/run_error_sweep.py`.

Includes per-run/per-file metrics such as:

- error probabilities (`loss_prob`, `mutation_prob`, `insertion_prob`, `shuffle_prob`, `prob_mean`)
- sizes, success/failure mode
- byte/bit errors and BER
- data/parity/transmission unit counts
- timing (`encode_time_s`, `decode_time_s`, `total_time_s`)
- scored-mode stats (`score_mean`, `score_p10`, `score_p90`, etc.)

### 3) Pepsysco Score Dumps (`reports/pepsysco/*.csv`)

When `error_model="scored"`, raw CSV responses from IEDB Pepsysco are saved here.

- Requires internet access.
- `score_label` affects filename prefix.

## Typical End-to-End Workflow

1. Put data in `resources/test/data_test/` (or choose a custom input folder).
2. Run batch encoding/decoding (`tests/test_run_batch.py` or your own `run_batch_on_folder` call).
3. Generate comparison report with `python3 src/reporting/report.py`.
4. Run sweeps with `tests/run_error_sweep.py`.
5. Plot sweep CSV with `plot_error_sweep.py`.
