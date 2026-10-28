# 今日头条 CLI 测试计划

此计划在测试实现之前编写。记录日期：2026-10-28（Asia/Shanghai）。

## 测试清单

- `test_driver.py` / `test_browser_driver.mjs`：Node.js 离线测试真实 JS 规范化函数，覆盖 19 位 ID、编码跳转、内容类型过滤、异常行，以及模拟任务空间的结束/交接生命周期；Node.js 为测试依赖，缺失时明确失败。
- `test_backend_protocol.py`：浏览器结果标记位于 stderr 时的协议回归、诊断隔离与非零退出码处理。
- `test_core.py`：约 15–25 个单元测试，覆盖本地草稿、输入校验、导出与浏览器数据解析。
- `test_full_e2e.py`：约 8–15 个安装后命令测试，覆盖 JSON 协议、帮助与完整本地草稿工作流。
- 真实头条网页验证：通过真实浏览器检查热榜、搜索、文章、频道页面与登录入口；记录成功项和受登录或页面限制的项目。

## 单元测试范围

- 草稿存储：创建、读取、列表、更新、删除，UUID 或 ID 校验，SQLite 持久化和不存在的草稿。
- 草稿内容：中文、多行内容、空标题/空正文、文件输入编码，以及 `--file` 和 `--content` 的互斥关系。
- 写入行为：`--dry-run` 不创建或修改记录；输出文件默认不覆盖已有文件，`--overwrite` 才允许覆盖。
- 网页解析和输入：文章 URL/ID 规范化、非头条网址拒绝、列表去重、正文缺失和挑战/登录页面的可识别错误。
- JSON 与错误：成功数据包和错误数据包的结构，错误退出码，JSON 输出不混入日志或 REPL 横幅。

## 端到端工作流

1. **本地创作整理**：用安装后的 CLI 从 UTF-8 文件创建草稿 → 列表 → 查看 → 更新 → 导出 Markdown → 删除；校验正文内容和最终存储状态。
2. **预演与防覆盖**：创建/更新/删除预演 → 验证存储未变；向已有输出路径导出 → 验证被拒绝且原文件未变。
3. **机器调用**：安装后从任意目录执行 `--help`、`--version`、`--json` 命令；解析 stdout JSON 并验证退出码。
4. **真实网页读取**：读取热榜、搜索词、频道与文章；结果必须来自实际网页，正文和列表不得以固定演示数据代替。

## 执行方式

在仓库根目录安装开发依赖并验证真实入口：

```powershell
.\.venv\Scripts\python.exe -m pip install -e './agent-harness[dev]'
$env:Path = "$PWD\.venv\Scripts;$env:Path"
$env:CLI_ANYTHING_FORCE_INSTALLED = '1'
.\.venv\Scripts\python.exe -m pytest agent-harness/cli_anything/toutiao/tests -v --tb=short
```

子进程测试通过 `_resolve_cli('cli-anything-toutiao')` 查找安装后的命令，不依赖固定工作目录。离线测试与真实网页检查分别记录；离线通过不代表在线接口或账号登录已验证。

## 测试结果

### 本地草稿专项计划（test_drafts.py，实现前补充）

预计 15–20 项：不存在的目录读取/预演不落盘、中文和多行内容持久化、
UUID/标题/正文参数校验、更新与删除事务、并发创建与不同字段并发更新、
数据库损坏可识别错误、Markdown UTF-8 导出、原文件防覆盖、显式覆盖、
预演导出不创建目录、数据库文件禁止作为导出目标、并发导出无部分文件。

### 资讯与浏览器适配专项计划（test_core.py，实现前补充）

纯数字长 ID 不丢精度；支持文章 URL 规范化；拒绝其他域名、用户信息、
显式端口、非文章路径与非法 ID。校验纯文本/Markdown 内容和来源格式。
模拟浏览器子进程，验证依赖缺失、超时、无法启动、无结果、损坏协议、
结构化失败、用户接管提示与成功结果解析。查询内容包含引号和 shell
字符时只能进入请求 JSON，不进入可执行脚本或命令行；临时文件须清理。

