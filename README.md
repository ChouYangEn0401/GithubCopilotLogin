# github_copilot_login

> 非官方套件，與 GitHub、Microsoft 無關。它只是驅動你自己電腦上、已登入的官方 `copilot` 命令列，用你自己的 **GitHub Copilot** 訂閱（不是 Microsoft 365 Copilot）；不讀、不存任何 token。

用你自己的 GitHub Copilot 訂閱，從 Python 叫模型：驅動官方的 `copilot -p … -s`，**不讀任何 token**。沒有相依套件。
姊妹套件：[ChatGPTLogin](https://github.com/ChouYangEn0401/ChatGPTLogin)（codex）。

```python
from github_copilot_login import ask
print(ask("請只回一個字：好").text)   # 先把 copilot 登入好
```

## 先看這幾件事
- **許可（2026-11-13，GitHub 官方文件）**：`copilot -p` 可用在腳本、CI、自動化。一般使用規範禁止「過量的自動化」，沒有明確門檻——頻率保持低。
- **不給任何 `--allow-*`**：無人值守時需要權限的動作會被拒絕，所以只回文字（照文件推論，沒實測）。
- **沒有用量、沒有 JSON**：文件那頁沒寫；`Reply.usage` 永遠是空的。
- prompt 走命令列（`-p` 時 stdin 被忽略），上限 30000 字，超過報錯、不截斷。SYNOX 的長系統提示可能超過，接進去前要確認。
- **沒在真的 copilot 上測過**（寫的時候那台沒裝）；測試用假的 runner。第一次用請先實測。

## 給程式呼叫（統一介面，0.2.0）

`github_copilot_login`、`claude_subscription`（ClaudeLogin）、`chatgpt_login` 三個訂閱登入套件用**同一組名字**（`INTERFACE_VERSION = "1"`），
包裝它們的程式可以用同一段程式碼接三家：

```python
from github_copilot_login import ask, LoginError, UsageLimitError, AuthError, NotInstalledError, CallTimeoutError

r = ask([{"role": "system", "content": "回答要短"},
         {"role": "user", "content": "一句話介紹台北"}], model=None, timeout=120)
print(r.text, r.model, r.usage)          # usage 永遠是 {}（copilot 不給用量）
```

| 名字 | 說明 |
|---|---|
| `ask(prompt, *, model=None, system=None, timeout=180.0, workdir="", runner=None, which=None) -> Result` | `prompt` 是字串或訊息清單；`model=None`＝copilot 自己的預設；`system` 接在提示最前面（copilot 沒有系統提示旗標） |
| `Result`（＝`Reply`） | `.text`、`.usage`（永遠 `{}`）、`.model`（指定的模型，沒指定是 `""`）、`.raw`（除錯用） |
| `LoginError` | 共同基底；`.kind` 是分類字串 |
| `UsageLimitError` | `kind="quota_exhausted"`；`.resets`（重置時間原文）、`.retry_after`（秒，猜不到是 `None`） |
| `AuthError` | `kind="auth_invalid"`：沒登入、登入過期 |
| `NotInstalledError` | `kind="not_installed"`：找不到 copilot、叫不起來 |
| `CallTimeoutError` | `kind="timeout"` |
| `PromptTooLongError` | 提示超過 30000 字；同時是 `LoginError` 和 `ValueError` |
| `CAPABILITIES` | 能力照實標：沒有工具呼叫、沒有串流、沒有用量、不收圖、多輪攤平、沒用真的 copilot 驗證過 |
| `flatten_messages(messages, system=None)` | 訊息清單 → `(system, prompt)`；三個套件寫法一樣 |

- 訊息清單：每則 `role`＋`content`（字串或只含文字的 parts）；`tool` 角色、圖片、最後一則不是 `user` → `ValueError`。
  多輪會攤成一段逐字稿送出，copilot 不記得前文。
- **額度用完、沒登入是看錯誤訊息的字猜的**（官方文件沒有寫錯誤格式、沒有實測）；猜不到就是一般的 `LoginError`。
- 舊的用法不變：`ask("…")`、`Reply`、`except LoginError` 照舊接得到所有錯誤。

## 之後
SYNOX 的 `ChatAdapter` 薄包一層（`kind: "github_copilot_login"`，`supports_tools=False` 走文字協定）。官方更正式的路是 Copilot SDK。
