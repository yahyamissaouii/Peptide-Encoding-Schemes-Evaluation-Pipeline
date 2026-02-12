"""
Reed–Solomon encode/decode wrappers backed by the `reedsolo` library.

Supports both legacy byte-aligned bitstrings and peptide-level symbols
(treating each peptide sequence as one RS symbol).
"""

import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from math import ceil
from typing import List, Optional, Sequence, Tuple

from reedsolo import RSCodec, ReedSolomonError

from src.encoding_schemes.peptide_mapping import AA_TO_BITS, BITS_TO_AA, PeptideMappingResult
from src.utils.bits_bytes_utils import bitstring_to_bytes, bytes_to_bitstring
from src.error_correction.interleave import interleave_sequence

# Debug logging controlled by environment variable ECC_DEBUG
_DEBUG = os.environ.get("ECC_DEBUG", "").lower() in {"1", "true", "yes"}


def _dbg(msg: str) -> None:
    if _DEBUG:
        print(f"[RS] {msg}", file=sys.stderr)


NUM_DATA_PEPTIDES = int(os.environ.get("NUM_DATA_PEPTIDES", "24"))
NUM_PARITY_PEPTIDES = int(os.environ.get("NUM_PARITY_PEPTIDES", "8"))


@lru_cache(maxsize=None)
def _get_codec(parity_symbols: int) -> RSCodec:
    if parity_symbols <= 0:
        raise ValueError("parity_symbols must be positive")
    return RSCodec(parity_symbols)


@dataclass
class PeptideMeta:
    block_id: int
    index_in_block: int
    is_parity: bool = False


@dataclass
class SymbolPadding:
    """
    Tracks how a peptide was padded to reach byte-aligned RS symbols.

    Attributes:
        data_bits: Number of meaningful data bits (amino-acid bits) in the symbol.
        padded_bits: Total bit length after byte-padding (always a multiple of 8).
        pad_offset: Bit position where padding starts inside the symbol bitstring.
        pad_bits: The exact padding bits that were inserted (may carry parity info).
    """
    data_bits: int
    padded_bits: int
    pad_offset: int
    pad_bits: str = ""


@dataclass
class RSEncodedPeptides:
    """
    Container for RS-protected peptide sequences.

    Attributes:
        peptides: Data peptides followed by parity peptides (already interleaved if used).
        data_lengths: Amino-acid length of each original data peptide (in RS order).
        pad_bits: Global pad bits used during bits→peptides mapping.
        peptide_length: Target peptide length used for padding during ECC.
        index_aa_length: Amino-acid length reserved for peptide indexing.
        parity_symbols: Number of parity symbols used for RS.
        interleave_depth: Applied interleaving depth (kept for decode and debugging).
        metadata: Per-peptide metadata for block-level grouping.
        data_block_size: Number of data peptides per RS block.
        padding: Per-peptide padding metadata aligned with `peptides`.
    """
    peptides: List[str]
    data_lengths: List[int]
    pad_bits: int
    peptide_length: int
    parity_symbols: int
    index_aa_length: int = 0
    interleave_depth: int = 1
    metadata: List[PeptideMeta] = field(default_factory=list)
    data_block_size: int = NUM_DATA_PEPTIDES
    padding: List[SymbolPadding] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Bit-level RS (legacy, byte symbols)
# ---------------------------------------------------------------------------


def rs_encode_blocks(bits: str, parity_symbols: int = 4) -> str:
    """
    Add RS parity to a byte-aligned bitstring using reedsolo.RSCodec.
    """
    if parity_symbols <= 0:
        return bits

    msg = bitstring_to_bytes(bits)
    codec = _get_codec(parity_symbols)
    print(f"encode len={len(msg)} parity={parity_symbols}")
    encoded = codec.encode(msg)
    return bytes_to_bitstring(encoded)


def rs_decode_blocks(bits: str, parity_symbols: int = 4) -> str:
    """
    Decode/correct RS-protected byte-aligned bitstring and strip parity.
    On decode failure, returns data without correction (parity stripped). This
    keeps the pipeline running even when correction is not possible.
    """
    if parity_symbols <= 0:
        return bits

    msg = bitstring_to_bytes(bits)
    codec = _get_codec(parity_symbols)
    print(f"decode len={len(msg)} parity={parity_symbols}")
    try:
        decoded = codec.decode(msg)
        decoded_bytes = decoded[0] if isinstance(decoded, tuple) else decoded
        print("decode corrected successfully")
        return bytes_to_bitstring(decoded_bytes)
    except ReedSolomonError as err:
        print(f"decode failed: {err}")
    except Exception as err:
        print(f"decode failed: {err}")

    data_only = msg[:-parity_symbols] if parity_symbols <= len(msg) else msg
    return bytes_to_bitstring(data_only)



