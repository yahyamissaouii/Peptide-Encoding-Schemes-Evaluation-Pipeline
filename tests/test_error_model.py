from src.encoding_schemes.huffman import huffman_encode, huffman_decode
from src.encoding_schemes.peptide_mapping import bits_to_peptides, peptides_to_bits
from src.error_model import apply_peptide_errors

data = b"hello peptide storage!"
encoded = huffman_encode(data)

# bits → peptides (18-mer)
mapping_result = bits_to_peptides(encoded.bits, peptide_length=18)
original_peptides = mapping_result.peptides

print("Original peptides:", original_peptides)

# apply errors
corrupted_peptides = apply_peptide_errors(
    original_peptides,
    loss_prob=0.0,
    mutation_prob=0.0,
    insertion_prob=0.0,
    shuffle_prob=0.0,
    shuffle_passes=0
)

print("Corrupted peptides:", corrupted_peptides)


recovered_bits = peptides_to_bits(
    mapping_result.__class__(
        peptides=corrupted_peptides,
        pad_bits=mapping_result.pad_bits,
        peptide_length=mapping_result.peptide_length,
    )
)

encoded.bits = recovered_bits
decoded = huffman_decode(encoded)
print("Decoded OK? ", decoded == data)
