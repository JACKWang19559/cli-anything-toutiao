"""Click and REPL interface to Toutiao's real web backend."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shlex
import sys
import tempfile
from typing import Any

import click

from cli_anything.toutiao.core.content import article_markdown, article_text
from cli_anything.toutiao.core.drafts import DraftStore
from cli_anything.toutiao.core.errors import ToutiaoError
from cli_anything.toutiao.utils.toutiao_backend import ToutiaoBackend


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _error(json_mode: bool, code: str, message: str) -> None:
    if json_mode:
        click.echo(_json({"ok": False, "error": {"code": code, "message": message}}))
    else:
        click.echo(f"错误 [{code}]: {message}", err=True)


class ToutiaoGroup(click.Group):
    """Keep even Click parsing errors within the machine-readable contract."""

    def main(self, args=None, prog_name=None, complete_var=None,
             standalone_mode=True, **extra):
        arguments = list(sys.argv[1:] if args is None else args)
        json_mode = "--json" in arguments
        try:
            result = super().main(
                args=arguments, prog_name=prog_name, complete_var=complete_var,
                standalone_mode=False, **extra,
            )
        except ToutiaoError as exc:
            _error(json_mode, exc.code, exc.message)
            status = 1
        except click.ClickException as exc:
            _error(json_mode, "INVALID_ARGUMENT", exc.format_message())
            status = exc.exit_code
        except click.exceptions.Exit as exc:
            status = exc.exit_code
        except (KeyboardInterrupt, click.Abort):
            _error(json_mode, "INTERRUPTED", "操作已取消。")
            status = 130
        except UnicodeError:
            _error(json_mode, "INVALID_ENCODING", "文件必须使用 UTF-8 编码。")
            status = 1
        except OSError as exc:
            _error(json_mode, "FILE_ERROR", str(exc))
            status = 1
        else:
            if not standalone_mode:
                return result
            status = 0
        if standalone_mode:
            raise SystemExit(status)
        if status:
            raise click.exceptions.Exit(status)
        return None


def _positive_timeout(ctx, param, value):
    if not math.isfinite(value) or value <= 0:
        raise click.BadParameter("必须是大于 0 的有限秒数。")
    return value


def _backend(ctx: click.Context) -> ToutiaoBackend:
    return ToutiaoBackend(timeout=ctx.obj["timeout"], space=ctx.obj["browser_space"])


def _store(ctx: click.Context) -> DraftStore:
    return DraftStore(ctx.obj["data_dir"])


def _human(value: Any) -> None:
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        _human(value["items"])
        for key in ("warning", "note"):
            if value.get(key):
                click.echo(str(value[key]))
        return
    if isinstance(value, list):
        if not value:
            click.echo("暂无结果。")
        for index, item in enumerate(value, 1):
            if isinstance(item, dict):
                title = item.get("title") or item.get("name") or item.get("id") or ""
                click.echo(f"{item.get('rank', index)}. {title}")
                for key in ("id", "url", "author", "updated_at"):
                    if item.get(key):
                        click.echo(f"   {key}: {item[key]}")
            else:
                click.echo(f"{index}. {item}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if item is None:
                continue
            if isinstance(item, (dict, list)):
                click.echo(f"{key}: {_json(item)}")
            else:
                click.echo(f"{key}: {item}")
        return
    click.echo(str(value))


def _emit(ctx: click.Context, data: Any, text: str | None = None) -> None:
    if ctx.obj["json"]:
        click.echo(_json({"ok": True, "data": data}))
    elif text is not None:
        click.echo(text)
    else:
        _human(data)


def _content(file: Path | None, content: str | None, *, required: bool) -> str | None:
    if file is not None and content is not None:
        raise click.UsageError("--file 与 --content 只能选择一个。")
    if file is not None:
        return file.read_text(encoding="utf-8-sig")
    if content is not None:
        return content
    if required:
        raise click.UsageError("请提供 --file 或 --content。")
    return None


def _export_text(path: Path, content: str, overwrite: bool) -> Path:
    target = path.expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=target.parent, delete=False) as output:
            temporary = output.name
            output.write(content)
        if overwrite:
            os.replace(temporary, target)
            temporary = None
        else:
            try:
                os.link(temporary, target)
            except FileExistsError:
                raise ToutiaoError("FILE_EXISTS", "目标文件已存在；覆盖请使用 --overwrite。") from None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    return target


@click.group(cls=ToutiaoGroup, invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="输出稳定的 JSON 对象，适合脚本与 AI。")
@click.option("--timeout", type=float, default=45.0, show_default=True,
              callback=_positive_timeout, help="浏览器操作超时秒数。")
@click.option("--browser-space", envvar="TOUTIAO_BROWSER_SPACE", help="复用指定 Ego 浏览器任务空间 ID。")
@click.option("--data-dir", type=click.Path(path_type=Path, file_okay=False),
              default=lambda: str(Path.home() / ".cli-anything-toutiao"),
              envvar="TOUTIAO_HOME", show_default="~/.cli-anything-toutiao",
              help="本地草稿数据目录。")
@click.version_option("0.1.0")
@click.pass_context
def cli(ctx, json_mode, timeout, browser_space, data_dir):
    """今日头条 CLI：读取资讯、查询登录状态、管理本地创作草稿。

    全局选项放在命令前，例如：toutiao --json hot --limit 10。
    不带命令时，在交互式终端进入 REPL。
    """
    ctx.ensure_object(dict)
    ctx.obj.update(json=json_mode, timeout=timeout, browser_space=browser_space,
                   data_dir=data_dir.expanduser())
    if ctx.invoked_subcommand is None:
        if sys.stdin.isatty() and sys.stdout.isatty() and not json_mode:
            ctx.invoke(repl)
        elif json_mode:
            _emit(ctx, {"commands": sorted(cli.commands), "help": "toutiao --help"})
        else:
            click.echo(ctx.get_help())


@cli.command()
@click.option("--limit", type=click.IntRange(1, 50), default=20, show_default=True)
@click.pass_context
def hot(ctx, limit):
    """读取当前头条热榜。"""
    _emit(ctx, _backend(ctx).call("hot", limit=limit))


@cli.command()
@click.option("--channel", type=click.Choice(["recommend", "tech", "finance", "hot", "world"]),
              default="recommend", show_default=True)
@click.option("--limit", type=click.IntRange(1, 50), default=20, show_default=True)
@click.pass_context
def feed(ctx, channel, limit):
    """读取推荐或指定频道的已加载资讯。"""
    _emit(ctx, _backend(ctx).call("feed", channel=channel, limit=limit))


@cli.command()
@click.argument("query")
@click.option("--limit", type=click.IntRange(1, 50), default=10, show_default=True)
@click.pass_context
def search(ctx, query, limit):
    """在今日头条搜索关键词。"""
    if not query.strip():
        raise click.BadParameter("搜索关键词不能为空。", param_hint="QUERY")
    _emit(ctx, _backend(ctx).call("search", query=query.strip(), limit=limit))


@cli.command()
@click.argument("reference", metavar="URL_OR_ID")
@click.option("--format", "output_format", type=click.Choice(["text", "markdown"]),
              default="markdown", show_default=True)
@click.option("--output", type=click.Path(path_type=Path, dir_okay=False), help="保存正文到 UTF-8 文件。")
@click.option("--overwrite", is_flag=True, help="允许覆盖输出文件。")
@click.pass_context
def article(ctx, reference, output_format, output, overwrite):
    """读取文章正文，接受头条链接或文章 ID。"""
    if output is not None and output.exists() and not overwrite:
        raise ToutiaoError("FILE_EXISTS", "目标文件已存在；覆盖请使用 --overwrite。")
    data = _backend(ctx).call("article", reference=reference)
    text = article_markdown(data) if output_format == "markdown" else article_text(data)
    if output is not None:
        saved = _export_text(output, text, overwrite)
        data = dict(data, output=str(saved), output_format=output_format)
        _emit(ctx, data, text=f"已保存：{saved}")
    else:
        _emit(ctx, data, text=text)


@cli.group()
def auth():
    """通过浏览器查看和完成登录。"""


@auth.command("status")
@click.pass_context
def auth_status(ctx):
    """查看网页当前是否显示已登录；不读取或输出 Cookie。"""
    _emit(ctx, _backend(ctx).call("auth_status"))


@auth.command("login")
@click.pass_context
def auth_login(ctx):
    """打开今日头条，交给用户完成登录。"""
    _emit(ctx, _backend(ctx).call("auth_login"))


@cli.group()
def creator():
    """头条号创作入口。"""


@creator.command("open")
@click.pass_context
def creator_open(ctx):
    """在浏览器打开真实头条号后台供用户继续操作。"""
    _emit(ctx, _backend(ctx).call("creator_open"))


@cli.command()
@click.pass_context
def doctor(ctx):
    """检查运行环境和浏览器依赖。"""
    _emit(ctx, _backend(ctx).doctor())


@cli.group()
def draft():
    """本地 Markdown 草稿；这些操作不会发布到头条号。"""


@draft.command("create")
@click.option("--title", required=True)
@click.option("--file", "content_file", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option("--content", help="直接传入 Markdown 正文。")
@click.option("--dry-run", is_flag=True, help="校验并返回预期结果，不保存。")
@click.pass_context
def draft_create(ctx, title, content_file, content, dry_run):
    body = _content(content_file, content, required=True)
    _emit(ctx, _store(ctx).create(title, body, dry_run=dry_run))


@draft.command("list")
@click.pass_context
def draft_list(ctx):
    """列出本地草稿。"""
    _emit(ctx, _store(ctx).list())


@draft.command("show")
@click.argument("draft_id")
@click.pass_context
def draft_show(ctx, draft_id):
    """查看一篇本地草稿。"""
    _emit(ctx, _store(ctx).get(draft_id))


@draft.command("update")
@click.argument("draft_id")
@click.option("--title")
@click.option("--file", "content_file", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option("--content")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def draft_update(ctx, draft_id, title, content_file, content, dry_run):
    body = _content(content_file, content, required=False)
    if title is None and body is None:
        raise click.UsageError("请至少提供 --title、--file 或 --content。")
    _emit(ctx, _store(ctx).update(draft_id, title=title, content=body, dry_run=dry_run))


@draft.command("delete")
@click.argument("draft_id")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def draft_delete(ctx, draft_id, dry_run):
    """删除指定本地草稿。"""
    _emit(ctx, _store(ctx).delete(draft_id, dry_run=dry_run))


@draft.command("export")
@click.argument("draft_id")
@click.option("--output", type=click.Path(path_type=Path, dir_okay=False), required=True)
@click.option("--overwrite", is_flag=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def draft_export(ctx, draft_id, output, overwrite, dry_run):
    """导出本地草稿为 Markdown，供头条号编辑器使用。"""
    _emit(ctx, _store(ctx).export(draft_id, output, overwrite=overwrite, dry_run=dry_run))


def _split_repl(line: str) -> list[str]:
    parser = shlex.shlex(line, posix=True)
    parser.whitespace_split = True
    parser.commenters = ""
    if os.name == "nt":
        parser.escape = ""
    return list(parser)


def _repl_command(parts: list[str]) -> str | None:
    """Find the root command while respecting values of global options."""
    options = {option: parameter for parameter in cli.params for option in parameter.opts}
    index = 0
    while index < len(parts):
        token = parts[index]
        if token == "--":
            return parts[index + 1] if index + 1 < len(parts) else None
        if not token.startswith("-"):
            return token
        option = options.get(token.split("=", 1)[0])
        if option is None:
            return None
        index += 1 if option.is_flag or "=" in token else 2
    return None


@cli.command()
@click.pass_context
def repl(ctx):
    """进入交互模式；输入 help 查看命令，quit 退出。"""
    json_mode = ctx.obj["json"]
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    skin = None
    prompt_session = None
    if interactive and not json_mode:
        from cli_anything.toutiao.utils.repl_skin import ReplSkin

        history_dir = ctx.obj["data_dir"]
        history_dir.mkdir(parents=True, exist_ok=True)
        skin = ReplSkin("toutiao", version="0.1.0", history_file=str(history_dir / "history"))
        skin.skill_install_cmd = "python -m pip install -e ./agent-harness"
        if skin.skill_path:
            skin.global_skill_path = skin.skill_path
        skin.print_banner()
        prompt_session = skin.create_prompt_session()
    prefix = ["--timeout", str(ctx.obj["timeout"]), "--data-dir", str(ctx.obj["data_dir"])]
    if ctx.obj["browser_space"] is not None:
        prefix.extend(["--browser-space", str(ctx.obj["browser_space"])])
    if json_mode:
        prefix.append("--json")
    while True:
        try:
            line = skin.get_input(prompt_session) if skin else input().strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        try:
            parts = _split_repl(line)
            if not parts:
                continue
            if parts[0] in {"exit", "quit"}:
                break
            if parts[0] == "help":
                parts = parts[1:] + ["--help"]
            if _repl_command(parts) == "repl":
                _error(json_mode, "INVALID_ARGUMENT", "已处于 REPL 中。")
                continue
            cli.main(prefix + parts, standalone_mode=False, prog_name="toutiao")
        except click.exceptions.Exit:
            continue
        except ValueError as exc:
            _error(json_mode, "INVALID_ARGUMENT", str(exc))
    if skin:
        skin.print_goodbye()


def main() -> None:
    """Entry point with UTF-8 output, including redirected Windows output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    cli()


if __name__ == "__main__":
    main()
