"""Installed-command workflows and explicitly selected real-browser checks.

Offline tests run by default. To run the live workflow, set
TOUTIAO_BROWSER_SPACE to an existing agent-controlled space, then use -m live.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


def _resolve_cli(name: str) -> list[str]:
    """Resolve the installed executable; enforce it during release validation."""
    executable = shutil.which(name)
    if executable:
        print(f"[_resolve_cli] Using installed command: {executable}")
        return [executable]
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1":
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e ./agent-harness")
    module = "cli_anything." + name.removeprefix("cli-anything-")
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


@pytest.fixture(scope="module")
def cli_base():
    return _resolve_cli("cli-anything-toutiao")


def _run(cli_base, *args, timeout=20, input=None):
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        cli_base + list(args), capture_output=True, text=True, encoding="utf-8",
        timeout=timeout, input=input, env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _success(cli_base, *args, **kwargs):
    result = _run(cli_base, *args, **kwargs)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert "data" in payload
    assert result.stderr == ""
    return payload["data"]


def _draft_args(tmp_path):
    return ["--json", "--data-dir", str(tmp_path / "draft data"), "draft"]


def test_installed_help(cli_base):
    result = _run(cli_base, "--help")
    assert result.returncode == 0
    for command in ("hot", "search", "article", "draft", "auth", "repl"):
        assert command in result.stdout


def test_installed_version(cli_base):
    result = _run(cli_base, "--version")
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_installed_no_argument_non_tty(cli_base):
    result = _run(cli_base)
    assert result.returncode == 0
    assert "Commands:" in result.stdout
    assert "Goodbye" not in result.stdout


def test_installed_json_discovery(cli_base):
    data = _success(cli_base, "--json")
    assert {"hot", "search", "article", "draft", "doctor"}.issubset(data["commands"])


@pytest.mark.parametrize("args", [
    ["unknown-command"],
    ["hot", "--limit", "-1"],
    ["search", ""],
])
def test_installed_json_argument_errors(cli_base, args):
    result = _run(cli_base, "--json", *args)
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert payload["error"]["message"]
    assert result.stderr == ""


def test_installed_doctor_does_not_launch_browser(cli_base):
    data = _success(cli_base, "--json", "doctor")
    assert data["backend"] == "ego-browser"
    assert isinstance(data["ready"], bool)
    assert data["python"]
    assert data["note"]


def test_installed_draft_file_round_trip(cli_base, tmp_path):
    body = "第一段：人工智能。\n\n## 观察\n- 中文条目\n- 第二条\n"
    source = tmp_path / "中文输入 草稿.md"
    source.write_text(body, encoding="utf-8")
    args = _draft_args(tmp_path)
    created = _success(cli_base, *args, "create", "--title", "中文测试标题", "--file", str(source))
    draft_id = created["id"]
    assert created["content"] == body
    assert created["status"] == "local_draft"
    rows = _success(cli_base, *args, "list")
    assert [item["id"] for item in rows] == [draft_id]
    assert _success(cli_base, *args, "show", draft_id)["content"] == body

    changed_body = "更新后的正文。\n第二行保留。"
    updated = _success(cli_base, *args, "update", draft_id, "--title", "更新标题", "--content", changed_body)
    assert updated["title"] == "更新标题"
    persisted = _success(cli_base, *args, "show", draft_id)
    assert persisted["content"] == changed_body
    assert persisted["updated_at"] == updated["updated_at"]

    output = tmp_path / "导出结果" / "文章.md"
    exported = _success(cli_base, *args, "export", draft_id, "--output", str(output))
    expected = ("# 更新标题\n\n" + changed_body + "\n").encode("utf-8")
    assert output.read_bytes() == expected
    assert exported["bytes"] == len(expected)
    assert Path(exported["path"]) == output
    print(f"\n  Markdown: {output} ({len(expected):,} bytes)")

    deleted = _success(cli_base, *args, "delete", draft_id)
    assert deleted["deleted"] is True
    assert _success(cli_base, *args, "list") == []
    missing = _run(cli_base, *args, "show", draft_id)
    assert missing.returncode != 0
    assert json.loads(missing.stdout)["error"]["code"] == "DRAFT_NOT_FOUND"


def test_installed_draft_dry_run_has_no_side_effects(cli_base, tmp_path):
    args = _draft_args(tmp_path)
    preview = _success(cli_base, *args, "create", "--title", "预演", "--content", "正文", "--dry-run")
    assert preview["dry_run"] is True
    assert not (tmp_path / "draft data").exists()
    created = _success(cli_base, *args, "create", "--title", "原题", "--content", "原文")
    draft_id = created["id"]
    changed = _success(cli_base, *args, "update", draft_id, "--title", "新题", "--dry-run")
    assert changed["title"] == "新题"
    assert _success(cli_base, *args, "show", draft_id)["title"] == "原题"
    deleted = _success(cli_base, *args, "delete", draft_id, "--dry-run")
    assert deleted["deleted"] is False
    assert _success(cli_base, *args, "show", draft_id)["content"] == "原文"
    output = tmp_path / "未创建目录" / "预演.md"
    exported = _success(cli_base, *args, "export", draft_id, "--output", str(output), "--dry-run")
    assert exported["dry_run"] is True
    assert not output.parent.exists()


def test_installed_draft_export_preserves_existing_file(cli_base, tmp_path):
    args = _draft_args(tmp_path)
    created = _success(cli_base, *args, "create", "--title", "测试", "--content", "导出正文")
    output = tmp_path / "existing.md"
    output.write_bytes(b"original-content")
    failed = _run(cli_base, *args, "export", created["id"], "--output", str(output))
    assert failed.returncode != 0
    assert json.loads(failed.stdout)["error"]["code"] == "OUTPUT_EXISTS"
    assert output.read_bytes() == b"original-content"
    _success(cli_base, *args, "export", created["id"], "--output", str(output), "--overwrite")
    assert output.read_bytes() == "# 测试\n\n导出正文\n".encode("utf-8")


def test_installed_json_repl(cli_base, tmp_path):
    data = _success(cli_base, "--json", "--data-dir", str(tmp_path / "data"), "repl",
                    input="draft list\nquit\n")
    assert data == []
    assert not (tmp_path / "data").exists()


@pytest.mark.live
def test_live_reader_workflow(cli_base, tmp_path):
    """Real service calls; opted-in failures are failures, never silent skips."""
    space = os.environ.get("TOUTIAO_BROWSER_SPACE")
    assert space, "Set TOUTIAO_BROWSER_SPACE to an existing agent-controlled Ego space before -m live."
    prefix = ["--json", "--timeout", "90", "--browser-space", space]
    for command in (
        ["hot", "--limit", "3"],
        ["feed", "--channel", "tech", "--limit", "3"],
        ["search", "人工智能", "--limit", "3"],
    ):
        data = _success(cli_base, *prefix, *command, timeout=115)
        assert data["backend"] == "ego-browser"
        assert data["fetched_at"]
        assert 0 < len(data["items"]) <= 3
        assert data["count"] == len(data["items"])
        for item in data["items"]:
            assert isinstance(item["id"], str) and item["id"].isdigit()
            assert item["title"].strip()
            assert item["url"].startswith("https://www.toutiao.com/")

    article_id = "7701468351923257896"
    output = tmp_path / "real-article.md"
    article = _success(cli_base, *prefix, "article", article_id, "--output", str(output), timeout=115)
    assert article["id"] == article_id  # Preserve 64-bit IDs without JS-number rounding.
    assert article["title"].strip()
    assert len(article["text"]) > 50
    assert article["url"] == f"https://www.toutiao.com/article/{article_id}/"
    content = output.read_text(encoding="utf-8")
    assert content.startswith("# ")
    assert article["url"] in content
    assert len(content) > 100
    print(f"\n  Real article: {output} ({output.stat().st_size:,} bytes)")

    status = _success(cli_base, *prefix, "auth", "status", timeout=115)
    assert status["logged_in"] is None or isinstance(status["logged_in"], bool)
    assert status["backend"] == "ego-browser"
    assert status["message"]
