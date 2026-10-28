"""Transactional local Markdown drafts, independent of the Toutiao account.

Nothing in this module saves a cloud draft or publishes content. SQLite owns
cross-process locking; every completed mutation is committed immediately.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
from uuid import UUID, uuid4

from cli_anything.toutiao.core.errors import ToutiaoError


_SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _draft_id(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ToutiaoError("INVALID_DRAFT_ID", "草稿 ID 必须是有效的 UUID。") from exc


def _title(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToutiaoError("INVALID_TITLE", "草稿标题不能为空。")
    value = value.strip()
    if "\n" in value or "\r" in value:
        raise ToutiaoError("INVALID_TITLE", "草稿标题必须为单行文字。")
    return value


def _content(value: str) -> str:
    if not isinstance(value, str):
        raise ToutiaoError("INVALID_CONTENT", "草稿正文必须为文本。")
    return value


def _row(row: sqlite3.Row) -> dict:
    return {**dict(row), "status": "local_draft"}


class DraftStore:
    """A local draft collection in ``data_dir/drafts.sqlite3``.

    Construction, reads, and dry runs never create files. A missing collection
    behaves like an empty collection. Read connections use SQLite's read-only
    URI mode so an accidental read cannot initialize or modify the database.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.path = self.data_dir / "drafts.sqlite3"

    @contextmanager
    def _connection(self, *, write: bool = False):
        connection = None
        try:
            if write:
                self.data_dir.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(self.path, timeout=15)
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(_SCHEMA)
            else:
                connection = sqlite3.connect(
                    self.path.as_uri() + "?mode=ro", uri=True, timeout=15
                )
            connection.row_factory = sqlite3.Row
            yield connection
            if write:
                connection.commit()
        except (sqlite3.Error, OSError) as exc:
            if connection is not None and write:
                connection.rollback()
            raise ToutiaoError(
                "DRAFT_STORAGE_ERROR", f"无法访问本地草稿库：{exc}"
            ) from exc
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _fetch(connection: sqlite3.Connection, draft_id: str) -> dict:
        row = connection.execute(
            "SELECT * FROM drafts WHERE id = ?", (draft_id,)
        ).fetchone()
        if row is None:
            raise ToutiaoError("DRAFT_NOT_FOUND", f"找不到本地草稿：{draft_id}")
        return _row(row)

    def create(self, title: str, content: str, dry_run: bool = False) -> dict:
        now = _timestamp()
        draft = {
            "id": str(uuid4()),
            "title": _title(title),
            "content": _content(content),
            "created_at": now,
            "updated_at": now,
            "status": "local_draft",
        }
        if dry_run:
            return {**draft, "dry_run": True}
        with self._connection(write=True) as connection:
            connection.execute(
                "INSERT INTO drafts (id, title, content, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                tuple(draft[key] for key in ("id", "title", "content", "created_at", "updated_at")),
            )
        return draft

    def list(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self._connection() as connection:
            return [
                _row(row)
                for row in connection.execute(
                    "SELECT * FROM drafts ORDER BY updated_at DESC, id"
                )
            ]

    def get(self, draft_id: str) -> dict:
        draft_id = _draft_id(draft_id)
        if not self.path.exists():
            raise ToutiaoError("DRAFT_NOT_FOUND", f"找不到本地草稿：{draft_id}")
        with self._connection() as connection:
            return self._fetch(connection, draft_id)

    def update(
        self,
        draft_id: str,
        title: str | None = None,
        content: str | None = None,
        dry_run: bool = False,
    ) -> dict:
        draft_id = _draft_id(draft_id)
        if title is None and content is None:
            raise ToutiaoError("NO_CHANGES", "请提供要更新的标题或正文。")
        title = _title(title) if title is not None else None
        content = _content(content) if content is not None else None
        if dry_run:
            draft = self.get(draft_id)
            if title is not None:
                draft["title"] = title
            if content is not None:
                draft["content"] = content
            return {**draft, "updated_at": _timestamp(), "dry_run": True}
        if not self.path.exists():
            raise ToutiaoError("DRAFT_NOT_FOUND", f"找不到本地草稿：{draft_id}")
        # Read and write occur in one reserved transaction. Concurrent updates
        # to different fields therefore cannot overwrite each other's changes.
        with self._connection(write=True) as connection:
            draft = self._fetch(connection, draft_id)
            if title is not None:
                draft["title"] = title
            if content is not None:
                draft["content"] = content
            draft["updated_at"] = _timestamp()
            connection.execute(
                "UPDATE drafts SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                (draft["title"], draft["content"], draft["updated_at"], draft_id),
            )
        return draft

    def delete(self, draft_id: str, dry_run: bool = False) -> dict:
        draft_id = _draft_id(draft_id)
        if dry_run:
            self.get(draft_id)
            return {"id": draft_id, "deleted": False, "would_delete": True,
                    "status": "local_draft", "dry_run": True}
        if not self.path.exists():
            raise ToutiaoError("DRAFT_NOT_FOUND", f"找不到本地草稿：{draft_id}")
        with self._connection(write=True) as connection:
            self._fetch(connection, draft_id)
            connection.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
        return {"id": draft_id, "deleted": True, "status": "local_draft"}

    def export(
        self,
        draft_id: str,
        path: Path,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> dict:
        draft = self.get(draft_id)
        destination = Path(path).expanduser().absolute()
        if destination.resolve() == self.path.resolve():
            raise ToutiaoError("INVALID_OUTPUT", "不能将草稿导出到草稿数据库文件。")
        if destination.exists() and self.path.exists():
            try:
                if destination.samefile(self.path):
                    raise ToutiaoError("INVALID_OUTPUT", "不能覆盖草稿数据库文件。")
            except OSError as exc:
                raise ToutiaoError("EXPORT_ERROR", f"无法检查导出路径：{exc}") from exc
        if destination.exists() and not overwrite:
            raise ToutiaoError("OUTPUT_EXISTS", f"文件已存在：{destination}")
        if destination.is_dir():
            raise ToutiaoError("INVALID_OUTPUT", "导出路径必须是文件。")
        markdown = f"# {draft['title']}\n\n{draft['content'].rstrip()}\n"
        payload = markdown.encode("utf-8")
        result = {
            "id": draft["id"], "path": str(destination), "format": "markdown",
            "bytes": len(payload), "status": "local_draft",
        }
        if dry_run:
            return {**result, "dry_run": True}
        temporary = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=destination.parent, prefix=".toutiao-", suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if overwrite:
                os.replace(temporary, destination)
            else:
                # link() atomically fails if another process created the target
                # after our check. Readers can only see the complete file.
                os.link(temporary, destination)
            return result
        except FileExistsError as exc:
            raise ToutiaoError("OUTPUT_EXISTS", f"文件已存在：{destination}") from exc
        except OSError as exc:
            raise ToutiaoError("EXPORT_ERROR", f"导出失败：{exc}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
