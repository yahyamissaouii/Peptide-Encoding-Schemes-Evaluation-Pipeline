"""
ECC registry to keep pipeline wiring simple.

Profiles are string keys that map to a pair of encode/decode functions.
"""

from typing import Callable, Dict, Sequence, Tuple, TYPE_CHECKING

from src.encoding_schemes.peptide_mapping import PeptideMappingResult
from src.error_correction.interleave import (
    interleave_bits,
    deinterleave_bits,
    interleave_sequence,
    deinterleave_sequence,
)

if TYPE_CHECKING:
    # Optional dependency (reedsolo) is only needed when RS profiles are used.
    from src.error_correction.reed_solomon import RSEncodedPeptides


EncodeFn = Callable[[str], str]
DecodeFn = Callable[[str], str]


def _pass_through(bits: str) -> str:
    return bits




# Peptide-level RS profile definitions: (parity_symbols, interleave_depth)
PEPTIDE_RS_PROFILES: Dict[str, Tuple[int, int]] = {
    "none": (0, 1),
    "rs4": (4, 1),
    "rs8": (8, 1),
    "rs16": (16, 1),
    "rs32": (32, 1),
    "rs64": (64, 1),
    "rs64_int4": (64, 4),

    "rs128": (128, 1),

    "rs200": (200, 1),
    "rs201" : (201, 1),
    "rs8_int4": (8, 4),
}
FOUNTAIN_PROFILES: Dict[str, float] = {
    "fnt05": 0.5,
    "fnt10": 1.0,
    "fnt20": 2.0,
    "fnt30": 3.0,
    "fnt50": 5.0,
    "fnt75": 7.5,
    "fnt100": 10.0,
    "fnt150": 15.0,
    "fnt200": 20.0,
}

"""
FOUNTAIN_PROFILES: Dict[str, float] = {
    "fnt05": 0.05,
    "fnt10": 0.10,
    "fnt20": 0.20,
    "fnt30": 0.30,
    "fnt50": 0.50,
    "fnt75": 0.75,
    "fnt100": 1.00,
    "fnt150": 1.50,
    "fnt200": 20.00,
}
"""

def get_fountain_overhead(profile: str, fallback: float) -> float:
    return FOUNTAIN_PROFILES.get(profile.lower(), fallback)




def ecc_encode_peptides(mapping: PeptideMappingResult, profile: str = "none") -> "RSEncodedPeptides":
    """
    Encode peptide sequences with ECC, treating each peptide as a single RS symbol.
    """
    # Lazy import so fountain-only runs don't require reedsolo installed.
    from src.error_correction.reed_solomon import rs_encode_peptides

    profile = profile.lower()
    if profile not in PEPTIDE_RS_PROFILES:
        raise ValueError(f"Unsupported ECC profile: {profile}")

    parity_symbols, depth = PEPTIDE_RS_PROFILES[profile]
    peptides = mapping.peptides
    lengths = [len(p) for p in peptides]

    if depth > 1:
        peptides = interleave_sequence(peptides, depth=depth)
        lengths = interleave_sequence(lengths, depth=depth)

    interleaved_mapping = PeptideMappingResult(
        peptides=peptides,
        pad_bits=mapping.pad_bits,
        peptide_length=mapping.peptide_length,
        index_aa_length=mapping.index_aa_length,
    )
    encoded = rs_encode_peptides(interleaved_mapping, parity_symbols=parity_symbols)
    encoded.data_lengths = lengths
    encoded.interleave_depth = depth
    return encoded


def ecc_decode_peptides(
    received_peptides: Sequence[str],
    encoded: "RSEncodedPeptides",
    profile: str = "none",
) -> PeptideMappingResult:
    """
    Decode peptide sequences that were protected by `ecc_encode_peptides`.
    """
    # Lazy import so fountain-only runs don't require reedsolo installed.
    from src.error_correction.reed_solomon import rs_decode_peptides

    profile = profile.lower()
    if profile not in PEPTIDE_RS_PROFILES:
        raise ValueError(f"Unsupported ECC profile: {profile}")

    rs_recovered = rs_decode_peptides(received_peptides, encoded)

    if encoded.interleave_depth > 1:
        restored = deinterleave_sequence(rs_recovered.peptides, depth=encoded.interleave_depth)
        return PeptideMappingResult(
            peptides=restored,
            pad_bits=rs_recovered.pad_bits,
            peptide_length=rs_recovered.peptide_length,
            index_aa_length=rs_recovered.index_aa_length,
        )

    return rs_recovered
