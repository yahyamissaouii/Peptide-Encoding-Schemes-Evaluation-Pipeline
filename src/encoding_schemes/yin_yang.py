from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from src.encoding_schemes.peptide_mapping import BITS_TO_AA
from src.pipeline.config import PipelineConfig
from src.utils.bits_bytes_utils import bitstring_to_bytes, bytes_to_bitstring


DEFAULT_ALPHABET = "AVLSTFYE"

# Yin–Yang-style redundant mapping (2 bits per residue) using the same 8-AA alphabet.
#
# Each 2-bit symbol maps to a *pair* of amino acids. The decoder maps both
# members of the pair back to the same 2-bit value, so the encoder is free to
# choose variants that satisfy offline rules (run-length, composition, etc.)
YY_PAIRS: Dict[str, Tuple[str, str]] = {
    "00": ("F", "E"),
    "01": ("Y", "S"),
    "10": ("V", "T"),
    "11": ("L", "A"),
}

YY_AA_TO_BITS: Dict[str, str] = {}
for bits, pair in YY_PAIRS.items():
    for aa in pair:
        if aa in YY_AA_TO_BITS:
            raise ValueError(f"Duplicate AA in YY pairs: {aa}")
        YY_AA_TO_BITS[aa] = bits


_AROMATIC = {"F", "Y"}
_STRONG_HYDROPHOBIC = {"V", "L", "F", "Y"}


@dataclass
class YinYangEncoded:
    peptides: List[str]
    pad_bits: int
    peptide_length: int
    index_aa_length: int
    original_size_bytes: int
    scheme_id: str = "yy_pairs_v1"


def _suffix_run_len(current: str, predicate, candidate: str) -> int:
    if not predicate(candidate):
        return 0
    run = 1
    for ch in reversed(current):
        if predicate(ch):
            run += 1
        else:
            break
    return run


def _suffix_same_len(current: str, candidate: str) -> int:
    run = 1
    for ch in reversed(current):
        if ch == candidate:
            run += 1
        else:
            break
    return run


def _choose_variant(
    candidates: Tuple[str, str],
    current_payload: str,
    payload_len: int,
) -> str:
    # Rule parameters tuned for peptide_length ~= 18, but work for other lengths.
    aro_cap = max(1, min(3, payload_len // 6))  # ~2-3 aromatics per 18-mer
    e_cap = max(2, min(6, payload_len // 3))    # allow some E, avoid all-E

    def penalty(aa: str) -> float:
        pen = 0.0

        same_run = _suffix_same_len(current_payload, aa)
        if same_run > 2:
            pen += 1000.0

        hydro_run = _suffix_run_len(current_payload, lambda x: x in _STRONG_HYDROPHOBIC, aa)
        if hydro_run > 2:
            pen += 1000.0

        e_run = _suffix_run_len(current_payload, lambda x: x == "E", aa)
        if e_run > 2:
            pen += 1000.0

        aro_count = sum(1 for ch in current_payload if ch in _AROMATIC) + (1 if aa in _AROMATIC else 0)
        if aro_count > aro_cap:
            pen += 1000.0

        e_count = current_payload.count("E") + (1 if aa == "E" else 0)
        if e_count > e_cap:
            pen += 1000.0

        # Soft preferences: bias toward polar/acidic variants to reduce hydrophobicity.
        if aa in _STRONG_HYDROPHOBIC:
            pen += 1.0
        if aa in _AROMATIC:
            pen += 0.5
        if aa == "E":
            pen += 0.2
        if aa in {"S", "T"}:
            pen -= 0.2

        # Avoid immediate repeats when possible.
        if current_payload and aa == current_payload[-1]:
            pen += 0.8

        return pen

    a0, a1 = candidates
    p0 = penalty(a0)
    p1 = penalty(a1)
    return a0 if p0 <= p1 else a1


def _index_prefix(idx: int, index_aa_length: int) -> str:
    if index_aa_length <= 0:
        return ""
    index_bits_len = index_aa_length * 3
    index_bits = f"{idx:0{index_bits_len}b}"
    return "".join(BITS_TO_AA[index_bits[i:i + 3]] for i in range(0, index_bits_len, 3))


def yin_yang_encode(data: bytes, cfg: PipelineConfig) -> YinYangEncoded:
    """
    Offline Yin–Yang-style encoder for peptides (no online scoring).

    - Converts bytes -> bitstring.
    - Encodes 2 bits per residue using YY_PAIRS, choosing variants via offline rules.
    - Chunks residues into peptides (optionally prefixing an index using the 3-bit AA mapping).
    """
    bits = bytes_to_bitstring(data)
    original_size = len(data)

    # Pad to a multiple of 2 bits (since we store 2 bits per residue).
    pad_bits = (2 - (len(bits) % 2)) % 2
    if pad_bits:
        bits += "0" * pad_bits

    payload_len = cfg.peptide_length - cfg.index_aa_length
    if payload_len <= 0:
        raise ValueError("peptide_length must be greater than index_aa_length.")

    payload_peptides: List[str] = []
    current_payload = ""

    for i in range(0, len(bits), 2):
        symbol = bits[i:i + 2]
        candidates = YY_PAIRS[symbol]
        aa = _choose_variant(candidates, current_payload, payload_len)
        current_payload += aa
        if len(current_payload) >= payload_len:
            payload_peptides.append(current_payload[:payload_len])
            current_payload = ""

    if current_payload:
        payload_peptides.append(current_payload)

    if cfg.index_aa_length:
        index_bits_len = cfg.index_aa_length * 3
        max_peptides = 1 << index_bits_len
        if len(payload_peptides) > max_peptides:
            raise ValueError("index_aa_length is too small for the number of peptides.")
        peptides = [_index_prefix(i, cfg.index_aa_length) + p for i, p in enumerate(payload_peptides)]
    else:
        peptides = payload_peptides

    return YinYangEncoded(
        peptides=peptides,
        pad_bits=pad_bits,
        peptide_length=cfg.peptide_length,
        index_aa_length=cfg.index_aa_length,
        original_size_bytes=original_size,
    )


def yin_yang_decode(encoded: YinYangEncoded) -> bytes:
    """
    Decode YinYangEncoded peptides back to bytes.
    """
    payloads: List[str] = []
    for pep in encoded.peptides:
        if encoded.index_aa_length and len(pep) >= encoded.index_aa_length:
            payloads.append(pep[encoded.index_aa_length:])
        elif not encoded.index_aa_length:
            payloads.append(pep)

    bits_list: List[str] = []
    for aa in "".join(payloads):
        if aa not in YY_AA_TO_BITS:
            raise ValueError(f"Unknown amino acid '{aa}' for Yin-Yang mapping.")
        bits_list.append(YY_AA_TO_BITS[aa])

    bits = "".join(bits_list)
    if encoded.pad_bits:
        bits = bits[:-encoded.pad_bits]

    decoded = bitstring_to_bytes(bits)
    return decoded[: encoded.original_size_bytes]
