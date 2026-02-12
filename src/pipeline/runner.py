
from src.pipeline.config import PipelineConfig



def encode_file_bytes(data: bytes, cfg: PipelineConfig):
    """
    Dispatch encoding based on cfg.encoder.
    Currently only Huffman is supported.
    """
    encoder = cfg.encoder.lower()
    if encoder == "huffman":

        from src.pipeline.huffman_runner import encode_decode_file_huffman

        return encode_decode_file_huffman(data, cfg)
    if encoder == "yin_yang":
        from src.pipeline.yin_yang_runner import encode_decode_file_yin_yang

        return encode_decode_file_yin_yang(data, cfg)
    if encoder == "fountain":
        from src.pipeline.fountain_runner import encode_decode_file_fountain

        return encode_decode_file_fountain(data, cfg)
    raise ValueError(f"Unsupported encoder: {cfg.encoder}")
