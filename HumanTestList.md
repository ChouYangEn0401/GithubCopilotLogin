# HumanTestList

人要親手做的檢查（真的 CLI、真的登入）。自動測試只用假的子程序，碰不到這些。

## 待測

- [ ] 2026-11-23 · 真的 copilot 第一次呼叫 · 裝好並登入 copilot 後跑 `python -c "from github_copilot_login import ask; print(ask('請只回一個字：好'))"` · 印出 `Reply(text='好', …)`
- [ ] 2026-11-23 · 沒登入時的錯誤字串 · 登出 copilot 後跑同一行 · 丟 `AuthError`；若是一般 `LoginError`，把 copilot 的原文記下來補進 `_AUTH_RE`
- [ ] 2026-11-23 · 額度用完時的錯誤字串 · 下次真的遇到時記下錯誤原文 · 丟 `UsageLimitError`；不是的話把原文補進 `_LIMIT_RE`
- [ ] 2026-11-23 · 系統提示接在最前面有效 · `ask('說好', system='只回一個英文單字')` · 回一個英文單字
- [ ] 2026-11-23 · 逾時會不會留下 node 程序（Windows，npm 的 copilot.cmd）· `ask('寫一篇很長的文章', timeout=5)` 後看工作管理員 · 沒有殘留的 node／copilot（有的話記下來，要改成殺整棵程序樹）
- [ ] 2026-11-23 · 新手教學能照著走完 · 找一台新電腦，照 docs/TUTORIAL.md 從頭走一遍 · 每一步「會看到什麼」都對得上；對不上的記下實際畫面交回改教學
- [ ] 2026-11-23 · 真的 copilot CLI 能不能跑（Windows）· 新電腦上 `winget install Microsoft.PowerShell`、`winget install GitHub.Copilot` → `copilot` 登入 → 教學步驟 8 的 `python -c …`；在 Windows PowerShell 5.1 與 PowerShell 7 各跑一次 · 有回答；記下 winget 裝完 `copilot` 是否直接在 PATH 上、5.1 視窗裡能不能用、資料夾信任或權限有沒有擋住無人值守的呼叫（原文）

## 測過了

（還沒有）
