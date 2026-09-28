import pytest

from audible_bookmarks.notes import Note, format_time, load_notes, save_notes


@pytest.mark.parametrize(
    ("ms", "expected"),
    [
        (0, "00:00:00.000"),
        (1_001, "00:00:01.001"),
        (26_530_133, "07:22:10.133"),
        (360_000_000, "100:00:00.000"),
    ],
)
def test_format_time(ms, expected):
    assert format_time(ms) == expected


def _note(id_: str, start_ms: int, text: str = "t") -> Note:
    return Note(
        id=id_,
        kind="clip",
        start_ms=start_ms,
        end_ms=start_ms + 1,
        timestamp=format_time(start_ms),
        chapter="Chapter 1",
        note="",
        text=text,
    )


def test_save_and_load_round_trip_sorted(tmp_path):
    path = tmp_path / "book" / "notes.json"
    save_notes(path, [_note("b", 200), _note("a", 100)])

    assert [n.id for n in load_notes(path)] == ["a", "b"]
    assert list(tmp_path.joinpath("book").iterdir()) == [path]  # no temp files left


def test_load_missing_file_returns_empty(tmp_path):
    assert load_notes(tmp_path / "missing.json") == []


def test_notes_without_padding_field_load_with_zero(tmp_path):
    path = tmp_path / "notes.json"
    save_notes(path, [_note("a", 100)])
    data = path.read_text().replace(',\n        "padding_ms": 0', "")
    assert "padding_ms" not in data
    path.write_text(data)

    [note] = load_notes(path)
    assert note.padding_ms == 0
