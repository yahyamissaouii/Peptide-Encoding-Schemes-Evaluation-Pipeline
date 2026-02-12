from __future__ import annotations

import html
import inspect
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st


# Keep imports stable when page is executed directly by Streamlit.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.error_model.apply_errors import apply_peptide_errors  # noqa: E402
from src.error_model.drop import drop_amino_acids, drop_peptides  # noqa: E402
from src.error_model.insert import insert_aa_random_position  # noqa: E402
from src.error_model.mutate import mutate_peptides  # noqa: E402
from src.error_model.shuffle import shuffle_amino_acids  # noqa: E402
from src.encoding_schemes.fountain import FountainEncoded, fountain_decode, fountain_encode  # noqa: E402
from src.encoding_schemes.huffman import HuffmanEncoded, huffman_decode, huffman_encode  # noqa: E402
from src.encoding_schemes.peptide_mapping import bits_to_peptides, peptides_to_bits, peptides_to_bits_fixed  # noqa: E402
from src.encoding_schemes.yin_yang import YinYangEncoded, yin_yang_decode, yin_yang_encode  # noqa: E402
from src.pipeline.config import PipelineConfig  # noqa: E402
from src.utils.bits_bytes_utils import bytes_to_bitstring  # noqa: E402

# Import shared styles
FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from utils.shared_styles import render_page_styles, render_nav_pills, render_page_header  # noqa: E402


DEFAULT_ALPHABET = "AVLSTFYE"


@dataclass
class TraceStep:
    line_no: int
    event: str
    before: str
    after: str
    detail: str
    stage: str


CODE_SNIPPETS: dict[str, str] = {
    "deletion": """
def residue_deletion(peptide, loss_prob, rng, drop_empty=True):
    out = []
    for i, aa in enumerate(peptide):
        u = rng.random()
        if u >= loss_prob:
            out.append(aa)
    result = "".join(out)
    if result or not drop_empty:
        return result
    return ""
""".strip("\n"),
    "substitution": """
def residue_substitution(peptide, mutation_prob, alphabet, rng):
    chars = list(peptide)
    for i, aa in enumerate(chars):
        u = rng.random()
        if u < mutation_prob:
            choices = [x for x in alphabet if x != aa]
            if choices:
                chars[i] = rng.choice(choices)
    return "".join(chars)
""".strip("\n"),
    "insertion": """
def residue_insertion(peptide, insertion_prob, alphabet, rng):
    chars = list(peptide)
    if not chars:
        return peptide
    out = []
    for aa in chars:
        u = rng.random()
        if u < insertion_prob:
            ins = rng.choice(alphabet)
            v = rng.random()
            if v < 0.5:
                out.append(ins); out.append(aa)
            else:
                out.append(aa); out.append(ins)
        else:
            out.append(aa)
    return "".join(out)
""".strip("\n"),
    "shuffle": """
def local_shuffle(peptide, shuffle_prob, passes, rng):
    chars = list(peptide)
    n = len(chars)
    if n <= 1 or shuffle_prob <= 0.0 or passes <= 0:
        return peptide
    for _ in range(passes):
        for i in range(n - 1):
            u = rng.random()
            if u < shuffle_prob:
                chars[i], chars[i + 1] = chars[i + 1], chars[i]
    return "".join(chars)
""".strip("\n"),
    "pipeline": """
def apply_error_pipeline(peptide, cfg, rng):
    after_loss = residue_deletion(peptide, cfg.loss_prob, rng, cfg.drop_empty)
    if after_loss == "" and cfg.drop_empty:
        return ""
    after_mutation = residue_substitution(after_loss, cfg.mutation_prob, cfg.alphabet, rng)
    after_insertion = residue_insertion(after_mutation, cfg.insertion_prob, cfg.alphabet, rng)
    after_shuffle = local_shuffle(after_insertion, cfg.shuffle_prob, cfg.shuffle_passes, rng)
    return after_shuffle
""".strip("\n"),
}

CODE_SNIPPETS_CODEC: dict[str, str] = {
    "huffman": """
raw_bytes = text.encode("utf-8")
raw_bits = bytes_to_bitstring(raw_bytes)
encoded = huffman_encode(raw_bytes)
mapping = bits_to_peptides(
    encoded.bits,
    peptide_length=cfg.peptide_length,
    index_aa_length=cfg.index_aa_length,
)
recovered_bits = peptides_to_bits(mapping)
decoded = huffman_decode(HuffmanEncoded(bits=recovered_bits, codec=encoded.codec))
decoded_text = decoded.decode("utf-8", errors="replace")
""".strip("\n"),
    "yin_yang": """
raw_bytes = text.encode("utf-8")
raw_bits = bytes_to_bitstring(raw_bytes)
encoded = yin_yang_encode(raw_bytes, cfg)
peptides = encoded.peptides
decoded = yin_yang_decode(
    YinYangEncoded(
        peptides=peptides,
        pad_bits=encoded.pad_bits,
        peptide_length=cfg.peptide_length,
        index_aa_length=cfg.index_aa_length,
        original_size_bytes=encoded.original_size_bytes,
        scheme_id=encoded.scheme_id,
    )
)
decoded_text = decoded.decode("utf-8", errors="replace")
""".strip("\n"),
    "fountain": """
raw_bytes = text.encode("utf-8")
encoded = fountain_encode(raw_bytes, cfg, overhead=overhead)
mapping = bits_to_peptides(
    encoded.bits,
    peptide_length=cfg.peptide_length,
    index_aa_length=cfg.index_aa_length,
    pad_to_full_peptide=True,
)
recovered_bits = peptides_to_bits_fixed(
    mapping.peptides,
    peptide_length=mapping.peptide_length,
    index_aa_length=mapping.index_aa_length,
    total_peptides=len(mapping.peptides),
    pad_bits=mapping.pad_bits,
)
encoded.bits = recovered_bits
decoded = fountain_decode(encoded)
decoded_text = decoded.decode("utf-8", errors="replace")
""".strip("\n"),
}


