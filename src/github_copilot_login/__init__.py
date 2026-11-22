"""
github_copilot_login: 用「使用者自己的 GitHub Copilot 訂閱」叫模型，做法是驅動官方的 `copilot` 命令列（`copilot -p ... -s`）。

    from github_copilot_login import ask
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

統一呼叫介面（0.2.0，`INTERFACE_VERSION = "1"`；`claude_subscription`、`chatgpt_login` 用同一組名字）：
`ask()` 的第一個參數可以是訊息清單、`Result`（＝`Reply`）有 `text`／`usage`／`model`／`raw`，
錯誤分成 `UsageLimitError`／`AuthError`／`NotInstalledError`／`CallTimeoutError`，全都是 `LoginError`。
額度用完、沒登入是**看錯誤訊息的字猜的**（文件沒有寫錯誤格式，沒有實測），猜不到就是一般的 `LoginError`。
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

__version__ = "0.2.0"

__all__ = [
    "ask", "find_copilot", "Reply", "LoginError", "NOT_FOUND", "argv", "MAX_PROMPT_CHARS",
    # 統一呼叫介面
    "INTERFACE_VERSION", "CAPABILITIES", "Result", "UsageLimitError", "AuthError", "NotInstalledError",
    "CallTimeoutError", "PromptTooLongError", "flatten_messages", "__version__",
]

NOT_FOUND = "這台電腦找不到 copilot（GitHub Copilot CLI）。先安裝它並登入，再試一次。"
MAX_PROMPT_CHARS = 30000
INTERFACE_VERSION = "1"

# 能力照實標（給包裝的程式決定能不能用這個來源）。
CAPABILITIES = {
    "interface": INTERFACE_VERSION,
    "backend": "copilot -p -s",
    "text": True,
    "tools": False,               # 沒有 function calling；也不給 copilot 任何 --allow-*
    "stream": False,
    "usage": False,               # 文件沒有用量輸出
    "cost": False,
    "system": "prepended",        # 沒有系統提示旗標：接在提示最前面
    "messages": "flattened",      # 多輪訊息攤成一段文字
    "images": False,
    "json_schema": False,
    "default_model": "",          # 空＝copilot 自己的預設
    "max_prompt_chars": MAX_PROMPT_CHARS,
    "verified_with_real_cli": False,
}


# --------------------------------------------------------------------------- #
# 錯誤（統一介面：每一種都是 LoginError，.kind 是分類字串）
# --------------------------------------------------------------------------- #
class LoginError(Exception):
    """叫不動；訊息是一句給人看的話。統一介面的共同基底，``kind`` 是分類字串。"""

    kind = "unknown"


class UsageLimitError(LoginError):
    """訂閱額度用完／被限流（看錯誤訊息的字猜的）。``resets``：服務說的重置時間原文；``retry_after``：秒數，猜不到是 None。"""

    kind = "quota_exhausted"

    def __init__(self, message: str, resets: str = "", retry_after: Optional[float] = None):
        super().__init__(message)
        self.resets = resets
        self.retry_after = retry_after


class AuthError(LoginError):
    """沒登入、登入過期（看錯誤訊息的字猜的）。"""

    kind = "auth_invalid"


class NotInstalledError(LoginError):
    """找不到 copilot，或叫不起來。"""

    kind = "not_installed"


class CallTimeoutError(LoginError):
    """超過 timeout 秒沒回。"""

    kind = "timeout"


class PromptTooLongError(LoginError, ValueError):
    """提示超過命令列能放的長度；呼叫端的輸入問題，所以也是 ValueError。"""

    kind = "bad_request"


# 錯誤訊息的猜法【推測：文件沒有寫錯誤格式，沒有實測】。只看 copilot 自己的輸出，不看這個套件加的提示句。
_AUTH_RE = re.compile(
    r"(?i)(not (?:logged|signed) in|no authentication|not authenticated|authentication (?:failed|required)|"
    r"please (?:log|sign) ?in|unauthori[sz]ed|bad credentials|(?:token|credentials?) (?:has |have )?expired|"
    r"expired (?:token|credentials?)|re-?authenticate|(?:status|http|code|error)\W{0,3}401\b)")
_LIMIT_RE = re.compile(
    r"(?i)(quota|usage limit|limit (?:reached|exceeded)|exceeded .{0,40}?(?:limit|requests|allowance)|"
    r"rate.?limit|too many requests|premium requests|(?:status|http|code|error)\W{0,3}429\b)")
_RESET_RE = re.compile(r"(?i)(?:try again|retry|resets?)\s+(in|at|after|on)\s+([^.\n]{1,60})")
_DURATION_RE = re.compile(r"(?i)(\d+(?:\.\d+)?)\s*(d(?:ays?)?|h(?:ours?|rs?)?|m(?:in(?:ute)?s?)?|s(?:ec(?:ond)?s?)?)\b")
_UNIT_SECONDS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def _reset_hint(raw: str) -> Tuple[str, Optional[float]]:
    """「try again in 2 hours 5 minutes」→ ("2 hours 5 minutes", 7500.0)；「at 5pm」只給原文、秒數 None。"""
    match = _RESET_RE.search(raw or "")
    if not match:
        return "", None
    text = match.group(2).strip()
    if match.group(1).lower() not in ("in", "after"):
        return text, None
    seconds = sum(float(n) * _UNIT_SECONDS[u[0].lower()] for n, u in _DURATION_RE.findall(text))
    return text, (seconds or None)


def _failure(message: str, raw: str) -> LoginError:
    """依 copilot 的原始輸出 raw 決定錯誤種類；猜不到就是一般的 LoginError。"""
    raw = " ".join(str(raw or "").split())
    if _AUTH_RE.search(raw):
        return AuthError(message)
    if _LIMIT_RE.search(raw):
        resets, retry_after = _reset_hint(raw)
        return UsageLimitError(message, resets=resets, retry_after=retry_after)
    return LoginError(message)


# --------------------------------------------------------------------------- #
# 訊息清單 → 一段提示（三個訂閱登入套件的寫法一模一樣）
# --------------------------------------------------------------------------- #
_MULTI_TURN_HEAD = ("Below is a conversation between a user and an assistant. "
                    "Reply as the assistant to the last user message, with the assistant's reply only.")
_ROLE_HEAD = {"user": "### User", "assistant": "### Assistant"}


def _content_text(content: Any) -> str:
    """訊息內容 → 文字。字串原樣；OpenAI 式 parts 清單只收 type=text，其他（圖片…）丟 ValueError。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type", "text") == "text":
                parts.append(str(part.get("text") or ""))
            else:
                kind = part.get("type") if isinstance(part, dict) else type(part).__name__
                raise ValueError(f"這個來源只收文字，不支援 {kind!r} 內容（例如圖片）。")
        return "".join(parts)
    raise ValueError(f"訊息內容要是字串或文字 parts 清單，收到 {type(content).__name__}。")


