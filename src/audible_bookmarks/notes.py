"""Reading and writing the transcribed notes file."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from audible_bookmarks.annotations import Annotation, Kind


@dataclass(frozen=True)
class Note:
    id: str
    kind: Kind
    start_ms: int
    end_ms: int
    timestamp: str
    chapter: str | None
    note: str
    text: str
    # Audio transcribed on each side of the clip beyond start_ms/end_ms.
    padding_ms: int = 0

    @classmethod
    def from_annotation(
        cls,
        annotation: Annotation,
        text: str,
        chapter: str | None = None,
        padding_ms: int = 0,
    ) -> "Note":
        return cls(
            id=annotation.id,
            kind=annotation.kind,
            start_ms=annotation.start_ms,
            end_ms=annotation.end_ms,
            timestamp=format_time(annotation.start_ms),
            chapter=chapter,
            note=annotation.note,
            text=text,
            padding_ms=padding_ms,
        )


def format_time(milliseconds: int) -> str:
    """Format a position as ``HH:MM:SS.mmm``."""
    seconds, millis = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{millis:03}"


def load_notes(path: Path) -> list[Note]:
    if not path.exists():
        return []
    return [Note(**item) for item in json.loads(path.read_text(encoding="utf-8"))]


def save_notes(path: Path, notes: list[Note]) -> None:
    """Atomically write ``notes`` sorted by position."""
    ordered = sorted(notes, key=lambda n: (n.start_ms, n.kind))
    payload = json.dumps([asdict(n) for n in ordered], ensure_ascii=False, indent=4)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