EXAMPLE_PEPTIDES = [
    "AVLSTFYEAVLSTFYE",
    "AVVVLLLSSSTTTFFF",
    "FYESTLAVFYESTLAV",
    "ALSVTFYEAAVVSTLE",
]


def _render_visualizer_styles() -> None:
    """Render visualizer-specific styles (in addition to shared styles)."""
    st.markdown(
        """
<style>
/* Visualizer-specific styles */
.trace-card {
  border: 1px solid rgba(27, 122, 95, 0.15);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.7);
  padding: 1rem;
  margin-bottom: 1rem;
}

.trace-card h4 {
  margin: 0 0 0.45rem 0;
  font-size: 1.1rem;
}

.trace-card p {
  margin: 0;
  color: var(--text-subtle);
}

.seq-row {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  margin-bottom: 0.6rem;
}

.seq-label {
  width: 58px;
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding-top: 0.3rem;
}

.seq-track {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem;
}

.aa {
  min-width: 1.8rem;
  text-align: center;
  padding: 0.24rem 0.35rem;
  border-radius: 6px;
  border: 1px solid rgba(27, 122, 95, 0.18);
  background: #ffffff;
  color: var(--text-ink);
  font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
  font-size: 0.86rem;
}

.aa-changed {
  background: rgba(27, 122, 95, 0.16);
  border-color: rgba(27, 122, 95, 0.45);
  color: var(--primary-strong);
  font-weight: 700;
}

.aa-empty {
  color: #7c9b8f;
}

.code-panel {
  border: 1px solid rgba(27, 122, 95, 0.18);
  border-radius: 12px;
  background: #f7fbf8;
  overflow: hidden;
}

.code-row {
  display: grid;
  grid-template-columns: 2.5rem 1fr;
  column-gap: 0.7rem;
  padding: 0.33rem 0.75rem;
  border-bottom: 1px solid rgba(27, 122, 95, 0.08);
}

.code-row:last-child {
  border-bottom: none;
}

.code-row.is-active {
  background: rgba(27, 122, 95, 0.17);
}

.line-no {
  color: #7c9b8f;
  font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
  font-size: 0.82rem;
  text-align: right;
}

.code-src {
  color: var(--text-ink);
  font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
  font-size: 0.84rem;
  white-space: pre-wrap;
}

.flow-row {
  margin-bottom: 0.7rem;
}

.flow-label {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.3rem;
}

.flow-value {
  margin: 0;
  padding: 0.6rem 0.7rem;
  border-radius: 8px;
  border: 1px solid rgba(27, 122, 95, 0.16);
  background: #ffffff;
  color: var(--text-ink);
  font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
  font-size: 0.8rem;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _clean_peptide(raw: str) -> tuple[str, str]:
    upper = raw.upper().strip()
    letters = "".join(ch for ch in upper if ch.isalpha())
    removed = "".join(ch for ch in upper if not ch.isalpha())
    return letters, removed


def _step(line_no: int, event: str, before: str, after: str, detail: str, stage: str) -> TraceStep:
    return TraceStep(
        line_no=line_no,
        event=event,
        before=before,
        after=after,
        detail=detail,
        stage=stage,
    )


def _trace_deletion(peptide: str, loss_prob: float, drop_empty: bool, rng: random.Random) -> tuple[list[TraceStep], str]:
    stage = "deletion"
    steps: list[TraceStep] = []
    out: list[str] = []
    steps.append(_step(1, "Initialize deletion algorithm", peptide, peptide, "Create empty output buffer.", stage))

    for i, aa in enumerate(peptide):
        current = "".join(out)
        roll = rng.random()
        steps.append(_step(4, f"Sample u for position {i + 1}", current, current, f"u={roll:.4f}", stage))
        if roll >= loss_prob:
            out.append(aa)
            after = "".join(out)
            steps.append(
                _step(
                    5,
                    f"Keep residue '{aa}'",
                    current,
                    after,
                    f"u={roll:.4f} >= p_loss={loss_prob:.4f}",
                    stage,
                )
            )
        else:
            steps.append(
                _step(
                    5,
                    f"Drop residue '{aa}'",
                    current,
                    current,
                    f"u={roll:.4f} < p_loss={loss_prob:.4f}",
                    stage,
                )
            )

    result = "".join(out)
    steps.append(_step(6, "Join kept residues", "".join(out), result, "result = ''.join(out)", stage))
    if result or not drop_empty:
        steps.append(_step(7, "Return result", peptide, result, "Output survives.", stage))
        return steps, result

    steps.append(_step(8, "Return empty peptide", peptide, "", "drop_empty=True and all residues dropped.", stage))
    return steps, ""


def _trace_substitution(
    peptide: str,
    mutation_prob: float,
    alphabet: str,
    rng: random.Random,
) -> tuple[list[TraceStep], str]:
    stage = "substitution"
    steps: list[TraceStep] = []
    chars = list(peptide)
    steps.append(_step(1, "Initialize residue list", peptide, peptide, "chars = list(peptide)", stage))

    for i, aa in enumerate(chars.copy()):
        before = "".join(chars)
        roll = rng.random()
        steps.append(_step(3, f"Sample u at position {i + 1}", before, before, f"u={roll:.4f}", stage))
        if roll < mutation_prob:
            choices = [x for x in alphabet if x != chars[i]]
            steps.append(
                _step(
                    5,
                    f"Build replacement set for '{chars[i]}'",
                    before,
                    before,
                    f"{len(choices)} choices in alphabet.",
                    stage,
                )
            )
            if choices:
                new_aa = rng.choice(choices)
                chars[i] = new_aa
                after = "".join(chars)
                steps.append(
                    _step(
                        6,
                        f"Mutate position {i + 1}: {aa} -> {new_aa}",
                        before,
                        after,
                        f"u={roll:.4f} < p_mut={mutation_prob:.4f}",
                        stage,
                    )
                )
        else:
            steps.append(
                _step(
                    4,
                    f"No mutation at position {i + 1}",
                    before,
                    before,
                    f"u={roll:.4f} >= p_mut={mutation_prob:.4f}",
                    stage,
                )
            )

    final = "".join(chars)
    steps.append(_step(7, "Return mutated peptide", peptide, final, "return ''.join(chars)", stage))
    return steps, final


def _trace_insertion(
    peptide: str,
    insertion_prob: float,
    alphabet: str,
    rng: random.Random,
) -> tuple[list[TraceStep], str]:
    stage = "insertion"
    steps: list[TraceStep] = []
    chars = list(peptide)
    steps.append(_step(1, "Initialize insertion algorithm", peptide, peptide, "chars = list(peptide)", stage))
    if not chars:
        steps.append(_step(2, "Empty peptide guard", peptide, peptide, "No insertion on empty input.", stage))
        return steps, peptide

    out: list[str] = []
    for i, aa in enumerate(chars):
        before = "".join(out)
        roll = rng.random()
        steps.append(_step(5, f"Sample u at source position {i + 1}", before, before, f"u={roll:.4f}", stage))
        if roll < insertion_prob:
            ins_aa = rng.choice(alphabet)
            place_roll = rng.random()
            if place_roll < 0.5:
                out.append(ins_aa)
                out.append(aa)
                after = "".join(out)
                steps.append(
                    _step(
                        9,
                        f"Insert '{ins_aa}' before '{aa}'",
                        before,
                        after,
                        f"u={roll:.4f} < p_ins={insertion_prob:.4f}, v={place_roll:.4f} < 0.5",
                        stage,
                    )
                )
            else:
                out.append(aa)
                out.append(ins_aa)
                after = "".join(out)
                steps.append(
                    _step(
                        10,
                        f"Insert '{ins_aa}' after '{aa}'",
                        before,
                        after,
                        f"u={roll:.4f} < p_ins={insertion_prob:.4f}, v={place_roll:.4f} >= 0.5",
                        stage,
                    )
                )
        else:
            out.append(aa)
            after = "".join(out)
            steps.append(
                _step(
                    11,
                    f"No insertion for '{aa}'",
                    before,
                    after,
                    f"u={roll:.4f} >= p_ins={insertion_prob:.4f}",
                    stage,
                )
            )

    final = "".join(out)
    steps.append(_step(12, "Return inserted peptide", peptide, final, "return ''.join(out)", stage))
    return steps, final


def _trace_shuffle(peptide: str, shuffle_prob: float, shuffle_passes: int, rng: random.Random) -> tuple[list[TraceStep], str]:
    stage = "shuffle"
    steps: list[TraceStep] = []
    chars = list(peptide)
    n = len(chars)
    steps.append(_step(1, "Initialize shuffle algorithm", peptide, peptide, f"n={n}", stage))
    if n <= 1 or shuffle_prob <= 0.0 or shuffle_passes <= 0:
        steps.append(
            _step(
                2,
                "Early return (no-op)",
                peptide,
                peptide,
                "Need n>1, shuffle_prob>0, shuffle_passes>0",
                stage,
            )
        )
        return steps, peptide

    for pass_idx in range(shuffle_passes):
        steps.append(
            _step(
                3,
                f"Start pass {pass_idx + 1}/{shuffle_passes}",
                "".join(chars),
                "".join(chars),
                "Iterate adjacent swaps.",
                stage,
            )
        )
        for i in range(n - 1):
            before = "".join(chars)
            roll = rng.random()
            steps.append(
                _step(
                    5,
                    f"Sample u for edge ({i + 1},{i + 2})",
                    before,
                    before,
                    f"u={roll:.4f}",
                    stage,
                )
            )
            if roll < shuffle_prob:
                chars[i], chars[i + 1] = chars[i + 1], chars[i]
                after = "".join(chars)
                steps.append(
                    _step(
                        6,
                        f"Swap positions {i + 1} and {i + 2}",
                        before,
                        after,
                        f"u={roll:.4f} < p_shuf={shuffle_prob:.4f}",
                        stage,
                    )
                )

    final = "".join(chars)
    steps.append(_step(7, "Return shuffled peptide", peptide, final, "return ''.join(chars)", stage))
    return steps, final


def _trace_pipeline(
    peptide: str,
    cfg: dict[str, Any],
    rng: random.Random,
) -> tuple[list[TraceStep], str]:
    stage = "pipeline"
    steps: list[TraceStep] = []
    steps.append(_step(1, "Start pipeline", peptide, peptide, "Input peptide.", stage))

    loss_steps, after_loss = _trace_deletion(
        peptide=peptide,
        loss_prob=cfg["loss_prob"],
        drop_empty=cfg["drop_empty"],
        rng=rng,
    )
    _ = loss_steps
    steps.append(
        _step(
            2,
            "Apply residue deletion",
            peptide,
            after_loss,
            f"p_loss={cfg['loss_prob']:.4f}",
            stage,
        )
    )

    if after_loss == "" and cfg["drop_empty"]:
        steps.append(
            _step(
                3,
                "Pipeline short-circuit",
                after_loss,
                "",
                "All residues deleted and drop_empty=True",
                stage,
            )
        )
        return steps, ""

    _, after_mut = _trace_substitution(
        peptide=after_loss,
        mutation_prob=cfg["mutation_prob"],
        alphabet=cfg["alphabet"],
        rng=rng,
    )
    steps.append(
        _step(
            4,
            "Apply substitution",
            after_loss,
            after_mut,
            f"p_mut={cfg['mutation_prob']:.4f}",
            stage,
        )
    )

    _, after_ins = _trace_insertion(
        peptide=after_mut,
        insertion_prob=cfg["insertion_prob"],
        alphabet=cfg["alphabet"],
        rng=rng,
    )
    steps.append(
        _step(
            5,
            "Apply insertion",
            after_mut,
            after_ins,
            f"p_ins={cfg['insertion_prob']:.4f}",
            stage,
        )
    )

    _, after_shuf = _trace_shuffle(
        peptide=after_ins,
        shuffle_prob=cfg["shuffle_prob"],
        shuffle_passes=cfg["shuffle_passes"],
        rng=rng,
    )
    steps.append(
        _step(
            6,
            "Apply local shuffle",
            after_ins,
            after_shuf,
            f"p_shuf={cfg['shuffle_prob']:.4f}, passes={cfg['shuffle_passes']}",
            stage,
        )
    )
    steps.append(_step(7, "Return pipeline output", peptide, after_shuf, "Final corrupted peptide.", stage))
    return steps, after_shuf


def _count_changed_positions(before: str, after: str) -> int:
    max_len = max(len(before), len(after))
    changed = 0
    for i in range(max_len):
        a = before[i] if i < len(before) else ""
        b = after[i] if i < len(after) else ""
        if a != b:
            changed += 1
    return changed


def _sequence_row_html(label: str, seq: str, ref: str) -> str:
    max_len = max(len(seq), len(ref))
    chips: list[str] = []
    if max_len == 0:
        chips.append('<span class="aa aa-empty">∅</span>')
    else:
        for i in range(max_len):
            a = seq[i] if i < len(seq) else "∅"
            b = ref[i] if i < len(ref) else "∅"
            klass = "aa aa-changed" if a != b else "aa"
            chips.append(f'<span class="{klass}" title="pos {i + 1}">{html.escape(a)}</span>')

    return (
        '<div class="seq-row">'
        f'<div class="seq-label">{html.escape(label)}</div>'
        f'<div class="seq-track">{"".join(chips)}</div>'
        "</div>"
    )


def _render_code_panel(code: str, active_line: int) -> str:
    rows: list[str] = []
    for i, raw in enumerate(code.splitlines(), start=1):
        klass = "code-row is-active" if i == active_line else "code-row"
        rows.append(
            f'<div class="{klass}">'
            f'<span class="line-no">{i:>2}</span>'
            f'<span class="code-src">{html.escape(raw)}</span>'
            "</div>"
        )
    return f'<div class="code-panel">{"".join(rows)}</div>'


def _build_trace(
    algorithm_key: str,
    peptide: str,
    cfg: dict[str, Any],
) -> tuple[list[TraceStep], str]:
    rng = random.Random(cfg["seed"])
    if algorithm_key == "deletion":
        return _trace_deletion(peptide, cfg["loss_prob"], cfg["drop_empty"], rng)
    if algorithm_key == "substitution":
        return _trace_substitution(peptide, cfg["mutation_prob"], cfg["alphabet"], rng)
    if algorithm_key == "insertion":
        return _trace_insertion(peptide, cfg["insertion_prob"], cfg["alphabet"], rng)
    if algorithm_key == "shuffle":
        return _trace_shuffle(peptide, cfg["shuffle_prob"], cfg["shuffle_passes"], rng)
    return _trace_pipeline(peptide, cfg, rng)


def _preview_text(value: str, max_chars: int = 240) -> str:
    if len(value) <= max_chars:
        return value
    keep = max(20, (max_chars - 5) // 2)
    return f"{value[:keep]} ... {value[-keep:]}"


def _bytes_preview(data: bytes, max_bytes: int = 56) -> str:
    if not data:
        return "∅"
    if len(data) <= max_bytes:
        return data.hex(" ")
    head = data[: max_bytes // 2].hex(" ")
    tail = data[-(max_bytes // 2):].hex(" ")
    return f"{head} ... {tail}"


def _peptides_preview(peptides: list[str], limit: int = 4) -> str:
    if not peptides:
        return "∅"
    shown = peptides[:limit]
    if len(peptides) > limit:
        shown.append(f"... (+{len(peptides) - limit} more)")
    return " | ".join(shown)


def _flow_row_html(label: str, value: str) -> str:
    cleaned = value if value else "∅"
    return (
        '<div class="flow-row">'
        f'<div class="flow-label">{html.escape(label)}</div>'
        f'<pre class="flow-value">{html.escape(cleaned)}</pre>'
        "</div>"
    )


def _build_codec_trace_huffman(text: str, cfg: PipelineConfig) -> tuple[list[TraceStep], dict[str, Any]]:
    steps: list[TraceStep] = []
    stage = "huffman"

    raw_bytes = text.encode("utf-8")
    raw_bits = bytes_to_bitstring(raw_bytes)
    steps.append(
        _step(
            1,
            "Encode UTF-8 input to bytes",
            text,
            _bytes_preview(raw_bytes),
            f"{len(raw_bytes)} byte(s)",
            stage,
        )
    )
    steps.append(
        _step(
            2,
            "Convert bytes to baseline bitstring",
            _bytes_preview(raw_bytes),
            _preview_text(raw_bits),
            f"{len(raw_bits)} bit(s)",
            stage,
        )
    )

    encoded = huffman_encode(raw_bytes)
    steps.append(
        _step(
            3,
            "Run Huffman encoder",
            _preview_text(raw_bits),
            _preview_text(encoded.bits),
            f"{len(encoded.bits)} encoded bit(s)",
            stage,
        )
    )

    mapping = bits_to_peptides(
        encoded.bits,
        peptide_length=cfg.peptide_length,
        index_aa_length=cfg.index_aa_length,
    )
    steps.append(
        _step(
            4,
            "Map encoded bits to peptides",
            _preview_text(encoded.bits),
            _peptides_preview(mapping.peptides),
            f"{len(mapping.peptides)} peptide(s), pad_bits={mapping.pad_bits}",
            stage,
        )
    )

    recovered_bits = peptides_to_bits(mapping)
    steps.append(
        _step(
            9,
            "Reconstruct bitstream from peptides",
            _peptides_preview(mapping.peptides),
            _preview_text(recovered_bits),
            f"{len(recovered_bits)} recovered bit(s)",
            stage,
        )
    )

    decoded = huffman_decode(HuffmanEncoded(bits=recovered_bits, codec=encoded.codec))
    decoded_text = decoded.decode("utf-8", errors="replace")
    steps.append(
        _step(
            10,
            "Decode Huffman bitstream back to text",
            _preview_text(recovered_bits),
            _preview_text(decoded_text),
            f"{len(decoded)} decoded byte(s)",
            stage,
        )
    )

    result = {
        "encoder_label": "Huffman",
        "input_text": text,
        "decoded_text": decoded_text,
        "input_bytes": len(raw_bytes),
        "bit_length": len(encoded.bits),
        "peptide_count": len(mapping.peptides),
        "peptide_preview": _peptides_preview(mapping.peptides, limit=6),
        "success": decoded == raw_bytes,
    }
    return steps, result


def _build_codec_trace_yin_yang(text: str, cfg: PipelineConfig) -> tuple[list[TraceStep], dict[str, Any]]:
    steps: list[TraceStep] = []
    stage = "yin_yang"

    raw_bytes = text.encode("utf-8")
    raw_bits = bytes_to_bitstring(raw_bytes)
    steps.append(
        _step(
            1,
            "Encode UTF-8 input to bytes",
            text,
            _bytes_preview(raw_bytes),
            f"{len(raw_bytes)} byte(s)",
            stage,
        )
    )
    steps.append(
        _step(
            2,
            "Convert bytes to baseline bitstring",
            _bytes_preview(raw_bytes),
            _preview_text(raw_bits),
            f"{len(raw_bits)} bit(s)",
            stage,
        )
    )

    encoded = yin_yang_encode(raw_bytes, cfg)
    steps.append(
        _step(
            3,
            "Run Yin-Yang constrained encoder",
            _preview_text(raw_bits),
            _peptides_preview(encoded.peptides),
            f"{len(encoded.peptides)} peptide(s), pad_bits={encoded.pad_bits}",
            stage,
        )
    )

    recovered = YinYangEncoded(
        peptides=encoded.peptides,
        pad_bits=encoded.pad_bits,
        peptide_length=encoded.peptide_length,
        index_aa_length=encoded.index_aa_length,
        original_size_bytes=encoded.original_size_bytes,
        scheme_id=encoded.scheme_id,
    )
    decoded = yin_yang_decode(recovered)
    decoded_text = decoded.decode("utf-8", errors="replace")
    steps.append(
        _step(
            5,
            "Decode Yin-Yang peptides back to text",
            _peptides_preview(encoded.peptides),
            _preview_text(decoded_text),
            f"{len(decoded)} decoded byte(s)",
            stage,
        )
    )

    result = {
        "encoder_label": "Yin-Yang",
        "input_text": text,
        "decoded_text": decoded_text,
        "input_bytes": len(raw_bytes),
        "bit_length": len(raw_bits),
        "peptide_count": len(encoded.peptides),
        "peptide_preview": _peptides_preview(encoded.peptides, limit=6),
        "success": decoded == raw_bytes,
    }
    return steps, result


def _build_codec_trace_fountain(
    text: str,
    cfg: PipelineConfig,
    overhead: float,
) -> tuple[list[TraceStep], dict[str, Any]]:
    steps: list[TraceStep] = []
    stage = "fountain"

    raw_bytes = text.encode("utf-8")
    steps.append(
        _step(
            1,
            "Encode UTF-8 input to bytes",
            text,
            _bytes_preview(raw_bytes),
            f"{len(raw_bytes)} byte(s)",
            stage,
        )
    )

    encoded: FountainEncoded = fountain_encode(raw_bytes, cfg, overhead=overhead)
    steps.append(
        _step(
            2,
            "Build LT droplets with CRC",
            _bytes_preview(raw_bytes),
            _preview_text(encoded.bits),
            f"droplets={encoded.droplet_count}, k={encoded.k}, bits={len(encoded.bits)}",
            stage,
        )
    )

    mapping = bits_to_peptides(
        encoded.bits,
        peptide_length=cfg.peptide_length,
        index_aa_length=cfg.index_aa_length,
        pad_to_full_peptide=True,
    )
    steps.append(
        _step(
            3,
            "Map droplet bitstream to peptides",
            _preview_text(encoded.bits),
            _peptides_preview(mapping.peptides),
            f"{len(mapping.peptides)} peptide(s), pad_bits={mapping.pad_bits}",
            stage,
        )
    )

    recovered_bits = peptides_to_bits_fixed(
        mapping.peptides,
        peptide_length=mapping.peptide_length,
        index_aa_length=mapping.index_aa_length,
        total_peptides=len(mapping.peptides),
        pad_bits=mapping.pad_bits,
    )
    steps.append(
        _step(
            9,
            "Reconstruct fixed droplet bitstream",
            _peptides_preview(mapping.peptides),
            _preview_text(recovered_bits),
            f"{len(recovered_bits)} recovered bit(s)",
            stage,
        )
    )

    encoded.bits = recovered_bits
    decoded = fountain_decode(encoded)
    decoded_text = decoded.decode("utf-8", errors="replace")
    steps.append(
        _step(
            17,
            "Run LT peeling decode to recover payload",
            _preview_text(recovered_bits),
            _preview_text(decoded_text),
            f"{len(decoded)} decoded byte(s)",
            stage,
        )
    )

    result = {
        "encoder_label": "Fountain",
        "input_text": text,
        "decoded_text": decoded_text,
        "input_bytes": len(raw_bytes),
        "bit_length": len(encoded.bits),
        "peptide_count": len(mapping.peptides),
        "peptide_preview": _peptides_preview(mapping.peptides, limit=6),
        "success": decoded == raw_bytes,
        "droplet_count": encoded.droplet_count,
        "symbol_size": encoded.symbol_size,
    }
    return steps, result


def _build_codec_trace(
    encoder_key: str,
    text: str,
    cfg: PipelineConfig,
    overhead: float,
) -> tuple[list[TraceStep], dict[str, Any]]:
    if encoder_key == "huffman":
        return _build_codec_trace_huffman(text, cfg)
    if encoder_key == "yin_yang":
        return _build_codec_trace_yin_yang(text, cfg)
    return _build_codec_trace_fountain(text, cfg, overhead)


def _render_sources_expander() -> None:
    with st.expander("Project Source Code Used In This Visualizer"):
        st.caption("These are the exact backend functions.")
        st.code(inspect.getsource(drop_amino_acids), language="python")
        st.code(inspect.getsource(mutate_peptides), language="python")
        st.code(inspect.getsource(insert_aa_random_position), language="python")
        st.code(inspect.getsource(shuffle_amino_acids), language="python")
        st.code(inspect.getsource(drop_peptides), language="python")
        st.code(inspect.getsource(apply_peptide_errors), language="python")
        st.code(inspect.getsource(huffman_encode), language="python")
        st.code(inspect.getsource(huffman_decode), language="python")
        st.code(inspect.getsource(yin_yang_encode), language="python")
        st.code(inspect.getsource(yin_yang_decode), language="python")
        st.code(inspect.getsource(fountain_encode), language="python")
        st.code(inspect.getsource(fountain_decode), language="python")


# Render shared styles, then visualizer-specific styles
render_page_styles()
_render_visualizer_styles()

render_page_header(
    "Error Model Visualizer",
    "Interactive, step-by-step simulation of peptide corruption algorithms with live sequence state and code-line tracing.",
)
render_nav_pills("visualizer")

tab_error, tab_codec = st.tabs(["Error Model Visualizer", "Encode / Decode Visualizer"])

with tab_error:
    st.markdown("### Error Model Visualizer")
    st.caption("Configure parameters below, then run the step-by-step peptide corruption trace.")

    with st.form("errviz_form"):
        form_cols = st.columns(3)
        with form_cols[0]:
            algorithm_label = st.selectbox(
                "Algorithm",
                options=[
                    "Residue deletion",
                    "Residue substitution",
                    "Residue insertion",
                    "Local shuffle",
                    "Full error pipeline",
                ],
                index=4,
            )
        with form_cols[1]:
            example = st.selectbox("Example peptide", options=["Custom input", *EXAMPLE_PEPTIDES], index=1)
        with form_cols[2]:
            seed = st.number_input("Random seed", min_value=0, max_value=999999, value=42, step=1)

        default_input = "" if example == "Custom input" else example
        peptide_input = st.text_input(
            "Input peptide",
            value=default_input,
            placeholder="e.g. AVLSTFYEAVLSTFYE",
        )

        aux_cols = st.columns(2)
        with aux_cols[0]:
            alphabet = st.text_input("Alphabet", value=DEFAULT_ALPHABET)
        with aux_cols[1]:
            drop_empty = st.checkbox("Drop empty peptide after deletion", value=True)

        prob_cols = st.columns(5)
        with prob_cols[0]:
            loss_prob = st.slider("Deletion probability", min_value=0.0, max_value=1.0, value=0.12, step=0.01)
        with prob_cols[1]:
            mutation_prob = st.slider("Mutation probability", min_value=0.0, max_value=1.0, value=0.12, step=0.01)
        with prob_cols[2]:
            insertion_prob = st.slider("Insertion probability", min_value=0.0, max_value=1.0, value=0.08, step=0.01)
        with prob_cols[3]:
            shuffle_prob = st.slider("Shuffle probability", min_value=0.0, max_value=1.0, value=0.16, step=0.01)
        with prob_cols[4]:
            shuffle_passes = st.number_input("Shuffle passes", min_value=1, max_value=8, value=1, step=1)

        run_error = st.form_submit_button("Run Error Visualization", type="primary", use_container_width=True)

    algorithm_key = {
        "Residue deletion": "deletion",
        "Residue substitution": "substitution",
        "Residue insertion": "insertion",
        "Local shuffle": "shuffle",
        "Full error pipeline": "pipeline",
    }[algorithm_label]

    cleaned_peptide, removed_chars = _clean_peptide(peptide_input)
    alphabet_clean = "".join(ch for ch in alphabet.upper() if ch.isalpha()) or DEFAULT_ALPHABET

    if run_error:
        if not cleaned_peptide:
            st.error("Enter at least one amino-acid character for the peptide input.")
        else:
            cfg = {
                "alphabet": alphabet_clean,
                "seed": int(seed),
                "loss_prob": float(loss_prob),
                "mutation_prob": float(mutation_prob),
                "insertion_prob": float(insertion_prob),
                "shuffle_prob": float(shuffle_prob),
                "shuffle_passes": int(shuffle_passes),
                "drop_empty": bool(drop_empty),
            }
            trace, final_peptide = _build_trace(
                algorithm_key=algorithm_key,
                peptide=cleaned_peptide,
                cfg=cfg,
            )
            st.session_state["errviz_payload"] = {
                "trace": trace,
                "algorithm_key": algorithm_key,
                "algorithm_label": algorithm_label,
                "cfg": cfg,
                "input": cleaned_peptide,
                "final": final_peptide,
                "removed_chars": removed_chars,
            }
            st.session_state["errviz_step"] = 0

    if "errviz_payload" not in st.session_state:
        st.info("Configure inputs and run the error visualization.")
    else:
        payload = st.session_state["errviz_payload"]
        trace: list[TraceStep] = payload["trace"]
        if not trace:
            st.warning("No trace steps generated.")
        else:
            removed_chars_payload = payload.get("removed_chars", "")
            if removed_chars_payload:
                st.caption(f"Non-letter characters ignored in input: `{removed_chars_payload}`")

            active_step = int(st.session_state.get("errviz_step", 0))
            active_step = min(max(active_step, 0), len(trace) - 1)
            st.session_state["errviz_step"] = active_step

            summary_cols = st.columns(4)
            summary_cols[0].metric("Algorithm", payload["algorithm_label"])
            summary_cols[1].metric("Steps", len(trace))
            summary_cols[2].metric("Input length", len(payload["input"]))
            summary_cols[3].metric("Final length", len(payload["final"]))

            nav_cols = st.columns([1, 1, 6])
            with nav_cols[0]:
                if st.button("Prev", use_container_width=True, key="errviz_prev"):
                    st.session_state["errviz_step"] = max(0, active_step - 1)
                    st.rerun()
            with nav_cols[1]:
                if st.button("Next", use_container_width=True, key="errviz_next"):
                    st.session_state["errviz_step"] = min(len(trace) - 1, active_step + 1)
                    st.rerun()
            with nav_cols[2]:
                selected = st.slider(
                    "Step",
                    min_value=1,
                    max_value=len(trace),
                    value=st.session_state["errviz_step"] + 1,
                    format="%d",
                    key="errviz_slider",
                )
                if selected - 1 != st.session_state["errviz_step"]:
                    st.session_state["errviz_step"] = selected - 1
                    st.rerun()

            step = trace[st.session_state["errviz_step"]]
            left, right = st.columns([1.15, 1], gap="large")

            with left:
                changed = _count_changed_positions(step.before, step.after)
                st.markdown(
                    f"""
<div class="trace-card">
  <h4>Step {st.session_state["errviz_step"] + 1}: {html.escape(step.event)}</h4>
  <p>{html.escape(step.detail)}</p>
  <div style="margin-top:0.8rem;">
    {_sequence_row_html("Before", step.before, step.after)}
    {_sequence_row_html("After", step.after, step.before)}
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )
                a, b, c = st.columns(3)
                a.metric("Changed positions", changed)
                b.metric("Before length", len(step.before))
                c.metric("After length", len(step.after))

            with right:
                st.markdown("#### Code Trace")
                st.caption(f"Highlighted line: `{step.line_no}`")
                st.markdown(
                    _render_code_panel(CODE_SNIPPETS[payload["algorithm_key"]], step.line_no),
                    unsafe_allow_html=True,
                )

            st.markdown("#### Timeline")
            timeline_rows = [
                {
                    "Step": idx + 1,
                    "Line": t.line_no,
                    "Event": t.event,
                    "Before": t.before,
                    "After": t.after,
                    "Detail": t.detail,
                }
                for idx, t in enumerate(trace)
            ]
            st.dataframe(timeline_rows, use_container_width=True, hide_index=True, height=320)

            st.markdown("#### Example Python Usage")
            st.code(
                f"""# Reproducible config used in this run
cfg = {payload["cfg"]}
peptide = "{payload["input"]}"
algorithm = "{payload["algorithm_key"]}"
""",
                language="python",
            )

    _render_sources_expander()

