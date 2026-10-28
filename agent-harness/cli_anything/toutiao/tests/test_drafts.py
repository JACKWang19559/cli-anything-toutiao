"""Local-file and concurrency contracts for the actual SQLite draft store."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from cli_anything.toutiao.core.drafts import DraftStore
from cli_anything.toutiao.core.errors import ToutiaoError


@pytest.fixture
def store(tmp_path):
    return DraftStore(tmp_path / "draft-data")


def test_read_empty_store_does_not_create_directory(store):
    assert store.list() == []
    with pytest.raises(ToutiaoError) as raised:
        store.get(str(uuid4()))
    assert raised.value.code == "DRAFT_NOT_FOUND"
    assert not store.data_dir.exists()


def test_dry_run_create_never_creates_store(store):
    result = store.create("  中文标题  ", "第一段\n\n第二段", dry_run=True)
    assert result["title"] == "中文标题"
    assert result["status"] == "local_draft"
    assert result["dry_run"] is True
    assert not store.data_dir.exists()


def test_create_round_trip_in_separate_store(store):
    draft = store.create("中文标题", "第一段\n\n- 条目\n")
    reopened = DraftStore(store.data_dir)
    assert reopened.get(draft["id"]) == draft
    assert reopened.list() == [draft]
    assert "dry_run" not in draft


@pytest.mark.parametrize("title", ["", "  ", "a\nb", "a\rb", None])
def test_invalid_title_does_not_create_database(store, title):
    with pytest.raises(ToutiaoError) as raised:
        store.create(title, "body")
    assert raised.value.code == "INVALID_TITLE"
    assert not store.path.exists()


def test_nontext_content_rejected(store):
    with pytest.raises(ToutiaoError) as raised:
        store.create("标题", {"content": "not a string"})
    assert raised.value.code == "INVALID_CONTENT"


@pytest.mark.parametrize("identifier", ["../../outside", "", "'; DROP TABLE drafts; --"])
def test_bad_ids_rejected_without_storage(store, identifier):
    with pytest.raises(ToutiaoError) as raised:
        store.get(identifier)
    assert raised.value.code == "INVALID_DRAFT_ID"
    assert not store.data_dir.exists()


def test_update_preserves_unmodified_fields_and_creation_time(store):
    original = store.create("初稿", "正文")
    updated = store.update(original["id"], title="第二稿")
    assert updated["title"] == "第二稿"
    assert updated["content"] == original["content"]
    assert updated["created_at"] == original["created_at"]
    assert store.get(original["id"]) == updated
    cleared = store.update(original["id"], content="")
    assert cleared["content"] == ""


def test_update_without_changes_rejected(store):
    draft = store.create("标题", "正文")
    with pytest.raises(ToutiaoError) as raised:
        store.update(draft["id"])
    assert raised.value.code == "NO_CHANGES"
    assert store.get(draft["id"]) == draft


def test_dry_run_update_and_delete_leave_database_bytes_unchanged(store):
    draft = store.create("原题", "原文")
    before = store.path.read_bytes()
    preview = store.update(draft["id"], title="新题", content="新文", dry_run=True)
    assert preview["title"] == "新题"
    assert preview["dry_run"] is True
    deletion = store.delete(draft["id"], dry_run=True)
    assert deletion["would_delete"] is True
    assert deletion["deleted"] is False
    assert store.get(draft["id"]) == draft
    assert store.path.read_bytes() == before


def test_delete_persists_and_missing_delete_is_error(store):
    draft = store.create("标题", "正文")
    assert store.delete(draft["id"])["deleted"] is True
    assert DraftStore(store.data_dir).list() == []
    with pytest.raises(ToutiaoError) as raised:
        store.delete(draft["id"])
    assert raised.value.code == "DRAFT_NOT_FOUND"


def test_concurrent_create_retains_every_draft(store):
    def create(index):
        return DraftStore(store.data_dir).create(f"标题 {index}", f"正文 {index}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create, range(24)))
    assert len({draft["id"] for draft in results}) == 24
    assert {draft["id"] for draft in store.list()} == {draft["id"] for draft in results}


def test_concurrent_partial_updates_do_not_lose_fields(store):
    draft = store.create("初始标题", "初始正文")
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(DraftStore(store.data_dir).update, draft["id"], title="最终标题")
        two = pool.submit(DraftStore(store.data_dir).update, draft["id"], content="最终正文")
        one.result()
        two.result()
    result = store.get(draft["id"])
    assert result["title"] == "最终标题"
    assert result["content"] == "最终正文"


def test_export_writes_complete_utf8_markdown(store, tmp_path):
    draft = store.create("你好", "第一行\n\n第二行\n")
    target = tmp_path / "导出" / "稿件.md"
    result = store.export(draft["id"], target)
    assert target.read_text(encoding="utf-8") == "# 你好\n\n第一行\n\n第二行\n"
    assert result["bytes"] == target.stat().st_size
    assert result["path"] == str(target)
    assert list(target.parent.glob(".toutiao-*.tmp")) == []


def test_export_existing_target_requires_overwrite(store, tmp_path):
    draft = store.create("标题", "正文")
    target = tmp_path / "draft.md"
    target.write_text("original", encoding="utf-8")
    with pytest.raises(ToutiaoError) as raised:
        store.export(draft["id"], target)
    assert raised.value.code == "OUTPUT_EXISTS"
    assert target.read_text(encoding="utf-8") == "original"
    store.export(draft["id"], target, overwrite=True)
    assert target.read_text(encoding="utf-8") == "# 标题\n\n正文\n"


def test_dry_run_export_does_not_create_parent(store, tmp_path):
    draft = store.create("标题", "正文")
    target = tmp_path / "new-parent" / "draft.md"
    result = store.export(draft["id"], target, dry_run=True)
    assert result["dry_run"] is True
    assert not target.parent.exists()


def test_export_cannot_overwrite_own_database(store):
    draft = store.create("标题", "正文")
    before = store.path.read_bytes()
    with pytest.raises(ToutiaoError) as raised:
        store.export(draft["id"], store.path, overwrite=True)
    assert raised.value.code == "INVALID_OUTPUT"
    assert store.path.read_bytes() == before


def test_corrupt_database_reports_domain_error(store):
    store.data_dir.mkdir()
    store.path.write_bytes(b"this is not a sqlite database")
    with pytest.raises(ToutiaoError) as raised:
        store.list()
    assert raised.value.code == "DRAFT_STORAGE_ERROR"


def test_competing_exports_cannot_overwrite_each_other(store, tmp_path):
    first = store.create("标题一", "正文一" * 10000)
    second = store.create("标题二", "正文二" * 10000)
    target = tmp_path / "contested.md"

    def export(identifier):
        try:
            store.export(identifier, target)
            return "ok"
        except ToutiaoError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(export, [first["id"], second["id"]]))
    assert sorted(outcomes) == ["OUTPUT_EXISTS", "ok"]
    assert target.read_text(encoding="utf-8") in {
        f"# {item['title']}\n\n{item['content']}\n" for item in (first, second)
    }
    assert list(tmp_path.glob(".toutiao-*.tmp")) == []
