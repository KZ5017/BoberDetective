from pathlib import Path


class StoragePathError(ValueError):
    """Raised when a requested storage path would leave the configured data root."""


class StoragePaths:
    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root.expanduser().resolve()

    def is_data_root_writable(self) -> bool:
        return self.data_root.exists() and self.data_root.is_dir() and self._can_write(self.data_root)

    def cases_dir(self) -> Path:
        return self._resolve_under_root("cases")

    def case_dir(self, case_id: str) -> Path:
        return self._resolve_under_root("cases", case_id)

    def originals_dir(self, case_id: str, document_id: str) -> Path:
        return self._resolve_under_root("cases", case_id, "originals", document_id)

    def derived_dir(self, case_id: str, document_id: str) -> Path:
        return self._resolve_under_root("cases", case_id, "derived", document_id)

    def exports_dir(self, case_id: str) -> Path:
        return self._resolve_under_root("cases", case_id, "exports")

    def audit_dir(self, case_id: str | None = None) -> Path:
        if case_id is None:
            return self._resolve_under_root("audit")
        return self._resolve_under_root("cases", case_id, "audit")

    def knowledge_document_dir(self, knowledge_document_id: str) -> Path:
        return self._resolve_under_root("knowledge", "documents", knowledge_document_id)

    def knowledge_document_originals_dir(self, knowledge_document_id: str) -> Path:
        return self._resolve_under_root("knowledge", "documents", knowledge_document_id, "originals")

    def knowledge_document_derived_dir(self, knowledge_document_id: str) -> Path:
        return self._resolve_under_root("knowledge", "documents", knowledge_document_id, "derived")

    def _resolve_under_root(self, *parts: str) -> Path:
        for part in parts:
            self._validate_path_part(part)
        candidate = self.data_root.joinpath(*parts).resolve()
        if not self._is_relative_to(candidate, self.data_root):
            raise StoragePathError("Resolved path escapes configured data root")
        return candidate

    @staticmethod
    def _validate_path_part(part: str) -> None:
        path_part = Path(part)
        if path_part.is_absolute() or part in {"", ".", ".."}:
            raise StoragePathError("Unsafe storage path segment")
        if len(path_part.parts) != 1:
            raise StoragePathError("Storage path segment must not contain separators")

    @staticmethod
    def _is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    @staticmethod
    def _can_write(path: Path) -> bool:
        probe = path / ".write-test"
        try:
            probe.touch(exist_ok=True)
            probe.unlink()
            return True
        except OSError:
            return False