执行结果见下方记录。


## 2026-10-28 执行结果（Asia/Shanghai）

以下日志中的本机项目绝对路径已统一替换为 `<PROJECT>`；测试名称、结果与运行时间保持原样。

- 平台：Windows，Python 3.12.14，pytest 9.2.0，Ego CLI skill v2.1.0。
- 已通过 `pip install -e ./agent-harness[dev]` 安装，设置 `CLI_ANYTHING_FORCE_INSTALLED=1`；子进程测试实际调用安装后的命令。
- 离线：118 passed，1 live deselected，6.01 秒。其中一个 pytest 用例内执行 16 项 Node 测试，全部通过，不重复计入 118。
- 在线：1 个组合工作流通过，40.42 秒；包含真实热榜、科技频道、人工智能搜索、文章 `7701468351923257896` 的 Markdown 导出、登录状态检查。线上验证运行时测试集合为 112 项，之后只增加了离线回归用例。
- 另验证了自动管理任务成功后的关闭流程，研究任务空间已经结束。
- 已构建 wheel，并检查包内浏览器脚本、agent skill、许可证及命令入口。
- 未执行登录交接/创作入口的真实人工流程，未测试未登录账号、验证码页面、所有频道、自动翻页或发布。交接生命周期使用独立单元测试验证。此版本不包含云端草稿和发布实现。
- `--limit` 是上限；读取当前已加载结果。Markdown 图片保留原站链接，可能过期。

### 离线完整输出

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.2.0, pluggy-1.7.0 -- <PROJECT>\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: <PROJECT>\agent-harness
configfile: pyproject.toml
collecting ... collected 119 items / 1 deselected / 118 selected

