"""CLI protocol and argument handling without live browser access."""

import json
from pathlib import Path

from click.testing import CliRunner
import pytest

from cli_anything.toutiao import toutiao_cli as module
from cli_anything.toutiao.core.errors import ToutiaoError


def invoke(*args, input=None):
    return CliRunner().invoke(module.cli, list(args), input=input)


@pytest.mark.parametrize("args", [
    ["hot", "--limit", "0"],
    ["hot", "--limit", "51"],
    ["--timeout", "nan", "hot"],
    ["--timeout", "0", "hot"],
    ["search", " "],
    ["unknown-command"],
])
def test_argument_errors_are_json(args):
    result = invoke("--json", *args)
    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert result.stderr == ""


def test_json_without_command_is_discoverable():
    result = invoke("--json")
    assert result.exit_code == 0
    assert "hot" in json.loads(result.stdout)["data"]["commands"]


def test_noninteractive_no_command_prints_help():
    result = invoke()
    assert result.exit_code == 0
    assert "Commands:" in result.stdout
    assert "Goodbye" not in result.stdout


def test_backend_error_is_json(monkeypatch):
    class Backend:
        def __init__(self, **kwargs):
            pass

        def call(self, *args, **kwargs):
            raise ToutiaoError("LOGIN_REQUIRED", "请在浏览器完成登录。")

    monkeypatch.setattr(module, "ToutiaoBackend", Backend)
    result = invoke("--json", "hot")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "LOGIN_REQUIRED"
    assert "Traceback" not in result.stdout


def test_unicode_result_and_options_reach_backend(monkeypatch):
    observed = {}

    class Backend:
        def __init__(self, **kwargs):
            observed.update(kwargs)

        def call(self, operation, **kwargs):
            observed.update(operation=operation, **kwargs)
            return {"items": [{"title": "中文热榜", "url": "https://www.toutiao.com/"}]}

    monkeypatch.setattr(module, "ToutiaoBackend", Backend)
    result = invoke("--json", "--timeout", "12", "--browser-space", "10", "hot", "--limit", "3")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["data"]["items"][0]["title"] == "中文热榜"
    assert "中文热榜" in result.stdout
    assert observed == {"timeout": 12.0, "space": "10", "operation": "hot", "limit": 3}


def test_draft_content_options_are_mutually_exclusive(tmp_path):
    source = tmp_path / "正文.md"
    source.write_text("正文", encoding="utf-8")
    result = invoke("--json", "--data-dir", str(tmp_path / "data"), "draft", "create",
                    "--title", "测试", "--file", str(source), "--content", "重复")
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"]["code"] == "INVALID_ARGUMENT"
    assert not (tmp_path / "data").exists()


def test_invalid_file_encoding_is_structured(tmp_path):
    source = tmp_path / "invalid.md"
    source.write_bytes(b"\xff\xfe\xff")
    result = invoke("--json", "--data-dir", str(tmp_path / "data"), "draft", "create",
                    "--title", "测试", "--file", str(source))
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "INVALID_ENCODING"


def test_json_repl_has_no_banner_or_prompt(tmp_path):
    result = invoke("--json", "--data-dir", str(tmp_path / "data"), "repl",
                    input="draft list\nquit\n")
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"ok": True, "data": []}
    assert not (tmp_path / "data").exists()


def test_article_export_and_overwrite_guard(monkeypatch, tmp_path):
    calls = []

    class Backend:
        def __init__(self, **kwargs):
            pass

        def call(self, operation, **kwargs):
            calls.append(operation)
            return {"title": "正文", "url": "https://www.toutiao.com/article/123/"}

    monkeypatch.setattr(module, "ToutiaoBackend", Backend)
    monkeypatch.setattr(module, "article_markdown", lambda value: "# 中文标题\n\n正文\n")
    target = tmp_path / "文章.md"
    args = ("--json", "article", "123", "--output", str(target))
    result = invoke(*args)
    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8") == "# 中文标题\n\n正文\n"
    assert Path(json.loads(result.stdout)["data"]["output"]) == target
    result = invoke(*args)
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "FILE_EXISTS"
    assert calls == ["article"]
    result = invoke(*args, "--overwrite")
    assert result.exit_code == 0
    assert calls == ["article", "article"]


def test_article_text_mode(monkeypatch):
    class Backend:
        def __init__(self, **kwargs):
            pass

        def call(self, operation, **kwargs):
            return {"title": "标题"}

    monkeypatch.setattr(module, "ToutiaoBackend", Backend)
    monkeypatch.setattr(module, "article_text", lambda value: "纯文本正文")
    result = invoke("article", "123", "--format", "text")
    assert result.exit_code == 0
    assert result.stdout.strip() == "纯文本正文"


def test_repl_quotes_and_windows_paths():
    assert module._split_repl('search "人工 智能"') == ["search", "人工 智能"]
    if module.os.name == "nt":
        assert module._split_repl('draft create --file "D:\\文章 目录\\草稿.md"')[-1] == "D:\\文章 目录\\草稿.md"
