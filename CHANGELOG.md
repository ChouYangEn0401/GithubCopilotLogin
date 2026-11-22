# Changelog

格式參考 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-TW/1.1.0/)，版號遵循 [SemVer 2.0.0](https://semver.org/lang/zh-TW/)。

## [Unreleased]

## [0.2.0] - 2026-11-23

### Added
- 統一呼叫介面（`INTERFACE_VERSION = "1"`；`claude_subscription`、`chatgpt_login` 用同一組名字），給多來源的 LLM 函式庫包裝用：
  - `ask()` 的第一個參數可以是訊息清單；新參數 `system`（接在提示最前面）；`model` 預設改成 `None`（＝copilot 自己的預設，跟以前的 `""` 一樣）。
  - `flatten_messages(messages, system=None) -> (system, prompt)`。
  - `Reply` 多了 `model`、`raw`；別名 `Result`。
  - 錯誤分類：`UsageLimitError`（`.resets`、`.retry_after`）、`AuthError`、`NotInstalledError`、`CallTimeoutError`、`PromptTooLongError`（也是 `ValueError`），全都是 `LoginError` 的子類別，各有 `.kind`。額度與登入是看錯誤訊息的字猜的。
  - `CAPABILITIES`：能力照實標。
  - `__version__`。
  - `tests/test_interface.py`。
- 這份 CHANGELOG。

### Fixed
- 暫存資料夾改用 `mkdtemp`＋`rmtree(ignore_errors=True)`：`TemporaryDirectory(ignore_cleanup_errors=…)` 要 Python 3.10，跟 `requires-python = ">=3.9"` 不合。

## [0.1.0] - 2026-11-13

### Added
- `ask()`：驅動官方 `copilot -p … -s --no-ask-user`，不給任何 `--allow-*`、不讀 token。
