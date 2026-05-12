from pathlib import Path

import pytest

from app.services.storage import StoragePathError, StoragePaths


def test_storage_paths_stay_under_data_root(tmp_path: Path) -> None:
    storage = StoragePaths(tmp_path)

    assert storage.case_dir("case-1") == tmp_path / "cases" / "case-1"


def test_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = StoragePaths(tmp_path)

    with pytest.raises(StoragePathError):
        storage.case_dir("../outside")

