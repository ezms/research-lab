import zipfile
from pathlib import Path


def _is_valid_zip(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path):
            return True
    except zipfile.BadZipFile:
        return False