def flatten_messages(messages_or_prompt: Any, system: Optional[str] = None) -> tuple:
    """字串或訊息清單 → ``(system, prompt)``（三個訂閱登入套件的寫法一模一樣）。

    * 字串：原樣當 prompt，system 照給的。
    * 清單：每則是 dict（``role``、``content``）或有 ``.role``／``.content`` 的物件。
      ``system`` 的內容收進 system（跟參數給的用空行接在後面）；``user``／``assistant`` 是對話；
      其他角色（``tool``…）丟 ValueError——這個來源沒有工具呼叫。內容可以是字串或 OpenAI 式 parts（只收文字）。
    * 只有一則 user（可以加 system）：prompt 就是那則原文。多輪：攤成一段逐字稿，最後一則必須是 user。"""
    if isinstance(messages_or_prompt, str):
        return system, messages_or_prompt
    if messages_or_prompt is None or isinstance(messages_or_prompt, (bytes, dict)):
        raise ValueError("要給字串，或訊息清單（每則有 role、content）。")
    systems, turns = [], []
    for msg in messages_or_prompt:
        if isinstance(msg, dict):
            role, content = msg.get("role"), msg.get("content")
        else:
            role, content = getattr(msg, "role", None), getattr(msg, "content", None)
        role = str(role or "").lower()
        text = _content_text(content)
        if role == "system":
            if text.strip():
                systems.append(text)
        elif role in _ROLE_HEAD:
            turns.append((role, text))
        else:
            raise ValueError(f"不支援的訊息角色 {role!r}：這個來源只有 system／user／assistant，沒有工具呼叫。")
    if not turns or turns[-1][0] != "user":
        raise ValueError("訊息清單裡最後一則（system 以外）必須是 user。")
    merged = "\n\n".join(s for s in ([system] if system else []) + systems) or system
    if len(turns) == 1:
        return merged, turns[0][1]
    body = "\n\n".join(f"{_ROLE_HEAD[role]}\n{text}" for role, text in turns)
    return merged, f"{_MULTI_TURN_HEAD}\n\n{body}"


