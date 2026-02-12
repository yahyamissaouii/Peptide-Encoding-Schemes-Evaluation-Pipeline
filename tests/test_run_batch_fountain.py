from pathlib import Path

from src.pipeline import PipelineConfig, run_batch_on_folder


# Fountain batch run (profile-controlled overhead)
cfg_fountain = PipelineConfig(
    peptide_length=18,
    ecc_profile="fnt50",
    visualize_as_pgm=False,
    embed_image_header=False,
    visualize_width=0,
    loss_prob=0.01,  # 2 %
    mutation_prob=0.005,  # 0.5 %
    insertion_prob=0.005,  # 0.5 %
    shuffle_prob=0.005,  # 0.5 %
    shuffle_passes=1,
    encoder="fountain",
)
run_batch_on_folder(
    input_root=Path("../resources/test/data_test"),
    output_root=Path(f"../resources/test/out_test_{cfg_fountain.encoder}_{cfg_fountain.ecc_profile}"),
    cfg=cfg_fountain,
)
