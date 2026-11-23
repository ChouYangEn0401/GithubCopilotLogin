# github_copilot_login

第一次用？看 [docs/TUTORIAL.md](docs/TUTORIAL.md)

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

## 訂閱登入的使用聲明

本套件呼叫**你自己在這台電腦上已登入的官方 `copilot` 命令列**，用的是你個人的 GitHub Copilot 訂閱帳號。給程式用的時候（例如經 ntu_easy_llm 的 `remote/subscription/*` 來源，或把它接進 agent 外殼），目錄與設定頁上標「只給本人使用」。

1. **不推薦拿個人訂閱服務別人**：不建議把個人訂閱拿來服務其他人、轉售、共用或分享出去——例如經 LLOP 之類的通道提供給別人、放進給訪客使用的 AI 功能，或放進給別人用的備援鏈。
2. **條款由你自己確認**：GitHub Copilot 有自己的使用條款與政策。某種用法是否被允許，請你自己閱讀並理解該服務的條款，並自行負責。
3. **本專案只提供技術介面**：本專案及其作者、維護者不代表任何服務商，與你如何使用自己的訂閱無關，也不對違反服務條款所造成的後果（例如帳號被限制或停用）負責。程式技術上不阻擋任何用法，但「沒被擋」不代表服務商允許。
4. 這段是對 MIT 授權中「按現狀提供、不附任何擔保」的補充說明，不是額外的授權條件。

<details>
<summary>English version</summary>

**Usage notice for subscription login.** This package calls the official `copilot` CLI that **you** have signed in to on your own machine, using your personal GitHub Copilot subscription. When used from other programs (for example the `remote/subscription/*` sources of ntu_easy_llm, or an agent shell), it is labelled "for personal use only".

1. **Not recommended for serving others.** We do not recommend using a personal subscription to serve other people, or to resell, pool or share access — for example through a relay channel such as LLOP, an AI feature offered to guests, or a fallback chain used by other people.
2. **You check the terms.** GitHub Copilot has its own terms of use and policies. Whether a particular use is allowed is for you to read, understand and take responsibility for.
3. **Technical interface only.** This project and its authors and maintainers do not represent any service provider, are not involved in how you use your subscription, and are not responsible for the consequences of violating a provider's terms (such as account restrictions or suspension). The code does not technically block any use; not being blocked does not mean a use is permitted by the provider.
4. This notice supplements the "as is, without warranty" clause of the MIT License; it is not an additional license condition.

</details>

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

## 授權

MIT License — 見 [LICENSE](LICENSE)。
