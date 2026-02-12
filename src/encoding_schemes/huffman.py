from dataclasses import dataclass
from dahuffman import HuffmanCodec
from src.utils.bits_bytes_utils import bytes_to_bitstring, bitstring_to_bytes


@dataclass
class HuffmanEncoded:
    """
    Container for Huffman-encoded data.

    - bits: encoded bit string (e.g. '010101...')
    - codec: HuffmanCodec object that knows how to decode these bits
    """
    bits: str
    codec: HuffmanCodec


def huffman_encode(data: bytes) -> HuffmanEncoded:
    """
    Encode raw bytes with Huffman coding.

    """
    codec = HuffmanCodec.from_data(data)
    encoded_bytes = codec.encode(data)
    bits = bytes_to_bitstring(encoded_bytes)
    return HuffmanEncoded(bits=bits, codec=codec)


def huffman_decode(encoded: HuffmanEncoded) -> bytes:
    """
    Decode HuffmanEncoded back to the original bytes.

    """
    encoded_bytes = bitstring_to_bytes(encoded.bits)
    return encoded.codec.decode(encoded_bytes)
