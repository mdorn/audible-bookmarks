import pytest

from audible_bookmarks.markdown import human_time, render_markdown
from audible_bookmarks.notes import Note, format_time


@pytest.mark.parametrize(
    ("ms", "expected"),
    [(0, "0:00"), (65_000, "1:05"), (3_600_000, "1:00:00"), (26_530_133, "7:22:10")],
)
def test_human_time(ms, expected):
    assert human_time(ms) == expected


def _note(start_ms: int, text: str, chapter: str | None) -> Note:
    return Note(
        id=str(start_ms),
        kind="clip",
        start_ms=start_ms,
        end_ms=start_ms + 30_000,
        timestamp=format_time(start_ms),
        chapter=chapter,
        note="",
        text=text,
    )


def test_renders_front_matter_and_chapter_groups_in_order():
    notes = [
        _note(3_000_000, "third", "Chapter 2"),
        _note(1_000_000, "first", "Chapter 1"),
        _note(2_000_000, "second", "Chapter 1"),
    ]

    assert render_markdown("Stoner", "John Williams", "1965", notes) == (
        "---\n"
        'author: "John Williams"\n'
        'title: "Stoner"\n'
        "year: 1965\n"
        "---\n"
        "\n"
        "Chapter 1:\n"
        "- 16:40: first\n"
        "- 33:20: second\n"
        "\n"
        "Chapter 2:\n"
        "- 50:00: third\n"
    )


def test_notes_without_chapter_have_no_heading():
    doc = render_markdown("T", "A", "2000", [_note(5_000, "text", None)])
    assert doc.endswith("---\n\n- 0:05: text\n")


def test_transcript_whitespace_is_collapsed_to_one_line():
    doc = render_markdown("T", "A", "2000", [_note(0, " one\n two  three ", "Ch")])
    assert "- 0:00: one two three\n" in doc


def test_quotes_in_front_matter_are_escaped_and_missing_year_is_blank():
    doc = render_markdown('The "Best" Book', "A", None, [])
    assert 'title: "The \\"Best\\" Book"\n' in doc
    assert "year:\n" in doc
