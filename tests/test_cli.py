import pytest

from calendar_sync.cli import build_parser


def test_sync_accepts_no_deletes() -> None:
    args = build_parser().parse_args(["sync", "--feed", "valorant", "--no-deletes"])

    assert args.no_deletes is True
    assert args.allow_unsafe_deletes is False


def test_delete_modes_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["sync", "--allow-unsafe-deletes", "--no-deletes"])