with tab_codec:
    st.markdown("### Encode/Decode Pipeline Visualizer")
    st.caption("Step through text -> bits -> encoder mapping -> peptides -> decoder output for Huffman, Yin-Yang, and Fountain.")

    with st.form("encviz_form"):
        form_cols = st.columns(3)
        with form_cols[0]:
            codec_label = st.selectbox(
                "Encoder",
                options=["Huffman", "Yin-Yang", "Fountain"],
                index=0,
            )
        with form_cols[1]:
            peptide_length_codec = int(st.number_input("Peptide length", min_value=4, max_value=64, value=18, step=1))
        with form_cols[2]:
            index_aa_codec = int(st.number_input("Index AA length", min_value=0, max_value=20, value=0, step=1))

        text_input_codec = st.text_area(
            "Text input",
            value="Peptide encoding visualizer demo.",
            height=130,
            placeholder="Enter UTF-8 text to encode and decode step by step.",
        )

        f_cols = st.columns(3)
        with f_cols[0]:
            overhead_codec = float(st.slider("Fountain overhead", min_value=0.0, max_value=1.5, value=0.10, step=0.01))
        with f_cols[1]:
            symbol_size_codec = int(st.number_input("Fountain symbol size (bytes)", min_value=1, max_value=64, value=17, step=1))
        with f_cols[2]:
            fountain_seed_codec = int(st.number_input("Fountain seed", min_value=0, max_value=999999, value=42, step=1))

        run_codec = st.form_submit_button("Run Encode/Decode Visualization", type="primary", use_container_width=True)

    codec_key = {
        "Huffman": "huffman",
        "Yin-Yang": "yin_yang",
        "Fountain": "fountain",
    }[codec_label]

    if run_codec:
        if not text_input_codec.strip():
            st.error("Enter input text for encode/decode visualization.")
        elif index_aa_codec >= peptide_length_codec:
            st.error("`Index AA length` must be smaller than `Peptide length`.")
        else:
            cfg_obj = PipelineConfig(
                encoder=codec_key,
                peptide_length=peptide_length_codec,
                index_aa_length=index_aa_codec,
                fountain_symbol_size=symbol_size_codec,
                fountain_seed=fountain_seed_codec,
            )
            try:
                trace, result = _build_codec_trace(codec_key, text_input_codec, cfg_obj, overhead_codec)
            except Exception as exc:
                st.error(f"Failed to build trace: {exc}")
            else:
                st.session_state["encviz_payload"] = {
                    "trace": trace,
                    "encoder_key": codec_key,
                    "encoder_label": codec_label,
                    "cfg": cfg_obj,
                    "overhead": overhead_codec,
                    "result": result,
                }
                st.session_state["encviz_step"] = 0

    if "encviz_payload" not in st.session_state:
        st.info("Configure inputs and run the encode/decode visualizer.")
    else:
        codec_payload = st.session_state["encviz_payload"]
        codec_trace: list[TraceStep] = codec_payload["trace"]
        result = codec_payload["result"]
        if not codec_trace:
            st.warning("No encode/decode trace generated.")
        else:
            active_step = int(st.session_state.get("encviz_step", 0))
            active_step = min(max(active_step, 0), len(codec_trace) - 1)
            st.session_state["encviz_step"] = active_step

            metric_cols = st.columns(4)
            metric_cols[0].metric("Encoder", codec_payload["encoder_label"])
            metric_cols[1].metric("Input bytes", int(result["input_bytes"]))
            metric_cols[2].metric("Encoded bits", int(result["bit_length"]))
            metric_cols[3].metric("Peptides", int(result["peptide_count"]))
            if "droplet_count" in result:
                extra_cols = st.columns(2)
                extra_cols[0].metric("Droplets", int(result["droplet_count"]))
                extra_cols[1].metric("Symbol bytes", int(result["symbol_size"]))

            if result["success"]:
                st.success("Decoded output matches input.")
            else:
                st.warning("Decoded output differs from input. Check trace steps and config.")

            nav_cols = st.columns([1, 1, 6])
            with nav_cols[0]:
                if st.button("Prev", use_container_width=True, key="encviz_prev"):
                    st.session_state["encviz_step"] = max(0, active_step - 1)
                    st.rerun()
            with nav_cols[1]:
                if st.button("Next", use_container_width=True, key="encviz_next"):
                    st.session_state["encviz_step"] = min(len(codec_trace) - 1, active_step + 1)
                    st.rerun()
            with nav_cols[2]:
                selected = st.slider(
                    "Step",
                    min_value=1,
                    max_value=len(codec_trace),
                    value=st.session_state["encviz_step"] + 1,
                    format="%d",
                    key="encviz_slider",
                )
                if selected - 1 != st.session_state["encviz_step"]:
                    st.session_state["encviz_step"] = selected - 1
                    st.rerun()

            step = codec_trace[st.session_state["encviz_step"]]
            left, right = st.columns([1.15, 1], gap="large")
            with left:
                st.markdown(
                    f"""
<div class="trace-card">
  <h4>Step {st.session_state["encviz_step"] + 1}: {html.escape(step.event)}</h4>
  <p>{html.escape(step.detail)}</p>
  <div style="margin-top:0.8rem;">
    {_flow_row_html("Before", step.before)}
    {_flow_row_html("After", step.after)}
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns(3)
                c1.metric("Line", step.line_no)
                c2.metric("Before chars", len(step.before))
                c3.metric("After chars", len(step.after))

            with right:
                st.markdown("#### Code Trace")
                st.caption(f"Highlighted line: `{step.line_no}`")
                st.markdown(
                    _render_code_panel(CODE_SNIPPETS_CODEC[codec_payload["encoder_key"]], step.line_no),
                    unsafe_allow_html=True,
                )

            st.markdown("#### Timeline")
            timeline_rows = [
                {
                    "Step": idx + 1,
                    "Line": t.line_no,
                    "Event": t.event,
                    "Before": _preview_text(t.before, 120),
                    "After": _preview_text(t.after, 120),
                    "Detail": t.detail,
                }
                for idx, t in enumerate(codec_trace)
            ]
            st.dataframe(timeline_rows, use_container_width=True, hide_index=True, height=300)

            st.markdown("#### Decoded Text")
            st.code(result["decoded_text"], language="text")
            st.markdown("#### Peptide Preview")
            st.code(result["peptide_preview"], language="text")

            st.markdown("#### Example Python Usage")
            st.code(
                f"""text = {result["input_text"]!r}
cfg = PipelineConfig(peptide_length={codec_payload["cfg"].peptide_length}, index_aa_length={codec_payload["cfg"].index_aa_length})
encoder = "{codec_payload["encoder_key"]}"
fountain_overhead = {codec_payload["overhead"]}
""",
                language="python",
            )
