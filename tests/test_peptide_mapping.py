from src.encoding_schemes.huffman import huffman_encode, huffman_decode
from src.encoding_schemes.peptide_mapping import bits_to_peptides, peptides_to_bits

data = b"hello Yahya"


encoded = huffman_encode(data)


mapping_result = bits_to_peptides(encoded.bits, peptide_length=18)
print("Peptides:", mapping_result.peptides)


recovered_bits = peptides_to_bits(mapping_result)


encoded.bits = recovered_bits
decoded = huffman_decode(encoded)


print("Roundtrip OK? ", decoded == data)
