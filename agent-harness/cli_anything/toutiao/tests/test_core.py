"""Validation and browser-process protocol tests; no live browser calls."""

import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pytest

from cli_anything.toutiao.core.content import article_markdown, article_text, article_url
from cli_anything.toutiao.core.errors import ToutiaoError
from cli_anything.toutiao.utils import toutiao_backend as backend_module
from cli_anything.toutiao.utils.toutiao_backend import MARKER, ToutiaoBackend


ARTICLE_ID = "7701568905705308681"
ARTICLE_URL = f"https://www.toutiao.com/article/{ARTICLE_ID}/"


@pytest.mark.parametrize("reference", [
    ARTICLE_ID,
    f"  {ARTICLE_ID}  ",
    f"https://www.toutiao.com/article/{ARTICLE_ID}/?source=feed#comment",
    f"http://toutiao.com/article/{ARTICLE_ID}",
    f"https://m.toutiao.com/a{ARTICLE_ID}/",
    f"https://www.toutiao.com/i{ARTICLE_ID}/",
])
def test_article_reference_canonicalization_preserves_long_id(reference):
    assert article_url(reference) == ARTICLE_URL


@pytest.mark.parametrize("reference", [
    f"https://evil.example/article/{ARTICLE_ID}/",
    f"https://www.toutiao.com.evil.example/article/{ARTICLE_ID}/",
    f"https://evil.example@www.toutiao.com/article/{ARTICLE_ID}/",
    f"https://user:secret@www.toutiao.com/article/{ARTICLE_ID}/",
    f"https://@www.toutiao.com/article/{ARTICLE_ID}/",
    f"https://www.toutiao.com:443/article/{ARTICLE_ID}/",
    f"https://www.toutiao.com:0/article/{ARTICLE_ID}/",
    f"https://www.toutiao.com:invalid/article/{ARTICLE_ID}/",
    f"https://www.toutiao.com:65536/article/{ARTICLE_ID}/",
    f"file://www.toutiao.com/article/{ARTICLE_ID}/",
    f"//www.toutiao.com/article/{ARTICLE_ID}/",
    f"https://www.toutiao.com/video/{ARTICLE_ID}/",
    f"https://www.toutiao.com/article/{ARTICLE_ID}/extra",
    "https://www.toutiao.com/article/12x45/",
    "https://www.toutiao.com/article/1234/",
    "https://www.toutiao.com/article/" + "1" * 31 + "/",
    "7701568905705308681.0",
    "1e18",
    "",
])
def test_article_rejects_untrusted_or_malformed_references(reference):
    with pytest.raises(ToutiaoError) as raised:
        article_url(reference)
    assert raised.value.code == "invalid_article"


def test_article_text_includes_only_available_metadata_and_source():
    article = {"title": "标题", "author": "作者", "published_at": "2026-10-28",
               "text": "  第一段\n\n第二段  ", "url": ARTICLE_URL}
    assert article_text(article) == f"标题\n\n作者 · 2026-10-28\n\n第一段\n\n第二段\n\n{ARTICLE_URL}\n"
    assert article_text({"title": "标题", "text": "正文"}) == "标题\n\n正文\n"


def test_markdown_escapes_title_preserves_extracted_body_and_source():
    article = {"title": "标题 [链接] *重点* <script>", "author": "作者",
               "markdown": "## 子标题\n\n正文", "text": "fallback", "url": ARTICLE_URL}
    result = article_markdown(article)
    assert result.startswith("# 标题 \\[链接\\] \\*重点\\* \\<script\\>\n")
    assert "作者\n\n" in result
    assert f"来源：{ARTICLE_URL}" in result
    assert result.endswith("## 子标题\n\n正文\n")
    assert "fallback" not in result


def test_markdown_falls_back_to_article_text():
    result = article_markdown({"title": "题", "text": "正文", "url": ARTICLE_URL})
    assert result.endswith("\n\n正文\n")


def _uri_path(uri):
    return Path(url2pathname(urlsplit(uri).path))


@pytest.fixture
def browser(monkeypatch):
    captured = {"payload": {"ok": True, "data": {"items": []}}, "returncode": 0,
                "stderr": "", "prefix": "browser diagnostic\n"}
    monkeypatch.setattr(backend_module.shutil, "which", lambda name: "ego-browser.cmd")

    def run(command, **options):
        captured["command"] = command
        captured["options"] = options
        script_uri = re.fullmatch(r"await import\('(.*)'\)", command[-1]).group(1)
        script = _uri_path(script_uri)
        captured["script_path"] = script
        captured["script"] = script.read_text(encoding="utf-8")
        request_uri = json.loads(re.search(r"new URL\((\".*?\")\)", captured["script"]).group(1))
        captured["request"] = json.loads(_uri_path(request_uri).read_text(encoding="utf-8"))
        if "exception" in captured:
            raise captured["exception"]
        stdout = captured.get("stdout", captured["prefix"] + MARKER + json.dumps(captured["payload"]))
        return subprocess.CompletedProcess(command, captured["returncode"], stdout, captured["stderr"])

    monkeypatch.setattr(backend_module.subprocess, "run", run)
    return captured


