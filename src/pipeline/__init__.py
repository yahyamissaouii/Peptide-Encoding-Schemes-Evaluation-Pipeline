from src.pipeline.config import PipelineConfig
from src.pipeline.runner import encode_file_bytes


def run_batch_on_folder(*args, **kwargs):
    # Lazy import so importing `src.pipeline` doesn't pull optional deps (e.g. dahuffman)
    # unless batch execution is actually requested.
    from src.utils.batch import run_batch_on_folder as _run_batch_on_folder

    return _run_batch_on_folder(*args, **kwargs)


__all__ = [
    "PipelineConfig",
    "encode_file_bytes",
    "run_batch_on_folder",
]
