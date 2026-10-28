"""Invoke the installed ego-browser engine, retaining credentials in the browser."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from cli_anything.toutiao.core.content import article_url
from cli_anything.toutiao.core.errors import ToutiaoError

MARKER = "__TOUTIAO_RESULT__"
OPERATIONS = {"hot", "feed", "search", "article", "auth_status", "auth_login", "creator_open"}


class ToutiaoBackend:
    def __init__(self, timeout: float = 45, space: str | None = None):
        if timeout <= 0:
            raise ToutiaoError("invalid_timeout", "timeout 必须大于 0。")
        self.timeout = timeout
        self.space = space

    def doctor(self) -> dict:
        executable = shutil.which("ego-browser")
        return {
            "ready": bool(executable),
            "backend": "ego-browser",
            "executable": executable,
            "browser_space": self.space,
            "python": __import__("sys").version.split()[0],
            "note": "这里只检查本机依赖；运行 auth status 检查网站访问和登录状态。",
            "install_hint": None if executable else "请安装并启动 Ego Lite，确保 ego-browser 在 PATH 中，然后运行 ego-browser skill。",
        }

    def call(self, operation: str, **kwargs):
        if operation not in OPERATIONS:
            raise ToutiaoError("unsupported_operation", "此版本不支持该操作。")
        if operation == "article":
            kwargs["url"] = article_url(kwargs.pop("reference"))
        if operation == "search":
            query = kwargs.get("query", "").strip()
            if not query or len(query) > 200:
                raise ToutiaoError("invalid_query", "关键词长度必须为 1–200 个字符。")
            kwargs["query"] = query
        if operation in {"hot", "feed", "search"}:
            limit = kwargs.get("limit", 20)
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
                raise ToutiaoError("invalid_limit", "limit 必须为 1–50。")
            kwargs["limit"] = limit
        if operation == "feed" and kwargs.get("channel", "recommend") not in {"recommend", "tech", "finance", "hot", "world"}:
            raise ToutiaoError("invalid_channel", "未知频道。")
        executable = shutil.which("ego-browser")
        if not executable:
            raise ToutiaoError("backend_missing", "未找到 ego-browser。请安装并启动 Ego Lite，并把 ego-browser 加入 PATH。")
        space = self.space
        request = {"operation": operation, "args": kwargs, "timeout_ms": int(self.timeout * 1000),
                   "space": int(space) if space and space.isdigit() else space or f"toutiao-cli-{uuid.uuid4().hex[:10]}",
                   "managed_space": not bool(space)}
        driver = Path(__file__).with_name("browser_driver.mjs").resolve().as_uri()
        with tempfile.TemporaryDirectory(prefix="toutiao-cli-") as folder:
            root = Path(folder)
            request_file = root / "request.json"
            request_file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            script = root / "run.mjs"
            # User text lives in JSON, never in shell source or executable JavaScript.
            script.write_text(
                "const fs = await import('node:fs/promises');\n"
                f"const request = JSON.parse(await fs.readFile(new URL({json.dumps(request_file.as_uri())}), 'utf8'));\n"
                f"const driver = await import({json.dumps(driver)});\n"
                "await driver.run(request);\n", encoding="utf-8")
            command = [executable, "nodejs", "-e", f"await import('{script.as_uri()}')"]
            try:
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                        timeout=self.timeout + 10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired:
                raise ToutiaoError("browser_timeout", "浏览器操作超时。请检查 Ego Lite 页面，必要时完成登录或验证，再重试；也可增大 --timeout。") from None
            except OSError:
                raise ToutiaoError("backend_unavailable", "无法启动 ego-browser，请先确认 Ego Lite 已启动。") from None
        # Ego Lite console output can arrive on stderr when called without a console.
        # Accept only our exact framed result, never forward arbitrary diagnostics.
        lines = [line.partition(MARKER)[2] for stream in (result.stdout, result.stderr)
                 for line in stream.splitlines() if line.startswith(MARKER)]
        if not lines:
            # Do not echo browser diagnostics, which can contain account URLs or credentials.
            code = "browser_control_required" if any(s in result.stderr for s in ("EGO_TASK", "control", "inactive")) else "browser_failed"
            raise ToutiaoError(code, "Ego Lite 未返回有效结果。请检查浏览器是否启动、任务空间是否由用户接管，或运行 ego-browser skill 排查。")
        try:
            payload = json.loads(lines[-1])
            if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
                raise ValueError
        except (ValueError, TypeError):
            raise ToutiaoError("invalid_backend_response", "浏览器返回了无法解析的结果。") from None
        if not payload["ok"]:
            error = payload.get("error", {})
            if not isinstance(error, dict):
                raise ToutiaoError("invalid_backend_response", "浏览器返回了无法解析的错误结果。")
            raise ToutiaoError(error.get("code", "browser_failed"), error.get("message", "浏览器操作失败。"))
        if result.returncode != 0 or "data" not in payload:
            raise ToutiaoError("browser_failed", "浏览器操作未正常完成。")
        return payload["data"]
