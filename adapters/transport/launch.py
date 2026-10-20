"""The start command of one harness, built for one started agent only.

Each started agent carries its harness's update-off switch on its own launch: Codex CLI the option
`-c check_for_update_on_startup=false`, Claude Code `DISABLE_AUTOUPDATER=1` in the started process's
environment. No configuration file and no user environment changes, so a session started by hand still
checks for updates. `args` holds the caller's other native options (permission mode, added folders) as given.
"""
from __future__ import annotations

from dataclasses import dataclass, field

HARNESSES = ("claude", "codex")
CODEX_UPDATE_OFF = ("-c", "check_for_update_on_startup=false")
CLAUDE_UPDATE_OFF = {"DISABLE_AUTOUPDATER": "1"}


@dataclass(frozen=True)
class Launch:
    binary: str                      # the harness command, also herdr's agent kind
    args: list[str]                  # the native arguments after the binary
    env: dict[str, str] = field(default_factory=dict)

    def argv(self) -> list[str]:
        return [self.binary, *self.args]


def _model_effort(harness: str, model: str | None, effort: str | None) -> list[str]:
    out: list[str] = []
    if harness == "claude":
        if model:
            out += ["--model", model]
        if effort:
            out += ["--effort", effort]
    else:
        if model:
            out += ["-m", model]
        if effort:
            out += ["-c", f"model_reasoning_effort={effort}"]
    return out


def interactive(harness: str, prompt: str | None, *, model: str | None = None, effort: str | None = None,
                resume: str | None = None, args: list[str] | None = None) -> Launch:
    """An interactive session for a pane; `resume` names the harness session to continue."""
    args = list(args or [])
    if harness == "claude":
        native = [*_model_effort(harness, model, effort), *args]
        if resume:
            native += ["--resume", resume]
        if prompt:
            native.append(prompt)
        return Launch("claude", native, dict(CLAUDE_UPDATE_OFF))
    if harness == "codex":
        native = [*CODEX_UPDATE_OFF, *_model_effort(harness, model, effort), *args]
        if resume:
            native = ["resume", *native, resume]
        if prompt:
            native.append(prompt)
        return Launch("codex", native, {})
    raise ValueError(f"unknown harness {harness!r}; one of {', '.join(HARNESSES)}")


def headless(harness: str, prompt: str, *, model: str | None = None, effort: str | None = None,
             args: list[str] | None = None) -> Launch:
    """A run with no terminal: it takes its whole task at the start and ends on its own."""
    args = list(args or [])
    if harness == "claude":
        return Launch("claude", ["-p", *_model_effort(harness, model, effort), *args, prompt],
                      dict(CLAUDE_UPDATE_OFF))
    if harness == "codex":
        return Launch("codex", ["exec", *CODEX_UPDATE_OFF, *_model_effort(harness, model, effort), *args,
                                prompt], {})
    raise ValueError(f"unknown harness {harness!r}; one of {', '.join(HARNESSES)}")
