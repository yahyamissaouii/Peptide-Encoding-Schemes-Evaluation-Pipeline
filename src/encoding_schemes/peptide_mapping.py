from dataclasses import dataclass
from typing import List


BITS_TO_AA = {
    "000": "A",
    "001": "V",
    "010": "L",
    "011": "S",
    "100": "T",
    "101": "F",
    "110": "Y",
    "111": "E",
}

AA_TO_BITS = {aa: bits for bits, aa in BITS_TO_AA.items()}


@dataclass
class PeptideMappingResult:
    """
    Result of mapping a bitstring to peptide sequences.

    """
    peptides: List[str]
    pad_bits: int
    peptide_length: int
    index_aa_length: int = 0


def _chunk_string(s: str, size: int) -> List[str]:
    """Split a string into chunks of length `size`."""
    return [s[i:i + size] for i in range(0, len(s), size)]


def bits_to_peptides(
    bits: str,
    peptide_length: int = 18,
    index_aa_length: int = 0,
    pad_to_full_peptide: bool = False,
) -> PeptideMappingResult:
    """
    Map a bitstring to peptide sequences.

    """
    if not set(bits).issubset({"0", "1"}):
        raise ValueError("bits_to_peptides expects a bitstring containing only '0' and '1'.")
    if index_aa_length < 0 or index_aa_length > peptide_length:
        raise ValueError("index_aa_length must be between 0 and peptide_length.")

    # Step 1: pad bits to multiple of 3
    remainder = len(bits) % 3
    pad_bits = (3 - remainder) % 3  # 0, 1 or 2
    if pad_bits:
        bits += "0" * pad_bits

    # Step 2: bits → amino acids
    aa_chars = []
    for i in range(0, len(bits), 3):
        triplet = bits[i:i + 3]
        aa = BITS_TO_AA[triplet]
        aa_chars.append(aa)
    aa_string = "".join(aa_chars)

    # Optional: pad to full peptide payload length (useful for fixed-size packet mapping).
    payload_len = peptide_length - index_aa_length
    if payload_len <= 0:
        raise ValueError("peptide_length must be greater than index_aa_length.")
    if pad_to_full_peptide and aa_string:
        remainder = len(aa_string) % payload_len
        if remainder:
            pad_aas = payload_len - remainder
            aa_string += "A" * pad_aas
            pad_bits += pad_aas * 3

    # Step 3: split into peptides (optionally prefix with index)
    payload_chunks = _chunk_string(aa_string, payload_len)

    if index_aa_length:
        index_bits_len = index_aa_length * 3
        max_peptides = 1 << index_bits_len
        if len(payload_chunks) > max_peptides:
            raise ValueError("index_aa_length is too small for the number of peptides.")

        peptides: List[str] = []
        for idx, chunk in enumerate(payload_chunks):
            index_bits = f"{idx:0{index_bits_len}b}"
            index_aas = "".join(
                BITS_TO_AA[index_bits[i:i + 3]] for i in range(0, index_bits_len, 3)
            )
            peptides.append(index_aas + chunk)
    else:
        peptides = _chunk_string(aa_string, peptide_length)

    return PeptideMappingResult(
        peptides=peptides,
        pad_bits=pad_bits,
        peptide_length=peptide_length,
        index_aa_length=index_aa_length,
    )


def peptides_to_bits(mapping_result: PeptideMappingResult) -> str:
    """
    Reverse mapping: peptide sequences → original bitstring.

    """
    if mapping_result.index_aa_length:
        aa_string = "".join(
            pep[mapping_result.index_aa_length:]
            if len(pep) >= mapping_result.index_aa_length
            else ""
            for pep in mapping_result.peptides
        )
    else:
        aa_string = "".join(mapping_result.peptides)

    bits_list = []
    for aa in aa_string:
        if aa not in AA_TO_BITS:
            raise ValueError(f"Unknown amino acid '{aa}' for this mapping.")
        bits_list.append(AA_TO_BITS[aa])

    bits = "".join(bits_list)

    # Remove padding bits at the end
    if mapping_result.pad_bits:
        bits = bits[:-mapping_result.pad_bits]

    return bits


def peptides_to_bits_fixed(
    peptides: List[str],
    peptide_length: int,
    index_aa_length: int,
    total_peptides: int,
    pad_bits: int,
) -> str:
    """
    Reconstruct a fixed-length bitstring from possibly missing/short peptides.

    Missing indices are filled with zero bits to preserve alignment.
    """
    payload_len = peptide_length - index_aa_length
    if payload_len <= 0:
        raise ValueError("peptide_length must be greater than index_aa_length.")
    payload_bits_per_peptide = payload_len * 3
    chunks = ["0" * payload_bits_per_peptide for _ in range(total_peptides)]
    seen = [False] * total_peptides

    for pos, pep in enumerate(peptides):
        if index_aa_length:
            if len(pep) < index_aa_length:
                continue
            if any(aa not in AA_TO_BITS for aa in pep[:index_aa_length]):
                continue
            idx_bits = "".join(AA_TO_BITS[aa] for aa in pep[:index_aa_length])
            idx = int(idx_bits, 2)
            if idx >= total_peptides or seen[idx]:
                continue
            payload_aas = pep[index_aa_length:]
        else:
            if pos >= total_peptides or seen[pos]:
                continue
            idx = pos
            payload_aas = pep

        payload_bits = "".join(AA_TO_BITS.get(aa, "000") for aa in payload_aas)
        if len(payload_bits) < payload_bits_per_peptide:
            payload_bits = payload_bits.ljust(payload_bits_per_peptide, "0")
        elif len(payload_bits) > payload_bits_per_peptide:
            payload_bits = payload_bits[:payload_bits_per_peptide]

        chunks[idx] = payload_bits
        seen[idx] = True

    bitstream = "".join(chunks)
    if pad_bits:
        bitstream = bitstream[:-pad_bits]
    return bitstream
