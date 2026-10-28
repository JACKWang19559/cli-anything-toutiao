# 今日头条 CLI

[![Tests](https://github.com/JACKWang19559/cli-anything-toutiao/actions/workflows/test.yml/badge.svg)](https://github.com/JACKWang19559/cli-anything-toutiao/actions/workflows/test.yml)

基于 [CLI-Anything](https://github.com/HKUDS/CLI-Anything) 构建的今日头条命令行工具：从真实浏览器读取资讯，管理本地创作草稿，并提供适合 agent 调用的 JSON 输出。

当前版本 `0.1.0`。使用 CLI-Anything 的构建流程、Python 命名空间、Click + REPL 结构，并复用其统一终端皮肤。上游固定版本和许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 功能

| 命令 | 用途 |
| --- | --- |
| `hot` | 读取今日头条热榜 |
| `feed` | 读取推荐、科技、财经、热点、国际频道 |
| `search` | 搜索资讯 |
| `article` | 读取文章正文，可导出文本或 Markdown |
| `auth status` / `auth login` | 检查会话、打开头条页面供用户登录 |
| `creator open` | 打开头条号创作入口 |
| `draft create/list/show/update/delete/export` | 本地草稿持久化与导出 |
| `doctor` | 检查运行依赖和配置 |

**草稿保存在本地 SQLite 数据库。本版本尚不支持向头条号上传草稿或发布文章。** 登录由用户在浏览器中完成；命令不会读取或输出账号密码。

## 安装

需要 Python 3.10+，在线命令还需要 [ego lite 浏览器](https://lite.ego.app/) 提供的 `ego-browser`。下载安装并完成首次设置，Windows 上重新打开终端，再确认 `ego-browser skill` 能显示当前浏览器用法。没有浏览器时仍可使用本地草稿功能。

Windows PowerShell，在此仓库根目录可使用安装脚本和启动器：

```powershell
git clone https://github.com/JACKWang19559/cli-anything-toutiao.git
cd cli-anything-toutiao
powershell -ExecutionPolicy Bypass -File .\install.ps1
.\toutiao.cmd --help
.\toutiao.cmd --json hot --limit 5
```

安装脚本创建本目录 `.venv` 并安装项目；若 `python` 不可用，可通过 `-Python 'C:\实际路径\python.exe'` 指定 Python 3.10+。`toutiao.cmd` 使用仓库内环境，无需激活或修改全局 PATH。

也可以手动安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './agent-harness[dev]'
.\.venv\Scripts\toutiao.exe --help
.\.venv\Scripts\toutiao.exe doctor
```

激活环境后可直接使用 `toutiao`，也可使用同义命令 `cli-anything-toutiao`：

```powershell
.\.venv\Scripts\Activate.ps1
toutiao --help
```

如 PowerShell 策略不允许激活，继续使用 `.\.venv\Scripts\toutiao.exe` 即可。

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e './agent-harness[dev]'
.venv/bin/toutiao --help
```

## 读取资讯

```powershell
toutiao hot --limit 10
toutiao --json hot --limit 10
toutiao feed --channel tech --limit 10
toutiao --json search "人工智能" --limit 5
toutiao article "https://www.toutiao.com/article/真实文章ID/"
toutiao article "真实文章ID" --format markdown --output article.md
```

文章参数接受实际文章 URL 或数字 ID；将示例占位符替换为搜索/频道返回的文章链接。已有导出文件默认不会被覆盖，确需覆盖时添加 `--overwrite`。

`feed --channel` 支持 `recommend`、`tech`、`finance`、`hot`、`world`。`--limit` 是返回数量上限，范围为 1–50；实际结果可能少于该值，取决于网页已加载内容。搜索、频道和热榜可能包含专题或视频；`article` 仅支持文章链接，且仅在页面提供可提取正文时返回正文。

支持的文章链接为 `toutiao.com`、`www.toutiao.com` 或 `m.toutiao.com` 下的 `/article/ID/`、`/aID/`、`/iID/`。短链接、热榜专题和视频应先打开，取得真实文章链接后再读取。

## 登录与创作入口

```powershell
toutiao auth status
toutiao auth login
toutiao creator open
```

`auth login` 打开今日头条首页并交给用户操作；在页面点击登录，完成登录或验证码后，再运行 `auth status`。打开页面成功不代表登录成功。会话保留在浏览器中，CLI 不导出 Cookie。

## 本地草稿

```powershell
toutiao draft create --title "今日观察" --content "这里是正文。"
toutiao draft create --title "行业分析" --file .\article.md
toutiao draft list
toutiao draft show 草稿ID
toutiao draft update 草稿ID --title "修订后的标题" --file .\article-v2.md
toutiao draft export 草稿ID --output .\draft.md
toutiao draft delete 草稿ID --dry-run
toutiao draft delete 草稿ID
```

草稿 ID 从创建或列表结果中取得。文件使用 UTF-8；`--file` 和 `--content` 二选一。`create`、`update`、`delete`、`export` 支持 `--dry-run`，用于检查操作而不更改数据库或写出文件。导出的 Markdown 可供后续手工发布使用。

## Agent 调用与配置

全局选项放在子命令之前：

```powershell
toutiao --json --timeout 60 hot --limit 5
toutiao --data-dir .\my-data --json draft list
```

| 选项 | 环境变量 | 默认值 |
| --- | --- | --- |
| `--data-dir` | `TOUTIAO_HOME` | `~/.cli-anything-toutiao` |
| `--browser-space` | `TOUTIAO_BROWSER_SPACE` | 自动管理浏览器任务空间 |
| `--timeout` | — | 45 秒 |
| `--json` | — | 默认输出便于阅读的文本 |

通常无需设置浏览器空间。`--browser-space` 用于需要复用已知 ego-browser 任务空间的高级场景；不要随意填入不存在的 ID。
复用同一个空间时应串行运行命令，以免两个进程同时切换页面。自动管理的只读任务成功后会关闭自己的页面；登录和创作入口会保留页面交给用户。

成功输出：

```json
{"ok": true, "data": {}}
```

错误输出并返回非零退出码：

```json
{"ok": false, "error": {"code": "ERROR_CODE", "message": "具体错误说明"}}
```

交互式终端中无参数运行进入 REPL，支持复用同一套命令；输入 `help` 查看帮助，`quit` 退出。在管道环境中无参数显示帮助，`--json` 单独使用则返回命令列表。Agent 使用一次性子命令即可。完整 agent 使用说明位于 [skills/cli-anything-toutiao/SKILL.md](skills/cli-anything-toutiao/SKILL.md)，安装包也包含相同 skill。

## 验证与限制

开发测试还需要 Node.js 18+（用于验证浏览器适配器的纯函数）。默认运行离线单元测试和安装后命令测试：

```powershell
$env:Path = "$PWD\.venv\Scripts;$env:Path"
$env:CLI_ANYTHING_FORCE_INSTALLED = '1'
.\.venv\Scripts\python.exe -m pytest agent-harness/cli_anything/toutiao/tests -v --tb=short
```

真实网页工作流需显式启用，使用调用方已拥有的 Ego 任务空间；缺少依赖或无法访问时会失败，不会用模拟结果替代：

```powershell
$env:TOUTIAO_BROWSER_SPACE = '你的已有任务空间ID'
.\.venv\Scripts\python.exe -m pytest agent-harness/cli_anything/toutiao/tests -m live -v --tb=short
```

测试计划和执行记录见 [TEST.md](agent-harness/cli_anything/toutiao/tests/TEST.md)。离线测试与真实网页测试分别报告，测试通过不意味着所有账号和网络都可访问所有内容。

今日头条网页布局、登录要求、验证页面和内容可见性可能变化。后端读取失败时会报告错误，不用固定内容填充结果。此项目是非官方 CLI，不使用头条内部签名破解，不提供验证码绕过或自动发布。

Markdown 保留正文与原始图片链接，不下载图片；站点签名图片链接可能过期。此版本读取已加载的首屏/首批结果，尚未实现自动翻页。

## 开源许可

本项目以 [Apache-2.0](LICENSE) 许可开源。上游代码归属及来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。GitHub Actions 在 Windows 和 Linux、Python 3.10 和 3.12 上运行离线测试及打包；真实头条网页测试需在本地显式启用。
