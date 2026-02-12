import os
import random

from src.error_correction.reed_solomon import _peptide_to_symbol_bytes, _symbol_bytes_to_peptide

L = 12  # or whatever your peptide_length is
for _ in range(100):
    # random "symbol" as bytes
    original_bytes = os.urandom((3 * L + 7) // 8)

    # bytes -> peptide
    pep = _symbol_bytes_to_peptide(original_bytes, aa_length=L, target_length=L)

    # peptide -> bytes
    recovered_bytes, _ = _peptide_to_symbol_bytes(pep, target_length=L)

    if recovered_bytes != original_bytes:
        print("Mismatch for L =", L)
        break


for L in (8, 12,18, 16, 24):
    print("Testing L =", L)
    ok = True
    for _ in range(100):
        original_bytes = os.urandom((3 * L + 7) // 8)
        pep = _symbol_bytes_to_peptide(original_bytes, aa_length=L, target_length=L)
        recovered_bytes, _ = _peptide_to_symbol_bytes(pep, target_length=L)
        if recovered_bytes != original_bytes:
            print("  Mismatch for L =", L)
            ok = False
            break
    if ok:
        print("  Round-trip OK for L =", L)
