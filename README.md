# copilot_login

用你自己的 GitHub Copilot 訂閱，從 Python 叫模型：驅動官方的 `copilot -p … -s`，**不讀任何 token**。沒有相依套件。
姊妹套件：`openai_login`（codex）。

```python
from copilot_login import ask
print(ask("請只回一個字：好").text)   # 先把 copilot 登入好
```

## 先看這幾件事
- **許可（2026-11-13，GitHub 官方文件）**：`copilot -p` 可用在腳本、CI、自動化。一般使用規範禁止「過量的自動化」，沒有明確門檻——頻率保持低。
- **不給任何 `--allow-*`**：無人值守時需要權限的動作會被拒絕，所以只回文字（照文件推論，沒實測）。
- **沒有用量、沒有 JSON**：文件那頁沒寫；`Reply.usage` 永遠是空的。
- prompt 走命令列（`-p` 時 stdin 被忽略），上限 30000 字，超過報錯、不截斷。SYNOX 的長系統提示可能超過，接進去前要確認。
- **沒在真的 copilot 上測過**（寫的時候那台沒裝）；測試用假的 runner。第一次用請先實測。

## 之後
SYNOX 的 `ChatAdapter` 薄包一層（`kind: "copilot_login"`，`supports_tools=False` 走文字協定）。官方更正式的路是 Copilot SDK。
