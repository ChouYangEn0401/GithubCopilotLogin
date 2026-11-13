import subprocess

import pytest

from github_copilot_login import MAX_PROMPT_CHARS, NOT_FOUND, LoginError, argv, ask


class Done:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def test_argv_is_silent_and_grants_no_tool_permission():
    a = argv("copilot", "hi", model="m1")
    assert a[:3] == ["copilot", "-p", "hi"] and "-s" in a and "--no-ask-user" in a
    assert a[a.index("--model") + 1] == "m1"
    assert not [x for x in a if x.startswith("--allow")]


def test_ask_returns_stripped_text_in_empty_cwd():
    seen = {}

    def runner(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        return Done("  好\n")

    r = ask("你好", runner=runner, which=lambda: "copilot")
    assert r.text == "好" and r.usage == {} and seen["cwd"]


def test_missing_binary_and_empty_or_failed_answer():
    with pytest.raises(LoginError, match="copilot"):
        ask("x", which=lambda: None)
    assert "登入" in NOT_FOUND
    with pytest.raises(LoginError, match="結束碼 1"):
        ask("x", runner=lambda c, **k: Done("", "not logged in", 1), which=lambda: "copilot")
    with pytest.raises(LoginError):
        ask("x", runner=lambda c, **k: Done("  ", "", 0), which=lambda: "copilot")


def test_timeout():
    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    with pytest.raises(LoginError, match="沒回"):
        ask("x", timeout=1, runner=slow, which=lambda: "copilot")


def test_too_long_prompt_is_refused_not_truncated():
    with pytest.raises(LoginError, match="太長"):
        ask("x" * (MAX_PROMPT_CHARS + 1), which=lambda: "copilot")
