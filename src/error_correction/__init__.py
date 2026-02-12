"""
Placeholder error-correction package.

This module is intentionally minimal so we can wire ECC into the pipeline
incrementally. Implementations will be added in follow-up steps.
"""

from src.error_correction.registry import (
    # ecc_encode_bits,
    # ecc_decode_bits,
    ecc_encode_peptides,
    ecc_decode_peptides,
)

# RS is an optional dependency; importing the package should not fail for
# fountain-only experiments.
try:
    from src.error_correction.reed_solomon import RSEncodedPeptides  # type: ignore
except ImportError:  # pragma: no cover
    RSEncodedPeptides = None  # type: ignore

__all__ = [
 #   "ecc_encode_bits",
 #   "ecc_decode_bits",
    "ecc_encode_peptides",
    "ecc_decode_peptides",
    "RSEncodedPeptides",
]
