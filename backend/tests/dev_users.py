from collections.abc import Sequence

import pytest

from scripts import create_dev_user


def run_script(monkeypatch: pytest.MonkeyPatch, *args: str, passwords: Sequence[str]) -> int:
    """Run the development user script, answering its password prompts in order."""
    answers = iter(passwords)
    monkeypatch.setattr(create_dev_user, "getpass", lambda _prompt: next(answers))
    return create_dev_user.main(args)