agent-harness\cli_anything\toutiao\tests\test_backend_protocol.py::test_framed_success_is_accepted_on_either_stream[stdout] PASSED [  0%]
agent-harness\cli_anything\toutiao\tests\test_backend_protocol.py::test_framed_success_is_accepted_on_either_stream[stderr] PASSED [  1%]
agent-harness\cli_anything\toutiao\tests\test_backend_protocol.py::test_framed_error_on_stderr_preserves_domain_error PASSED [  2%]
agent-harness\cli_anything\toutiao\tests\test_backend_protocol.py::test_unframed_embedded_marker_in_stderr_is_never_a_result PASSED [  3%]
agent-harness\cli_anything\toutiao\tests\test_backend_protocol.py::test_nonzero_process_cannot_succeed_via_stderr_frame PASSED [  4%]
agent-harness\cli_anything\toutiao\tests\test_backend_protocol.py::test_malformed_stderr_frame_is_a_protocol_error PASSED [  5%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_argument_errors_are_json[args0] PASSED [  5%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_argument_errors_are_json[args1] PASSED [  6%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_argument_errors_are_json[args2] PASSED [  7%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_argument_errors_are_json[args3] PASSED [  8%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_argument_errors_are_json[args4] PASSED [  9%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_argument_errors_are_json[args5] PASSED [ 10%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_json_without_command_is_discoverable PASSED [ 11%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_noninteractive_no_command_prints_help PASSED [ 11%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_backend_error_is_json PASSED [ 12%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_unicode_result_and_options_reach_backend PASSED [ 13%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_draft_content_options_are_mutually_exclusive PASSED [ 14%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_invalid_file_encoding_is_structured PASSED [ 15%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_json_repl_has_no_banner_or_prompt PASSED [ 16%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_article_export_and_overwrite_guard PASSED [ 16%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_article_text_mode PASSED [ 17%]
agent-harness\cli_anything\toutiao\tests\test_cli.py::test_repl_quotes_and_windows_paths PASSED [ 18%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_reference_canonicalization_preserves_long_id[7701568905705308681] PASSED [ 19%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_reference_canonicalization_preserves_long_id[  7701568905705308681  ] PASSED [ 20%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_reference_canonicalization_preserves_long_id[https://www.toutiao.com/article/7701568905705308681/?source=feed#comment] PASSED [ 21%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_reference_canonicalization_preserves_long_id[http://toutiao.com/article/7701568905705308681] PASSED [ 22%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_reference_canonicalization_preserves_long_id[https://m.toutiao.com/a7701568905705308681/] PASSED [ 22%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_reference_canonicalization_preserves_long_id[https://www.toutiao.com/i7701568905705308681/] PASSED [ 23%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://evil.example/article/7701568905705308681/] PASSED [ 24%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com.evil.example/article/7701568905705308681/] PASSED [ 25%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://evil.example@www.toutiao.com/article/7701568905705308681/] PASSED [ 26%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://user:secret@www.toutiao.com/article/7701568905705308681/] PASSED [ 27%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://@www.toutiao.com/article/7701568905705308681/] PASSED [ 27%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com:443/article/7701568905705308681/] PASSED [ 28%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com:0/article/7701568905705308681/] PASSED [ 29%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com:invalid/article/7701568905705308681/] PASSED [ 30%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com:65536/article/7701568905705308681/] PASSED [ 31%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[file://www.toutiao.com/article/7701568905705308681/] PASSED [ 32%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[//www.toutiao.com/article/7701568905705308681/] PASSED [ 33%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com/video/7701568905705308681/] PASSED [ 33%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com/article/7701568905705308681/extra] PASSED [ 34%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com/article/12x45/] PASSED [ 35%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com/article/1234/] PASSED [ 36%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[https://www.toutiao.com/article/1111111111111111111111111111111/] PASSED [ 37%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[7701568905705308681.0] PASSED [ 38%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[1e18] PASSED [ 38%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_rejects_untrusted_or_malformed_references[] PASSED [ 39%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_article_text_includes_only_available_metadata_and_source PASSED [ 40%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_markdown_escapes_title_preserves_extracted_body_and_source PASSED [ 41%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_markdown_falls_back_to_article_text PASSED [ 42%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_browser_request_keeps_user_text_out_of_script_and_shell PASSED [ 43%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_browser_article_passes_normalized_url PASSED [ 44%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_browser_search_trims_query PASSED [ 44%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_invalid_query_rejected_before_browser[] PASSED [ 45%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_invalid_query_rejected_before_browser[   ] PASSED [ 46%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_invalid_query_rejected_before_browser[query2] PASSED [ 47%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_invalid_limits_rejected_before_browser[0] PASSED [ 48%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_invalid_limits_rejected_before_browser[51] PASSED [ 49%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_invalid_limits_rejected_before_browser[-1] PASSED [ 50%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_invalid_limits_rejected_before_browser[True] PASSED [ 50%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_invalid_limits_rejected_before_browser[1.5] PASSED [ 51%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_invalid_limits_rejected_before_browser[2] PASSED [ 52%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_unknown_channel_and_operation_fail_before_browser PASSED [ 53%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_nonpositive_timeout_rejected[0] PASSED [ 54%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_nonpositive_timeout_rejected[-1] PASSED [ 55%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_missing_backend_has_actionable_error_and_doctor_status PASSED [ 55%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_process_failure_becomes_domain_error_and_cleans_temp_files[exception0-browser_timeout] PASSED [ 56%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_process_failure_becomes_domain_error_and_cleans_temp_files[exception1-backend_unavailable] PASSED [ 57%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_malformed_protocol_returns_domain_error[__TOUTIAO_RESULT__not json] PASSED [ 58%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_malformed_protocol_returns_domain_error[__TOUTIAO_RESULT__[]] PASSED [ 59%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_malformed_protocol_returns_domain_error[__TOUTIAO_RESULT__{"ok": "true", "data": {}}] PASSED [ 60%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_malformed_protocol_returns_domain_error[__TOUTIAO_RESULT__{}] PASSED [ 61%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_malformed_failure_payload_returns_domain_error[None] PASSED [ 61%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_malformed_failure_payload_returns_domain_error[error1] PASSED [ 62%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_malformed_failure_payload_returns_domain_error[bad error] PASSED [ 63%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_structured_browser_error_preserved PASSED [ 64%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_missing_result_sanitizes_diagnostics[secret-account-url-browser_failed] PASSED [ 65%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_missing_result_sanitizes_diagnostics[EGO_TASK_SPACE_INACTIVE secret-account-url-browser_control_required] PASSED [ 66%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_nonzero_exit_cannot_report_success PASSED [ 66%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_success_missing_data_is_rejected PASSED [ 67%]
agent-harness\cli_anything\toutiao\tests\test_core.py::test_only_marker_lines_are_results_and_last_result_wins PASSED [ 68%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_read_empty_store_does_not_create_directory PASSED [ 69%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_dry_run_create_never_creates_store PASSED [ 70%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_create_round_trip_in_separate_store PASSED [ 71%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_invalid_title_does_not_create_database[] PASSED [ 72%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_invalid_title_does_not_create_database[  ] PASSED [ 72%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_invalid_title_does_not_create_database[a\nb] PASSED [ 73%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_invalid_title_does_not_create_database[a\rb] PASSED [ 74%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_invalid_title_does_not_create_database[None] PASSED [ 75%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_nontext_content_rejected PASSED [ 76%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_bad_ids_rejected_without_storage[../../outside] PASSED [ 77%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_bad_ids_rejected_without_storage[] PASSED [ 77%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_bad_ids_rejected_without_storage['; DROP TABLE drafts; --] PASSED [ 78%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_update_preserves_unmodified_fields_and_creation_time PASSED [ 79%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_update_without_changes_rejected PASSED [ 80%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_dry_run_update_and_delete_leave_database_bytes_unchanged PASSED [ 81%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_delete_persists_and_missing_delete_is_error PASSED [ 82%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_concurrent_create_retains_every_draft PASSED [ 83%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_concurrent_partial_updates_do_not_lose_fields PASSED [ 83%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_export_writes_complete_utf8_markdown PASSED [ 84%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_export_existing_target_requires_overwrite PASSED [ 85%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_dry_run_export_does_not_create_parent PASSED [ 86%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_export_cannot_overwrite_own_database PASSED [ 87%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_corrupt_database_reports_domain_error PASSED [ 88%]
agent-harness\cli_anything\toutiao\tests\test_drafts.py::test_competing_exports_cannot_overwrite_each_other PASSED [ 88%]
agent-harness\cli_anything\toutiao\tests\test_driver.py::test_browser_driver_normalization_and_lifecycle PASSED [ 89%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_help PASSED [ 90%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_version PASSED [ 91%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_no_argument_non_tty PASSED [ 92%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_json_discovery PASSED [ 93%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_json_argument_errors[args0] PASSED [ 94%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_json_argument_errors[args1] PASSED [ 94%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_json_argument_errors[args2] PASSED [ 95%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_doctor_does_not_launch_browser PASSED [ 96%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_draft_file_round_trip PASSED [ 97%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_draft_dry_run_has_no_side_effects PASSED [ 98%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_draft_export_preserves_existing_file PASSED [ 99%]
agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_installed_json_repl PASSED [100%]

====================== 118 passed, 1 deselected in 6.01s ======================
```

### 在线完整输出

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.2.0, pluggy-1.7.0 -- <PROJECT>\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: <PROJECT>\agent-harness
configfile: pyproject.toml
collecting ... collected 112 items / 111 deselected / 1 selected

agent-harness\cli_anything\toutiao\tests\test_full_e2e.py::test_live_reader_workflow PASSED [100%]

===================== 1 passed, 111 deselected in 40.42s ======================
```
