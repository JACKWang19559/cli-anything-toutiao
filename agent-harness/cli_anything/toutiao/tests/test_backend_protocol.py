"""Regression coverage for Ego's framed results arriving on stderr."""

import json
import subprocess

import pytest

from cli_anything.toutiao.core.errors import ToutiaoError
from cli_anything.toutiao.utils import toutiao_backend as backend_module
from cli_anything.toutiao.utils.toutiao_backend import MARKER, ToutiaoBackend


def invoke(monkeypatch, *, stdout="", stderr="", returncode=0):
    monkeypatch.setattr(backend_module.shutil, "which", lambda name: "ego-browser")
    monkeypatch.setattr(
        backend_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, returncode, stdout, stderr),
    )
    return ToutiaoBackend().call("hot", limit=3)


@pytest.mark.parametrize("channel", ["stdout", "stderr"])
def test_framed_success_is_accepted_on_either_stream(monkeypatch, channel):
    data = {"items": [{"id": "7701568905705308681", "title": "测试"}]}
    frame = MARKER + json.dumps({"ok": True, "data": data}, ensure_ascii=False)
    streams = {"stdout": "startup diagnostics\n", "stderr": "private account diagnostic\n"}
    streams[channel] += frame + "\n"
    assert invoke(monkeypatch, **streams) == data


def test_framed_error_on_stderr_preserves_domain_error(monkeypatch):
    frame = MARKER + json.dumps({"ok": False, "error": {
        "code": "verification_required", "message": "请完成验证",
    }}, ensure_ascii=False)
    with pytest.raises(ToutiaoError) as raised:
        invoke(monkeypatch, stderr="private diagnostic\n" + frame + "\n")
    assert raised.value.code == "verification_required"
    assert raised.value.message == "请完成验证"


def test_unframed_embedded_marker_in_stderr_is_never_a_result(monkeypatch):
    fake_frame = "debug says " + MARKER + '{"ok":true,"data":{"secret":"private diagnostic"}}'
    with pytest.raises(ToutiaoError) as raised:
        invoke(monkeypatch, stderr=fake_frame)
    assert raised.value.code == "browser_failed"
    assert "private diagnostic" not in raised.value.message


def test_nonzero_process_cannot_succeed_via_stderr_frame(monkeypatch):
    frame = MARKER + '{"ok":true,"data":{"items":[]}}'
    with pytest.raises(ToutiaoError) as raised:
        invoke(monkeypatch, stderr=frame, returncode=1)
    assert raised.value.code == "browser_failed"


def test_malformed_stderr_frame_is_a_protocol_error(monkeypatch):
    with pytest.raises(ToutiaoError) as raised:
        invoke(monkeypatch, stderr=MARKER + 'not-json\n')
    assert raised.value.code == "invalid_backend_response"
