from dataclasses import dataclass


@dataclass
class PipelineConfig:
    """
    Configuration for the peptide-storage pipeline.
    """
    peptide_length: int = 18
    visualize_as_pgm: bool = False
    visualize_width: int = 0
    convert_images_to_ppm: bool = True
    embed_image_header: bool = False
    ecc_profile: str = "none"
    loss_prob: float = 0.0
    mutation_prob: float = 0.0
    insertion_prob: float = 0.0
    shuffle_prob: float = 0.0
    shuffle_passes: int = 1
    encoder: str = "huffman"
    index_aa_length: int = 0
    error_model: str = "basic"
    score_column: str | None = None
    score_label: str | None = None
    score_retry_sleep: float = 1.0
    score_max_sleep: float = 30.0
    score_timeout: float = 30.0
    score_batch_size: int = 5000
    score_batch_max_payload_bytes: int = 200_000
    # Fountain-code settings (used when encoder="fountain")
    # NOTE: With peptide_length=18 and index_aa_length=0, one LT droplet is mapped
    # over a small, fixed number of peptides. Large symbol sizes make droplets
    # span many peptides, causing CRC to reject almost everything under noise.
    fountain_symbol_size: int = 17
    fountain_overhead: float = 0.1
    fountain_seed_bytes: int = 4
    fountain_degree_bytes: int = 2
    fountain_crc_bytes: int = 4
    fountain_c: float = 0.1
    fountain_delta: float = 0.5
    fountain_seed: int | None = None
    fountain_max_bytes: int = 1_048_576
