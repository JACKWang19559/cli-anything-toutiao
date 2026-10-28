# cli-anything-toutiao

今日头条 CLI，版本 0.1.0。提供真实网页资讯读取、本地 SQLite 草稿、JSON 输出与交互 REPL。

## 安装与依赖

Python 3.10+。从仓库根目录运行 `python -m pip install -e ./agent-harness`，或在 `agent-harness` 内运行 `python -m pip install -e .`。安装后使用 `toutiao` 或 `cli-anything-toutiao`，两个入口等价。

在线功能调用 [ego lite](https://lite.ego.app/) 提供的 `ego-browser`。下载安装并完成首次设置后，Windows 用户需重新打开终端。先验证 `ego-browser skill`，再运行 `toutiao doctor`。本地草稿不需要浏览器。浏览器保存账号会话，登录需用户在浏览器中完成。

## 命令

```text
toutiao [--json] [--timeout 45] [--browser-space ID] [--data-dir PATH] COMMAND

hot [--limit 20]
feed [--channel recommend|tech|finance|hot|world] [--limit 20]
search QUERY [--limit 10]
article URL_OR_ID [--format text|markdown] [--output PATH] [--overwrite]
auth status
auth login
creator open
doctor
draft create --title TITLE (--file PATH | --content TEXT) [--dry-run]
draft list
draft show ID
draft update ID [--title TITLE] [--file PATH | --content TEXT] [--dry-run]
draft delete ID [--dry-run]
draft export ID --output PATH [--overwrite] [--dry-run]
```

在交互终端无参数进入 REPL，`help` 查看帮助，`quit` 退出；在非交互环境无参数显示帮助。`--help` 查看当前安装版本的准确选项。

## 示例

```powershell
toutiao --json hot --limit 5
toutiao --json search "人工智能" --limit 5
toutiao feed --channel tech
toutiao draft create --title "观察" --file article.md
toutiao draft list
toutiao draft export 草稿ID --output draft.md
```

文章 ID/URL 使用资讯列表的真实结果，草稿 ID 使用创建结果。`--limit` 为 1–50 的结果上限，网页实际加载结果可能更少。文章命令接受头条域名下的 `/article/ID/`、`/aID/`、`/iID/`，不接受短链接、专题或视频链接。本地文件按 UTF-8 读写。导出默认拒绝覆盖，`--overwrite` 显式允许覆盖。草稿变更立即保存到 SQLite，预演使用 `--dry-run`。

## 输出与状态

`--json` 输出 `{"ok":true,"data":...}`。错误输出 `{"ok":false,"error":{"code":"...","message":"..."}}` 并返回非零退出码。全局选项应写在子命令前。

数据目录默认 `~/.cli-anything-toutiao`，可用 `TOUTIAO_HOME` 或 `--data-dir` 覆盖。默认自动管理浏览器任务空间，通常无需配置；高级调用方可用 `TOUTIAO_BROWSER_SPACE` 或 `--browser-space` 指定已有任务空间。超时默认 45 秒。
同一任务空间应串行调用。Markdown 保留原始图片链接，未下载图片，签名链接可能过期。搜索和频道读取当前已加载结果，暂不自动翻页。

`auth login` 和 `creator open` 仅打开真实页面，不代表登录成功或内容发布成功。草稿是本地记录，此版本没有上传草稿或线上发布能力。网页内容变化、验证码或登录限制会导致在线命令失败。

## CLI-Anything 来源

依据 https://github.com/HKUDS/CLI-Anything 的 Codex/HARNESS 流程构建，使用其统一 `repl_skin.py`，版本 `34f519533bc175d2fe287ab8316b0dd99bb9cc43`，Apache-2.0。今日头条闭源，分析依据为实际网页而非服务器源码。本项目为独立非官方适配。

包内 `skills/SKILL.md` 提供 agent 使用约定。仓库内测试计划与执行记录位于 `tests/TEST.md`。

开发验证需要安装 `[dev]` 依赖和 Node.js 18+，默认 `pytest` 运行离线测试。真实网页测试显式使用 `pytest -m live`，并通过 `TOUTIAO_BROWSER_SPACE` 指定调用方拥有的任务空间。
