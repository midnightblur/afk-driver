"""Resolve the optional Chromium browser used by the lavish page test."""

import os
import shutil
import sys


COMMANDS = ("chrome", "msedge", "chromium", "chromium-browser", "google-chrome")


def executable():
    """Return a browser command or a standard Windows installation path."""
    for command in COMMANDS:
        path = shutil.which(command)
        if path:
            return path
    candidates = (
        ("PROGRAMFILES", "Google", "Chrome", "Application", "chrome.exe"),
        ("PROGRAMFILES(X86)", "Microsoft", "Edge", "Application", "msedge.exe"),
        ("LOCALAPPDATA", "Google", "Chrome", "Application", "chrome.exe"),
    )
    for variable, *parts in candidates:
        root = os.environ.get(variable)
        if root:
            path = os.path.join(root, *parts)
            if os.path.isfile(path):
                return path
    return None


if __name__ == "__main__":
    browser = executable()
    if browser:
        sys.stdout.write(browser + "\n")
    sys.exit(0 if browser else 1)
