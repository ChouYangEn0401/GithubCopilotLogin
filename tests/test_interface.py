"""統一呼叫介面（三個訂閱登入套件共用的名字）：訊息清單、Result、錯誤分類。全部用假的 runner，不叫真的 copilot。"""

import subprocess

import pytest

import github_copilot_login as gcl
from github_copilot_login import (CAPABILITIES, INTERFACE_VERSION, AuthError, CallTimeoutError, LoginError,
                                  NotInstalledError, PromptTooLongError, Reply, Result, UsageLimitError, ask,
                                  flatten_messages)


class Done:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def capture(out="好"):
    seen = {}

    def runner(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        return Done(out)

    return seen, runner


def test_names_and_hierarchy():
    assert Result is Reply and INTERFACE_VERSION == "1"
    for cls in (UsageLimitError, AuthError, NotInstalledError, CallTimeoutError, PromptTooLongError):
        assert issubclass(cls, LoginError)
    assert issubclass(PromptTooLongError, ValueError)
    assert [c.kind for c in (LoginError, UsageLimitError, AuthError, NotInstalledError, CallTimeoutError)] == \
        ["unknown", "quota_exhausted", "auth_invalid", "not_installed", "timeout"]
    for name in ("INTERFACE_VERSION", "CAPABILITIES", "Result", "UsageLimitError", "AuthError",
                 "NotInstalledError", "CallTimeoutError", "flatten_messages"):
        assert name in gcl.__all__


def test_capabilities_are_honest():
    assert CAPABILITIES["tools"] is False and CAPABILITIES["usage"] is False and CAPABILITIES["stream"] is False
    assert CAPABILITIES["system"] == "prepended" and CAPABILITIES["verified_with_real_cli"] is False


def test_result_shape():
    seen, runner = capture()
    r = ask("hi", model="m1", runner=runner, which=lambda: "copilot")
    assert (r.text, r.usage, r.model) == ("好", {}, "m1")
    assert r.raw["returncode"] == 0
    r = ask("hi", runner=runner, which=lambda: "copilot")
    assert r.model == "" and "--model" not in seen["cmd"]


def test_messages_are_flattened_and_system_prepended():
    seen, runner = capture()
    ask([{"role": "system", "content": "be brief"}, {"role": "user", "content": "q1"},
         {"role": "assistant", "content": "a1"}, {"role": "user", "content": "q2"}],
        runner=runner, which=lambda: "copilot")
    sent = seen["cmd"][seen["cmd"].index("-p") + 1]
    assert sent.startswith("[Instructions]\nbe brief\n\n[Request]\n")
    assert sent.endswith("### User\nq1\n\n### Assistant\na1\n\n### User\nq2")


def test_single_message_and_plain_string_are_sent_as_is():
    seen, runner = capture()
    ask([{"role": "user", "content": "只有一句"}], runner=runner, which=lambda: "copilot")
    assert seen["cmd"][2] == "只有一句"
    ask("plain", system="S", runner=runner, which=lambda: "copilot")
    assert seen["cmd"][2] == "[Instructions]\nS\n\n[Request]\nplain"


def test_flatten_rejects_tools_images_and_bad_order():
    for msgs in ([{"role": "tool", "content": "x"}, {"role": "user", "content": "y"}],
                 [{"role": "user", "content": [{"type": "image_url"}]}],
                 [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
                 []):
        with pytest.raises(ValueError):
            flatten_messages(msgs)
    assert flatten_messages("x") == (None, "x")


@pytest.mark.parametrize("stderr,cls", [
    ("Error: Not logged in. Please run copilot and use /login", AuthError),
    ("HTTP 401: Bad credentials", AuthError),
    ("You have exceeded your premium requests allowance", UsageLimitError),
    ("429 Too Many Requests", UsageLimitError),
    ("something else broke", LoginError),
])
def test_failures_are_classified(stderr, cls):
    with pytest.raises(LoginError) as info:
        ask("x", runner=lambda c, **k: Done("", stderr, 1), which=lambda: "copilot")
    assert type(info.value) is cls
    assert "結束碼 1" in str(info.value)


def test_usage_limit_reset_hint():
    raw = "Rate limit exceeded. Try again in 1 hour 30 minutes."
    with pytest.raises(UsageLimitError) as info:
        ask("x", runner=lambda c, **k: Done("", raw, 1), which=lambda: "copilot")
    assert info.value.resets == "1 hour 30 minutes" and info.value.retry_after == 5400
    with pytest.raises(UsageLimitError) as info:
        ask("x", runner=lambda c, **k: Done("", "quota exceeded, resets at 5pm", 1), which=lambda: "copilot")
    assert info.value.resets == "5pm" and info.value.retry_after is None


def test_not_installed_timeout_and_too_long():
    with pytest.raises(NotInstalledError):
        ask("x", which=lambda: None)

    def boom(cmd, **kw):
        raise OSError("cannot run")

    with pytest.raises(NotInstalledError):
        ask("x", runner=boom, which=lambda: "copilot")

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    with pytest.raises(CallTimeoutError):
        ask("x", timeout=1, runner=slow, which=lambda: "copilot")
    with pytest.raises(PromptTooLongError):
        ask("x", system="s" * gcl.MAX_PROMPT_CHARS, which=lambda: "copilot")


def test_scratch_dir_is_removed():
    seen, runner = capture()
    ask("x", runner=runner, which=lambda: "copilot")
    import os
    assert not os.path.exists(seen["cwd"])