# ---------------------------------------------------------------------------
# Peptide-level RS: one peptide == one RS symbol
# ---------------------------------------------------------------------------

def _peptide_to_symbol_bytes(
    peptide: str,
    target_length: int,
    pad_info: Optional[SymbolPadding] = None,
) -> Tuple[bytes, SymbolPadding]:
    """
    Convert a peptide string into a fixed-length byte representation.

    When pad_info is provided, its padding bits/length are reused so we can
    reconstruct the exact byte-aligned symbol used during encoding (important
    when target_length*3 is not byte-aligned).

    Returns (symbol_bytes, padding_info).
    """
    symbol_bits = target_length * 3
    aa_bits: List[str] = []
    data_bits = min(len(peptide), target_length) * 3

    # Trim to target length if the peptide was extended by the error model
    trimmed = peptide[:target_length]
    for aa in trimmed:
        aa_bits.append(AA_TO_BITS.get(aa, "000"))

    bits = "".join(aa_bits)
    if len(bits) < symbol_bits:
        bits += "0" * (symbol_bits - len(bits))
    else:
        bits = bits[:symbol_bits]

    if pad_info is None:
        pad_offset = symbol_bits
        pad_len = (8 - (len(bits) % 8)) % 8  # byte padding needed
        pad_bits = "0" * pad_len
        bits += pad_bits
        pad_info = SymbolPadding(
            data_bits=data_bits,
            padded_bits=len(bits),
            pad_offset=pad_offset,
            pad_bits=pad_bits,
        )
    else:
        pad_len = max(pad_info.padded_bits - pad_info.pad_offset, 0)
        pad_bits = pad_info.pad_bits or ("0" * pad_len)
        base = bits[:pad_info.pad_offset]
        bits = base + pad_bits[:pad_len]
        # Ensure final length matches stored metadata
        if len(bits) < pad_info.padded_bits:
            bits = bits.ljust(pad_info.padded_bits, "0")
        elif len(bits) > pad_info.padded_bits:
            bits = bits[:pad_info.padded_bits]

    # Pad to full bytes for reedsolo (metadata already expects byte-alignment)
    if len(bits) % 8:
        bits += "0" * (8 - (len(bits) % 8))
        pad_info.padded_bits = len(bits)

    return bitstring_to_bytes(bits), pad_info


def _symbol_bytes_to_peptide(
    symbol_bytes: bytes,
    aa_length: int,
    target_length: int,
    pad_info: Optional[SymbolPadding] = None,
) -> str:
    """
    Convert a fixed-length RS symbol back into a peptide string of length `aa_length`.
    """
    bits = bytes_to_bitstring(symbol_bytes)
    if pad_info:
        if len(bits) > pad_info.padded_bits:
            bits = bits[:pad_info.padded_bits]
        pad_len = max(pad_info.padded_bits - pad_info.pad_offset, 0)
        if pad_len and pad_info.pad_offset < len(bits):
            bits = bits[:pad_info.pad_offset] + bits[pad_info.pad_offset + pad_len:]
        total_bits = max(pad_info.data_bits, aa_length * 3)
    else:
        total_bits = target_length * 3
        if len(bits) < total_bits:
            bits = bits.ljust(total_bits, "0")
    bits = bits[:aa_length * 3]

    aas: List[str] = []
    for i in range(0, len(bits), 3):
        chunk = bits[i:i + 3]
        aas.append(BITS_TO_AA.get(chunk, "A"))
    return "".join(aas)


def _max_rs_symbols(codec: RSCodec) -> int:
    # reedsolo exposes `nsize` on RSCodec; fall back to 255 when absent.
    return getattr(codec, "nsize", 255)


def chunk_peptides(peptides: Sequence[str], k: int) -> List[List[str]]:
    """
    Split peptides into blocks of size `k` (last block may be shorter).
    """
    if k <= 0:
        raise ValueError("Chunk size k must be positive")
    return [list(peptides[i:i + k]) for i in range(0, len(peptides), k)]


