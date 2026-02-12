from src.encoding_schemes.huffman import huffman_encode, huffman_decode
from src.encoding_schemes.peptide_mapping import bits_to_peptides, peptides_to_bits
from src.error_correction.registry import ecc_encode_peptides, ecc_decode_peptides
import src.error_correction.reed_solomon as rs


def test_rs_protects_entire_peptide_symbol():
    """
    A single corrupted peptide should be correctable when RS parity covers peptides.
    """
    data = b"peptide-rs-symbol"
    enc = huffman_encode(data)
    mapping = bits_to_peptides(enc.bits, peptide_length=6)

    encoded = ecc_encode_peptides(mapping, profile="rs4")

    # Corrupt one peptide (flip the first amino acid if present)
    corrupted = list(encoded.peptides)
    if corrupted and corrupted[0]:
        flipped = "V" if corrupted[0][0] != "V" else "A"
        corrupted[0] = flipped + corrupted[0][1:]

    recovered_mapping = ecc_decode_peptides(corrupted, encoded=encoded, profile="rs4")
    recovered_bits = peptides_to_bits(recovered_mapping)

    enc.bits = recovered_bits
    decoded = huffman_decode(enc)

    assert decoded == data


def test_rs_block_chunking_recovers_multiple_blocks():
    """
    Ensure block-level RS adds parity per block and still decodes when errors hit each block.
    """
    original_k = rs.NUM_DATA_PEPTIDES
    rs.NUM_DATA_PEPTIDES = 2  # force multiple blocks for a small payload
    try:
        data = b"block-chunk-test"
        enc = huffman_encode(data)
        mapping = bits_to_peptides(enc.bits, peptide_length=4)

        encoded = ecc_encode_peptides(mapping, profile="rs4")

        corrupted = list(encoded.peptides)
        # Corrupt the first data peptide of each block
        for pep_idx, meta in enumerate(encoded.metadata):
            if meta.index_in_block == 0 and not meta.is_parity:
                bad = corrupted[pep_idx]
                if bad:
                    corrupted[pep_idx] = ("Y" if bad[0] != "Y" else "A") + bad[1:]

        recovered_mapping = ecc_decode_peptides(corrupted, encoded=encoded, profile="rs4")
        recovered_bits = peptides_to_bits(recovered_mapping)
        enc.bits = recovered_bits
        decoded = huffman_decode(enc)

        assert decoded == data
    finally:
        rs.NUM_DATA_PEPTIDES = original_k


def test_rs_metadata_retains_padding_bits_for_misaligned_symbols():
    """
    When peptide_length*3 is not byte-aligned, ensure padding metadata is kept
    so RS can still correct a corrupted peptide.
    """
    original_k = rs.NUM_DATA_PEPTIDES
    rs.NUM_DATA_PEPTIDES = 1  # keep a tiny block to isolate symbol-level behavior
    try:
        data = b"pad-bit-coverage"
        enc = huffman_encode(data)
        mapping = bits_to_peptides(enc.bits, peptide_length=5)  # 5*3 = 15 -> needs padding

        encoded = ecc_encode_peptides(mapping, profile="rs4")
        expected_pad_len = (8 - ((encoded.peptide_length * 3) % 8)) % 8
        assert len(encoded.padding) == len(encoded.peptides)
        assert all((p.padded_bits - p.pad_offset) == expected_pad_len for p in encoded.padding)

        corrupted = list(encoded.peptides)
        if corrupted and corrupted[0]:
            corrupted[0] = ("Y" if corrupted[0][0] != "Y" else "A") + corrupted[0][1:]

        recovered_mapping = ecc_decode_peptides(corrupted, encoded=encoded, profile="rs4")
        recovered_bits = peptides_to_bits(recovered_mapping)
        enc.bits = recovered_bits
        decoded = huffman_decode(enc)

        assert decoded == data
    finally:
        rs.NUM_DATA_PEPTIDES = original_k
