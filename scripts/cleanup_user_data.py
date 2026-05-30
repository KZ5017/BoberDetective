from __future__ import annotations

from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

from app.core.config import get_settings


PRESERVED_TABLES = {"alembic_version", "users"}


def main() -> None:
    settings = get_settings()
    truncated = _truncate_database(settings.database_url)
    removed_case_files = _remove_case_files(settings.data_root)
    removed_collections = _remove_qdrant_collections(settings.qdrant_url)
    print(
        {
            "truncated_tables": truncated,
            "removed_case_files": removed_case_files,
            "removed_qdrant_collections": removed_collections,
        }
    )


def _truncate_database(database_url: str) -> list[str]:
    engine = create_engine(database_url)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                select tablename
                from pg_tables
                where schemaname = 'public'
                order by tablename
                """
            )
        ).all()
        tables = [row[0] for row in rows if row[0] not in PRESERVED_TABLES]
        if not tables:
            return []
        quoted_tables = ", ".join(f'"{table}"' for table in tables)
        conn.execute(text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"))
        return tables


def _remove_case_files(data_root: Path) -> int:
    cases_dir = data_root / "cases"
    if not cases_dir.exists():
        return 0
    removed_files = 0
    for path in sorted(cases_dir.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
            removed_files += 1
        elif path.is_dir():
            path.rmdir()
    cases_dir.mkdir(parents=True, exist_ok=True)
    return removed_files


def _remove_qdrant_collections(qdrant_url: str) -> list[str]:
    removed: list[str] = []
    try:
        with httpx.Client(base_url=qdrant_url.rstrip("/"), timeout=20) as client:
            response = client.get("/collections")
            response.raise_for_status()
            collections = response.json().get("result", {}).get("collections", [])
            for collection in collections:
                name = collection.get("name")
                if not isinstance(name, str) or not name.startswith("boberdetective_chunks"):
                    continue
                delete_response = client.delete(f"/collections/{name}")
                delete_response.raise_for_status()
                removed.append(name)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Could not clean Qdrant collections: {exc}") from exc
    return removed


if __name__ == "__main__":
    main()