def encode_rs_block(
    block: Sequence[str],
    parity_symbols: int,
    target_len: int,
) -> Tuple[List[str], List[SymbolPadding], List[SymbolPadding]]:
    """
    Encode a single RS block (data peptides only) and return parity peptides
    along with padding metadata for both data and parity symbols.
    """
    if parity_symbols <= 0 or not block:
        return [], [], []

    codec = _get_codec(parity_symbols)
    data_count = len(block)
    max_symbols = _max_rs_symbols(codec)
    if data_count + parity_symbols > max_symbols:
        raise ValueError(
            f"Too many symbols for one block: data={data_count}, parity={parity_symbols}, limit={max_symbols}"
        )

    symbol_bytes_list: List[bytes] = []
    data_padding: List[SymbolPadding] = []
    for peptide in block:
        sym_bytes, pad_info = _peptide_to_symbol_bytes(peptide, target_len)
        symbol_bytes_list.append(sym_bytes)
        data_padding.append(pad_info)
    symbol_byte_len = len(symbol_bytes_list[0]) if symbol_bytes_list else 0

    parity_matrix: List[List[int]] = [[0] * symbol_byte_len for _ in range(parity_symbols)]


    for byte_idx in range(symbol_byte_len):
        column = bytes(sym[byte_idx] for sym in symbol_bytes_list)
        encoded_col = codec.encode(column)
        parity_slice = encoded_col[data_count:]
        for p_idx, val in enumerate(parity_slice):
            parity_matrix[p_idx][byte_idx] = val

    parity_peptides: List[str] = []
    parity_padding: List[SymbolPadding] = []
    for parity_bytes in parity_matrix:
        parity_byte_str = bytes(parity_bytes)
        parity_bits = bytes_to_bitstring(parity_byte_str)
        pad_offset = target_len * 3
        pad_bits = parity_bits[pad_offset:] if len(parity_bits) > pad_offset else ""
        parity_padding.append(
            SymbolPadding(
                data_bits=pad_offset,
                padded_bits=len(parity_bits),
                pad_offset=pad_offset,
                pad_bits=pad_bits,
            )
        )
        parity_peptides.append(
            _symbol_bytes_to_peptide(parity_byte_str, target_len, target_len)
        )
    return parity_peptides, data_padding, parity_padding


def decode_rs_block(
    block_peptides: Sequence[str],
    parity_symbols: int,
    target_len: int,
    data_lengths: Sequence[int],
    block_padding: Optional[Sequence[Optional[SymbolPadding]]] = None,
    index_aa_length: int = 0,
    index_base: int = 0,
) -> List[str]:
    """
    Decode a single RS block (data + parity peptides) and return corrected data peptides.
    """
    data_count = len(data_lengths)
    if parity_symbols <= 0:
        return list(block_peptides[:data_count])

    codec = _get_codec(parity_symbols)
    expected_total = data_count + parity_symbols
    aligned = list(block_peptides[:expected_total])
    if len(aligned) < expected_total:
        aligned.extend([""] * (expected_total - len(aligned)))

    erase_pos: List[int] = []
    max_index_value = 1 << (index_aa_length * 3) if index_aa_length else 0
    for idx, pep in enumerate(aligned):
        if not pep:
            erase_pos.append(idx)
            continue
        if len(pep) > target_len:
            erase_pos.append(idx)
            continue
        if any(aa not in AA_TO_BITS for aa in pep):
            erase_pos.append(idx)
            continue
        if index_aa_length and idx < data_count:
            if len(pep) < index_aa_length:
                erase_pos.append(idx)
                continue
            index_bits = "".join(AA_TO_BITS[aa] for aa in pep[:index_aa_length])
            expected = index_base + idx
            if expected >= max_index_value or int(index_bits, 2) != expected:
                erase_pos.append(idx)

    symbol_bytes_list: List[bytes] = []
    for idx, pep in enumerate(aligned):
        pad_info = block_padding[idx] if block_padding and idx < len(block_padding) else None
        sym_bytes, _ = _peptide_to_symbol_bytes(pep, target_len, pad_info)
        symbol_bytes_list.append(sym_bytes)

    symbol_byte_len = len(symbol_bytes_list[0]) if symbol_bytes_list else 0
    recovered_bytes: List[List[int]] = [[0] * symbol_byte_len for _ in range(data_count)]

    failed_cols = 0

    for byte_idx in range(symbol_byte_len):
        column = bytes(sym[byte_idx] for sym in symbol_bytes_list)
        try:
            decoded_col = codec.decode(column, erase_pos=erase_pos)
            data_bytes = decoded_col[0] if isinstance(decoded_col, tuple) else decoded_col
        except Exception as err:
            print(f"decode block column {byte_idx} failed: {err}")
            data_bytes = column[:data_count]

        if failed_cols > 0:
            print(f"[BLOCK] block had {failed_cols} failed RS columns "
         f"(data={data_count}, parity={parity_symbols}, symbol_bytes={symbol_byte_len})")



        if len(data_bytes) > data_count:
            data_bytes = data_bytes[:data_count]

        for row_idx, val in enumerate(data_bytes):
            recovered_bytes[row_idx][byte_idx] = val

    corrected_peptides: List[str] = []
    for row_idx, (row_bytes, aa_len) in enumerate(zip(recovered_bytes, data_lengths)):
        pad_info = None
        if block_padding and row_idx < len(block_padding):
            pad_info = block_padding[row_idx]
        peptide = _symbol_bytes_to_peptide(bytes(row_bytes), aa_len, target_len, pad_info)
        corrected_peptides.append(peptide)

    return corrected_peptides


