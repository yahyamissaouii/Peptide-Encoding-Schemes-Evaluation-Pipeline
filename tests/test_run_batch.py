from pathlib import Path

from src.pipeline import PipelineConfig, run_batch_on_folder



# With RS8
"""
cfg = PipelineConfig(
    peptide_length=18,
    ecc_profile="rs64",
    visualize_as_pgm=False,
    embed_image_header=False,
    visualize_width=0,
    loss_prob=0.01, # 2 %
    mutation_prob=0.005, # 2 %
    insertion_prob=0.005, # 2 %what 
    shuffle_prob=0.005, # 2 %
    shuffle_passes=1,
    encoder="fountain",
)
"""
"""
cfg = PipelineConfig(
    peptide_length=18,
    encoder="yin_yang",
    ecc_profile="rs64",
    error_model="scored",
    score_column=None,
)
"""
cfg = PipelineConfig(
    peptide_length=18,
    encoder="fountain",
    ecc_profile="fnt50",
    fountain_symbol_size=17,   # <= 17 for L=18, idx=0
    fountain_seed=123,
    error_model="basic",       # or scored
    loss_prob=0.01,
    mutation_prob=0.005,
    insertion_prob=0.005,
    shuffle_prob=0.005,
)


run_batch_on_folder(
    input_root=Path("../resources/test/data_test"),
    output_root=Path(f"../resources/test/out_test_{cfg.encoder}_{cfg.ecc_profile}"),
    cfg=cfg,
)
