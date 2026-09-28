import json
from pathlib import Path
from typing import Any

import pytest

from audible_bookmarks import cli
from audible_bookmarks.config import Paths
from audible_bookmarks.notes import Note, save_notes
from audible_bookmarks.transcribe import DEFAULT_MODEL


def test_transcribe_defaults():
    args = cli.build_parser().parse_args(["transcribe", "B1"])
    assert args.asin == "B1"
    assert args.model == DEFAULT_MODEL
    assert args.bookmark_window == 30.0
    assert args.clip_padding == 0.0
    assert not args.save_clips
    assert not args.force
    assert args.paths == Paths(Path("data"))


def test_clip_padding_option():
    args = cli.build_parser().parse_args(["transcribe", "B1", "--clip-padding", "2.5"])
    assert args.clip_padding == 2.5


def test_data_dir_option():
    args = cli.build_parser().parse_args(["--data-dir", "/tmp/x", "list"])
    assert args.paths.auth_file == Path("/tmp/x/audible_configs/audible.json")


def test_command_is_required():
    with pytest.raises(SystemExit):
        cli.main([])


@pytest.mark.parametrize("command", [["list"], ["logout"], ["transcribe", "B1"]])
def test_not_logged_in_is_reported(tmp_path, capsys, command):
    assert cli.main(["--data-dir", str(tmp_path), *command]) == 1
    assert "audible-bookmarks login" in capsys.readouterr().err


def test_login_when_already_logged_in(tmp_path, capsys):
    paths = Paths(tmp_path)
    paths.config_dir.mkdir(parents=True)
    paths.auth_file.write_text("{}")

    assert cli.main(["--data-dir", str(tmp_path), "login"]) == 0
    assert "Already logged in" in capsys.readouterr().out


class FakeClient:
    def __init__(self, auth: Any) -> None:
        pass

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        assert path == "1.0/library"
        return {
            "items": [
                {"asin": "B1", "title": "Stoner", "authors": [{"name": "J. Williams"}]}
            ]
        }


def test_list_prints_and_caches_library(tmp_path, capsys, monkeypatch):
    paths = Paths(tmp_path)
    monkeypatch.setattr(cli.auth, "load_auth", lambda *a: object())
    monkeypatch.setattr(cli.auth, "save_auth", lambda auth: None)
    monkeypatch.setattr(cli.audible, "Client", FakeClient)

    assert cli.main(["--data-dir", str(tmp_path), "list"]) == 0

    out = capsys.readouterr().out
    assert "B1" in out
    assert "Stoner" in out
    assert "J. Williams" in out
    assert json.loads(paths.library_file.read_text())[0]["asin"] == "B1"


def test_transcribe_unknown_asin(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli.auth, "load_auth", lambda *a: object())
    monkeypatch.setattr(cli.audible, "Client", FakeClient)

    assert cli.main(["--data-dir", str(tmp_path), "transcribe", "NOPE"]) == 1
    assert "NOPE not found" in capsys.readouterr().err


def _transcribed_book(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    paths.config_dir.mkdir(parents=True)
    paths.library_file.write_text(
        json.dumps(
            [
                {
                    "asin": "B1",
                    "title": "Stoner",
                    "authors": [{"name": "John Williams"}],
                    "release_date": "2010-06-16",
                }
            ]
        )
    )
    save_notes(
        paths.notes_file("B1"),
        [
            Note(
                id="c1",
                kind="clip",
                start_ms=26_530_133,
                end_ms=26_560_133,
                timestamp="07:22:10.133",
                chapter="Chapter 13",
                note="",
                text="end of the semester",
            )
        ],
    )


def test_markdown_requires_transcription(tmp_path, capsys):
    assert cli.main(["--data-dir", str(tmp_path), "markdown", "B1"]) == 1
    assert "audible-bookmarks transcribe B1" in capsys.readouterr().err


def test_markdown_prints_document(tmp_path, capsys):
    _transcribed_book(tmp_path)

    assert cli.main(["--data-dir", str(tmp_path), "markdown", "B1"]) == 0

    out = capsys.readouterr().out
    assert out.startswith('---\nauthor: "John Williams"\ntitle: "Stoner"\nyear: 2010\n')
    assert out.endswith("Chapter 13:\n- 7:22:10: end of the semester\n")


def test_markdown_year_override_and_output_file(tmp_path, capsys):
    _transcribed_book(tmp_path)
    output = tmp_path / "out" / "stoner.md"

    args = ["--data-dir", str(tmp_path), "markdown", "B1", "--year", "1965"]
    assert cli.main([*args, "-o", str(output)]) == 0

    assert "year: 1965\n" in output.read_text()
    assert str(output) in capsys.readouterr().out
