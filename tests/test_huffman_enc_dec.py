from src.encoding_schemes.huffman import huffman_encode, huffman_decode

data = b"hello peptide!"
encoded = huffman_encode(data)
decoded = huffman_decode(encoded)

print("Encoded: ", encoded)
print("Decoded: ", decoded)

print("OK?     ", decoded == data)
