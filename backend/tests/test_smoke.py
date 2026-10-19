from importlib.util import find_spec


def test_package_is_installed() -> None:
    assert find_spec("accessflow") is not None
