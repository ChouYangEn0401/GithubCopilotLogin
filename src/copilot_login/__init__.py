"""
copilot_login: 用「使用者自己的 GitHub Copilot 訂閱」叫模型，做法是驅動官方的 `copilot` 命令列（`copilot -p ... -s`）。

    from copilot_login import ask
    print(ask("請只回一個字：好").text)       # 先在終端機把 copilot 登入好（互動式 /login）

依據（2026-11-13，GitHub 官方文件
docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically）：
- 文件寫明 `copilot -p` 可用在腳本、CI、自動化；`-s` 靜默模式只輸出乾淨文字；`--model` 指定模型；`--no-ask-user` 不問問題。
- 一般 GitHub 使用規範禁止「過量的自動化」，沒有明確門檻；請保持低頻率。
- **這個套件不讀、不碰任何 token**：登入狀態由官方 binary 自己管。

比 codex 安全的一點：不給任何 `--allow-tool`／`--allow-all`。無人值守時需要權限的動作會被拒絕，所以它實際上只能回文字
（文件：`--assisted-approval` 那段說「仍需批准的請求在無人值守執行會被拒絕」；沒有 `--allow-*` 就沒有預先批准）。
這是照文件推論，**沒有實測**。

沒在真的 copilot 上驗證過（寫這個時那台沒裝）。文件那頁沒有 JSON 輸出、離開碼、用量；所以這裡沒有 token 用量，
`Reply.usage` 永遠是空的。prompt 走命令列（`-p` 時 stdin 會被忽略），Windows 命令列上限約 32k 字，超過就直接報錯、不截斷。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

__all__ = ["ask", "find_copilot", "Reply", "LoginError", "NOT_FOUND", "argv", "MAX_PROMPT_CHARS"]

NOT_FOUND = "這台電腦找不到 copilot（GitHub Copilot CLI）。先安裝它並登入，再試一次。"
MAX_PROMPT_CHARS = 30000


class LoginError(Exception):
    """叫不動；訊息是一句給人看的話。"""


@dataclass
class Reply:
    text: str
    usage: Dict[str, int] = field(default_factory=dict)    # 文件沒有提供用量，永遠空


def find_copilot() -> Optional[str]:
    """PATH 上的 copilot；沒有就看 npm 全域安裝的固定位置（Windows 的 %APPDATA%\\npm）。"""
    found = shutil.which("copilot")
    if found:
        return found
    appdata = os.environ.get("APPDATA")
    if appdata:
        for name in ("copilot.cmd", "copilot.exe", "copilot"):
            path = os.path.join(appdata, "npm", name)
            if os.path.isfile(path):
                return path
    return None


def argv(exe: str, prompt: str, *, model: str = "") -> List[str]:
    """沒有任何 --allow-* 旗標：需要權限的動作在無人值守時會被拒絕。"""
    out = [exe, "-p", prompt, "-s", "--no-ask-user"]
    if model:
        out += ["--model", model]
    return out


def ask(prompt: str, *, model: str = "", timeout: float = 180.0, workdir: str = "",
        runner: Optional[Callable] = None, which: Optional[Callable[[], Optional[str]]] = None) -> Reply:
    """問一次。runner／which 給測試換假的。workdir 空＝每次用一個新的空暫存資料夾。"""
    if len(prompt) > MAX_PROMPT_CHARS:
        raise LoginError(f"提示太長（{len(prompt)} 字，上限 {MAX_PROMPT_CHARS}）：copilot -p 走命令列，超過會被系統截掉。")
    exe = (which or find_copilot)()
    if not exe:
        raise LoginError(NOT_FOUND)
    run = runner or subprocess.run
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def go(cwd: str):
        try:
            return run(argv(exe, prompt, model=model), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=cwd, creationflags=flags)
        except subprocess.TimeoutExpired:
            raise LoginError(f"Copilot 超過 {int(timeout)} 秒沒回。")
        except OSError as e:
            raise LoginError(f"叫不起 copilot：{e}")

    if workdir:
        os.makedirs(workdir, exist_ok=True)
        done = go(workdir)
    else:
        with tempfile.TemporaryDirectory(prefix="copilot_login-", ignore_cleanup_errors=True) as tmp:
            done = go(tmp)
    text = (done.stdout or "").strip()
    if done.returncode != 0 or not text:
        tail = (done.stderr or text or "").strip()[-200:]
        raise LoginError(f"Copilot 沒有給答案（結束碼 {done.returncode}）：{tail or '（沒有訊息）'}。是不是還沒登入、或訂閱額度用完了？")
    return Reply(text=text)