def test_browser_request_keeps_user_text_out_of_script_and_shell(browser):
    query = "头条'); process.exit(1); // $(whoami) `echo danger` & <script>"
    assert ToutiaoBackend(timeout=12, space="10").call("search", query=query, limit=3) == {"items": []}
    assert browser["request"]["args"] == {"query": query, "limit": 3}
    assert browser["request"]["space"] == 10
    assert browser["request"]["managed_space"] is False
    assert browser["request"]["timeout_ms"] == 12000
    assert query not in browser["script"]
    assert all(query not in argument for argument in browser["command"])
    assert browser["options"].get("shell", False) is False
    assert browser["options"]["timeout"] == 22
    assert browser["options"]["encoding"] == "utf-8"
    assert not browser["script_path"].exists()


def test_browser_article_passes_normalized_url(browser):
    ToutiaoBackend().call("article", reference=ARTICLE_ID)
    assert browser["request"]["args"] == {"url": ARTICLE_URL}
    assert browser["request"]["managed_space"] is True
    assert browser["request"]["space"].startswith("toutiao-cli-")


def test_browser_search_trims_query(browser):
    ToutiaoBackend(space="existing-space").call("search", query="  人工智能  ")
    assert browser["request"]["args"]["query"] == "人工智能"
    assert browser["request"]["space"] == "existing-space"


@pytest.mark.parametrize("query", ["", "   ", "x" * 201])
def test_invalid_query_rejected_before_browser(browser, query):
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("search", query=query)
    assert raised.value.code == "invalid_query"
    assert "command" not in browser


@pytest.mark.parametrize("limit", [0, 51, -1, True, 1.5, "2"])
def test_invalid_limits_rejected_before_browser(browser, limit):
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("hot", limit=limit)
    assert raised.value.code == "invalid_limit"
    assert "command" not in browser


def test_unknown_channel_and_operation_fail_before_browser(browser):
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("feed", channel="unknown")
    assert raised.value.code == "invalid_channel"
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("publish")
    assert raised.value.code == "unsupported_operation"
    assert "command" not in browser


@pytest.mark.parametrize("timeout", [0, -1])
def test_nonpositive_timeout_rejected(timeout):
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend(timeout=timeout)
    assert raised.value.code == "invalid_timeout"


def test_missing_backend_has_actionable_error_and_doctor_status(monkeypatch):
    monkeypatch.setattr(backend_module.shutil, "which", lambda name: None)
    backend = ToutiaoBackend()
    assert backend.doctor()["ready"] is False
    assert "Ego Lite" in backend.doctor()["install_hint"]
    with pytest.raises(ToutiaoError) as raised:
        backend.call("hot")
    assert raised.value.code == "backend_missing"


@pytest.mark.parametrize(("exception", "code"), [
    (subprocess.TimeoutExpired("ego-browser", 1), "browser_timeout"),
    (OSError("private diagnostic"), "backend_unavailable"),
])
def test_process_failure_becomes_domain_error_and_cleans_temp_files(browser, exception, code):
    browser["exception"] = exception
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("hot")
    assert raised.value.code == code
    assert "private diagnostic" not in raised.value.message
    assert not browser["script_path"].exists()


@pytest.mark.parametrize("stdout", [
    MARKER + "not json",
    MARKER + "[]",
    MARKER + '{"ok": "true", "data": {}}',
    MARKER + "{}",
])
def test_malformed_protocol_returns_domain_error(browser, stdout):
    browser["stdout"] = stdout
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("hot")
    assert raised.value.code == "invalid_backend_response"


@pytest.mark.parametrize("error", [None, [], "bad error"])
def test_malformed_failure_payload_returns_domain_error(browser, error):
    browser["payload"] = {"ok": False, "error": error}
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("hot")
    assert raised.value.code == "invalid_backend_response"


def test_structured_browser_error_preserved(browser):
    browser["payload"] = {"ok": False, "error": {"code": "login_required", "message": "请登录"}}
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("hot")
    assert raised.value.code == "login_required"
    assert raised.value.message == "请登录"


@pytest.mark.parametrize(("stderr", "code"), [
    ("secret-account-url", "browser_failed"),
    ("EGO_TASK_SPACE_INACTIVE secret-account-url", "browser_control_required"),
])
def test_missing_result_sanitizes_diagnostics(browser, stderr, code):
    browser["stdout"] = "non-result output"
    browser["stderr"] = stderr
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("hot")
    assert raised.value.code == code
    assert "secret-account-url" not in raised.value.message


def test_nonzero_exit_cannot_report_success(browser):
    browser["returncode"] = 1
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("hot")
    assert raised.value.code == "browser_failed"


def test_success_missing_data_is_rejected(browser):
    browser["payload"] = {"ok": True}
    with pytest.raises(ToutiaoError) as raised:
        ToutiaoBackend().call("hot")
    assert raised.value.code == "browser_failed"


def test_only_marker_lines_are_results_and_last_result_wins(browser):
    browser["stdout"] = (
        'diagnostic contains ' + MARKER + '{"ok": false}\n'
        + MARKER + '{"ok": true, "data": {"old": true}}\n'
        + MARKER + '{"ok": true, "data": {"title": "中文"}}\n'
    )
    assert ToutiaoBackend().call("hot") == {"title": "中文"}