def recombine_blocks(blocks: Sequence[Sequence[str]]) -> List[str]:
    """
    Flatten decoded blocks back into a single peptide list.
    """
    combined: List[str] = []
    for blk in blocks:
        combined.extend(list(blk))
    return combined


def rs_encode_peptides(mapping: PeptideMappingResult, parity_symbols: int = 4) -> RSEncodedPeptides:
    """
    Apply RS parity where *each peptide sequence* is one RS symbol.

    The algorithm encodes column-wise across peptides in RS blocks so an entire
    peptide being corrupted counts as a single symbol error per column.
    """
    data_lengths = [len(p) for p in mapping.peptides]
    if not mapping.peptides:
        return RSEncodedPeptides(
            peptides=[],
            data_lengths=[],
            pad_bits=mapping.pad_bits,
            peptide_length=mapping.peptide_length,
            index_aa_length=mapping.index_aa_length,
            parity_symbols=0,
            metadata=[],
            data_block_size=NUM_DATA_PEPTIDES,
            padding=[],
        )

    target_len = mapping.peptide_length
    parity_per_block = parity_symbols if parity_symbols is not None else NUM_PARITY_PEPTIDES
    block_size = NUM_DATA_PEPTIDES

    data_blocks = chunk_peptides(mapping.peptides, block_size)
    length_blocks = chunk_peptides(data_lengths, block_size)

    out_peptides: List[str] = []
    out_meta: List[PeptideMeta] = []
    out_padding: List[SymbolPadding] = []

    for block_id, block in enumerate(data_blocks):
        # Data peptides
        for idx, pep in enumerate(block):
            out_peptides.append(pep)
            out_meta.append(PeptideMeta(block_id=block_id, index_in_block=idx, is_parity=False))

        # Parity peptides per block (with padding metadata)
        if parity_per_block > 0:
            parity_peptides, data_pad_info, parity_pad_info = encode_rs_block(block, parity_per_block, target_len)
        else:
            parity_peptides, parity_pad_info = [], []
            data_pad_info = []
            for pep in block:
                _, pad_info = _peptide_to_symbol_bytes(pep, target_len)
                data_pad_info.append(pad_info)

        out_padding.extend(data_pad_info)
        for p_idx, pep in enumerate(parity_peptides):
            out_peptides.append(pep)
            out_meta.append(
                PeptideMeta(
                    block_id=block_id,
                    index_in_block=len(block) + p_idx,
                    is_parity=True,
                )
            )
        out_padding.extend(parity_pad_info)

    return RSEncodedPeptides(
        peptides=out_peptides,
        data_lengths=data_lengths,
        pad_bits=mapping.pad_bits,
        peptide_length=target_len,
        index_aa_length=mapping.index_aa_length,
        parity_symbols=parity_per_block,
        metadata=out_meta,
        data_block_size=block_size,
        padding=out_padding,
    )


