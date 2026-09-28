"""Rendering transcribed notes as a markdown document."""

import json
from itertools import groupby

from audible_bookmarks.notes import Note


def human_time(milliseconds: int) -> str:
    """Format a position as ``H:MM:SS``, or ``M:SS`` under an hour."""
    minutes, seconds = divmod(milliseconds // 1000, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


def _bullet(note: Note) -> str:
    text = " ".join(note.text.split())
    return f"- {human_time(note.start_ms)}: {text}"


def render_markdown(
    title: str, author: str, year: str | None, notes: list[Note]
) -> str:
    """Render front matter plus one bullet per note, grouped by chapter."""
    # json.dumps produces a double-quoted string that is also valid YAML.
    lines = [
        "---",
        f"author: {json.dumps(author, ensure_ascii=False)}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"year: {year or ''}".rstrip(),
        "---",
    ]
    ordered = sorted(notes, key=lambda n: (n.start_ms, n.kind))
    for chapter, group in groupby(ordered, key=lambda n: n.chapter):
        lines.append("")
        if chapter:
            lines.append(f"{chapter}:")
        lines.extend(_bullet(note) for note in group)
    return "\n".join(lines) + "\n"
