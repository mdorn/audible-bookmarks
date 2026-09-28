"""Fetching and parsing the user's clips and bookmarks for a book."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import audible

SIDECAR_URL = "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/sidecar"

Kind = Literal["clip", "bookmark"]


@dataclass(frozen=True)
class Annotation:
    id: str
    kind: Kind
    start_ms: int
    end_ms: int
    note: str = ""
    created: str = ""


def fetch_annotations(
    client: audible.Client, asin: str, cache_file: Path
) -> dict[str, Any]:
    """Download the annotation sidecar for ``asin`` and cache it to ``cache_file``."""
    sidecar = client.get(SIDECAR_URL, params={"type": "AUDI", "key": asin})
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    return sidecar


def parse_annotations(
    sidecar: dict[str, Any], bookmark_window_ms: int, duration_ms: int | None = None
) -> list[Annotation]:
    """Turn the raw sidecar into clips and bookmarks sorted by position.

    Plain bookmarks have no end, so they get a window of ``bookmark_window_ms``,
    clamped to ``duration_ms`` when known. A bookmark at the same position as a
    clip is dropped, since the Audible app creates both when you save a clip.
    """
    records = sidecar["payload"]["records"]
    clips: list[Annotation] = []
    bookmarks: list[Annotation] = []

    for record in records:
        # Other types (e.g. audible.last_heard) have no annotationId.
        if record.get("type") not in ("audible.clip", "audible.bookmark"):
            continue
        start_ms = int(record["startPosition"])
        metadata = record.get("metadata") or {}
        common = {
            "id": record["annotationId"],
            "start_ms": start_ms,
            "note": (metadata.get("note") or metadata.get("title") or "").strip(),
            "created": record.get("creationTime", ""),
        }
        match record.get("type"):
            case "audible.clip":
                clips.append(
                    Annotation(kind="clip", end_ms=int(record["endPosition"]), **common)
                )
            case "audible.bookmark":
                end_ms = start_ms + bookmark_window_ms
                if duration_ms is not None:
                    end_ms = min(end_ms, duration_ms)
                bookmarks.append(Annotation(kind="bookmark", end_ms=end_ms, **common))

    clip_starts = {clip.start_ms for clip in clips}
    bookmarks = [b for b in bookmarks if b.start_ms not in clip_starts]
    return sorted(clips + bookmarks, key=lambda a: (a.start_ms, a.kind))