def rs_decode_peptides(
    received_peptides: Sequence[str],
    encoded: RSEncodedPeptides,
) -> PeptideMappingResult:
    """
    Decode RS-protected peptides that were encoded with `rs_encode_peptides`.
    Returns only the corrected *data* peptides (parity is stripped).
    """
    block_size = encoded.data_block_size or NUM_DATA_PEPTIDES
    parity_symbols = encoded.parity_symbols
    target_len = encoded.peptide_length

    use_index = encoded.index_aa_length > 0 and encoded.data_lengths
    index_bits_len = encoded.index_aa_length * 3
    total_data = len(encoded.data_lengths)

    data_by_index: dict[int, str] = {}
    index_map: Optional[dict[int, int]] = None
    used_positions: set[int] = set()

    if use_index and encoded.interleave_depth > 1:
        interleaved = interleave_sequence(list(range(total_data)), depth=encoded.interleave_depth)
        index_map = {orig_idx: inter_idx for inter_idx, orig_idx in enumerate(interleaved)}

    def _parse_index(pep: str) -> Optional[int]:
        if not use_index or len(pep) < encoded.index_aa_length:
            return None
        bits: List[str] = []
        for aa in pep[:encoded.index_aa_length]:
            if aa not in AA_TO_BITS:
                return None
            bits.append(AA_TO_BITS[aa])
        idx = int("".join(bits), 2)
        if idx >= total_data or idx >= (1 << index_bits_len):
            return None
        if index_map is not None:
            return index_map.get(idx)
        return idx

    # Pair incoming peptides with metadata (order-based fallback)
    meta_pairs: List[Tuple[int, str, PeptideMeta]] = []
    for idx, pep in enumerate(received_peptides):
        if idx >= len(encoded.metadata or []):
            break
        meta_pairs.append((idx, pep, encoded.metadata[idx]))

    if use_index:
        for pos, pep in enumerate(received_peptides):
            mapped_idx = _parse_index(pep)
            if mapped_idx is None or mapped_idx in data_by_index:
                continue
            data_by_index[mapped_idx] = pep
            used_positions.add(pos)

    def _fallback_padding(is_parity: bool, aa_len: int) -> SymbolPadding:
        symbol_bits = target_len * 3
        pad_len = (8 - (symbol_bits % 8)) % 8
        data_bits = symbol_bits if is_parity else aa_len * 3
        return SymbolPadding(
            data_bits=data_bits,
            padded_bits=symbol_bits + pad_len,
            pad_offset=symbol_bits,
            pad_bits="0" * pad_len,
        )

    num_blocks = ceil(len(encoded.data_lengths) / block_size) if block_size else 0
    length_blocks = chunk_peptides(encoded.data_lengths, block_size)

    recovered_blocks: List[List[str]] = []

    for block_id in range(num_blocks):
        data_lengths = length_blocks[block_id] if block_id < len(length_blocks) else []
        data_count = len(data_lengths)
        expected_total = data_count + parity_symbols

        block_entries: List[str] = [""] * expected_total
        block_padding: List[Optional[SymbolPadding]] = [None] * expected_total
        for meta_idx, meta in enumerate(encoded.metadata or []):
            if meta.block_id != block_id:
                continue
            if meta.index_in_block < expected_total:
                aa_len = (
                    data_lengths[meta.index_in_block]
                    if meta.index_in_block < len(data_lengths)
                    else target_len
                )
                if meta_idx < len(encoded.padding or []):
                    block_padding[meta.index_in_block] = encoded.padding[meta_idx]
                else:
                    block_padding[meta.index_in_block] = _fallback_padding(meta.is_parity, aa_len)

        if use_index:
            # Place data peptides by index (missing index => erasure)
            for idx in range(data_count):
                global_idx = block_id * block_size + idx
                block_entries[idx] = data_by_index.get(global_idx, "")

        for pos, pep, meta in meta_pairs:
            if use_index and pos in used_positions:
                continue
            if meta.block_id != block_id:
                continue
            if meta.index_in_block < expected_total and not block_entries[meta.index_in_block]:
                block_entries[meta.index_in_block] = pep

        erasure_index_len = encoded.index_aa_length if use_index and encoded.interleave_depth <= 1 else 0
        corrected_block = decode_rs_block(
            block_entries,
            parity_symbols,
            target_len,
            data_lengths,
            block_padding,
            index_aa_length=erasure_index_len,
            index_base=block_id * block_size,
        )
        recovered_blocks.append(corrected_block)

    combined = recombine_blocks(recovered_blocks)

    return PeptideMappingResult(
        peptides=combined,
        pad_bits=encoded.pad_bits,
        peptide_length=encoded.peptide_length,
        index_aa_length=encoded.index_aa_length,
    )