def _with_system(system: Optional[str], prompt: str) -> str:
    """沒有系統提示旗標：把 system 接在提示最前面。"""
    if not system:
        return prompt
    return f"[Instructions]\n{system}\n\n[Request]\n{prompt}"


# --------------------------------------------------------------------------- #
# 呼叫
# --------------------------------------------------------------------------- #
@dataclass
class Reply:
    text: str
    usage: Dict[str, int] = field(default_factory=dict)    # 文件沒有提供用量，永遠空
    model: str = ""                                         # 呼叫時指定的模型；沒指定（copilot 自己的預設）是空字串
    raw: Any = None                                         # 除錯用：{"returncode", "stdout"}；內容不保證


Result = Reply


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


@contextlib.contextmanager
def _scratch_dir():
    """新的空暫存資料夾，用完刪掉（刪不掉就算了）。Python 3.9 沒有 TemporaryDirectory(ignore_cleanup_errors=…)。"""
    path = tempfile.mkdtemp(prefix="github_copilot_login-")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def ask(prompt: Any, *, model: Optional[str] = None, system: Optional[str] = None, timeout: float = 180.0,
        workdir: str = "", runner: Optional[Callable] = None,
        which: Optional[Callable[[], Optional[str]]] = None) -> Reply:
    """問一次。prompt 可以是字串或訊息清單（見 flatten_messages）；system 接在提示最前面（copilot 沒有系統提示旗標）。

    model=None／空字串＝copilot 自己的預設。runner／which 給測試換假的。workdir 空＝每次用一個新的空暫存資料夾。
    錯誤：PromptTooLongError（也是 ValueError）、NotInstalledError、CallTimeoutError、AuthError、UsageLimitError、
    其他 LoginError；訊息清單格式不對丟 ValueError。"""
    system, text = flatten_messages(prompt, system)
    text = _with_system(system, text)
    model = model or ""
    if len(text) > MAX_PROMPT_CHARS:
        raise PromptTooLongError(
            f"提示太長（{len(text)} 字，上限 {MAX_PROMPT_CHARS}）：copilot -p 走命令列，超過會被系統截掉。")
    exe = (which or find_copilot)()
    if not exe:
        raise NotInstalledError(NOT_FOUND)
    run = runner or subprocess.run
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def go(cwd: str):
        try:
            return run(argv(exe, text, model=model), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=cwd, creationflags=flags)
        except subprocess.TimeoutExpired:
            raise CallTimeoutError(f"Copilot 超過 {int(timeout)} 秒沒回。")
        except OSError as e:
            raise NotInstalledError(f"叫不起 copilot：{e}")

    if workdir:
        os.makedirs(workdir, exist_ok=True)
        done = go(workdir)
    else:
        with _scratch_dir() as tmp:
            done = go(tmp)
    out = (done.stdout or "").strip()
    if done.returncode != 0 or not out:
        raw = f"{done.stderr or ''} {out}".strip()
        tail = (done.stderr or out or "").strip()[-200:]
        raise _failure(f"Copilot 沒有給答案（結束碼 {done.returncode}）：{tail or '（沒有訊息）'}。"
                       "是不是還沒登入、或訂閱額度用完了？", raw[-2000:])
    return Reply(text=out, model=model, raw={"returncode": done.returncode, "stdout": done.stdout})
