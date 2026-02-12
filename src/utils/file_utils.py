from pathlib import Path


def add_suffix_to_top_level(rel_path: Path, suffix: str) -> Path:
    """
    Add a suffix to the top-level directory name of a relative path.

    Example:
        'dwd_weatherdata/subdir/file1.txt'
        + '_encoded'
        -> 'dwd_weatherdata_encoded/subdir/file1.txt'
    """
    parts = list(rel_path.parts)
    if not parts:
        return Path()
    parts[0] = parts[0] + suffix
    return Path(*parts)


def suffix_filename(path: Path, suffix: str) -> Path:
    """
    Add a suffix before the file extension.

    Example:
        file1.txt + '_encoded' -> file1_encoded.txt
        README   + '_decoded'  -> README_decoded
    """
    if path.suffix:
        return path.with_name(path.stem + suffix + path.suffix)
    return path.with_name(path.name + suffix)