# Simple debug / self-test helpers

def _inject_byte_errors(encoded_bits: str, n_errors: int) -> str:
    """
    Flip entire bytes in the encoded bitstring to simulate symbol errors.
    This operates on bytes, since RSCodec works on byte symbols.
    """
    data = bytearray(bitstring_to_bytes(encoded_bits))
    if not data:
        return encoded_bits

    # Spread errors over the first n_errors bytes (wrapping if needed)
    for i in range(n_errors):
        idx = i % len(data)
        # Flip all bits in this byte
        data[idx] ^= 0xFF

    return bytes_to_bitstring(bytes(data))


def _self_test() -> None:
    """
    Basic round-trip tests demonstrating that:
    - parity is added,
    - correctable errors are fixed,
    with full debug printouts of internal bitstrings.
    """

    parity_symbols = 8  # reasonably strong for a short demo message
    message_bytes = b"Hello Reed-Solomon!"
    msg_bits = bytes_to_bitstring(message_bytes)

    print("=== RS self-test ===")
    print(f"Original message (bytes): {message_bytes!r}")
    print(f"Original message (string): {message_bytes.decode(errors='ignore')}")
    print(f"Original message bitstring ({len(msg_bits)} bits):")
    print(msg_bits)
    print()

    # --------------------------------------------------------------
    # Encode
    # --------------------------------------------------------------
    encoded_bits = rs_encode_blocks(msg_bits, parity_symbols=parity_symbols)
    encoded_bytes = bitstring_to_bytes(encoded_bits)

    print("=== ENCODING ===")
    print(f"Encoded length (bytes): {len(encoded_bytes)}")
    print(f"Data bytes: {len(message_bytes)}, parity bytes: {len(encoded_bytes) - len(message_bytes)}")
    print(f"Encoded bitstring ({len(encoded_bits)} bits):")
    print(encoded_bits)
    assert len(encoded_bytes) - len(message_bytes) == parity_symbols, "Parity bytes not as expected"
    print()

    # --------------------------------------------------------------
    # Decode with no errors
    # --------------------------------------------------------------
    decoded_bits = rs_decode_blocks(encoded_bits, parity_symbols=parity_symbols)
    decoded_bytes = bitstring_to_bytes(decoded_bits)

    print("=== DECODE (NO ERRORS) ===")
    print("Decoded bytes:", decoded_bytes)
    print("Decoded string:", decoded_bytes.decode(errors='ignore'))
    print("Decoded bitstring:")
    print(decoded_bits)
    print("Match OK:", decoded_bytes == message_bytes)
    assert decoded_bytes == message_bytes, "Round-trip without errors failed"
    print()

    # --------------------------------------------------------------
    # Introduce correctable errors
    # --------------------------------------------------------------
    correctable_errors = parity_symbols // 2
    corrupted_bits = _inject_byte_errors(encoded_bits, n_errors=correctable_errors)
    corrupted_bytes = bitstring_to_bytes(corrupted_bits)

    print("=== ERROR INJECTION ===")
    print(f"Introduced {correctable_errors} byte errors.")
    print("Corrupted bytes:", corrupted_bytes)
    print("Corrupted bitstring:")
    print(corrupted_bits)
    print()

    # --------------------------------------------------------------
    # Decode after errors
    # --------------------------------------------------------------
    decoded_err_bits = rs_decode_blocks(corrupted_bits, parity_symbols=parity_symbols)
    decoded_err_bytes = bitstring_to_bytes(decoded_err_bits)

    print("=== DECODE (AFTER ERROR CORRECTION) ===")
    print("Decoded-after-errors bytes:", decoded_err_bytes)
    print("Decoded-after-errors string:", decoded_err_bytes.decode(errors='ignore'))
    print("Decoded-after-errors bitstring:")
    print(decoded_err_bits)
    print("Corrected OK:", decoded_err_bytes == message_bytes)
    assert decoded_err_bytes == message_bytes, "RS failed to correct within its capability"
    print()

    print("=== RS self-test PASSED ===")

if __name__ == "__main__":
    # For extra debug logs, run:
    #   ECC_DEBUG=1 python this_module.py
    _self_test()
