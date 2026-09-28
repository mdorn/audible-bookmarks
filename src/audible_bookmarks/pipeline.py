"""Transcribing every annotation of a downloaded book."""

import logging
from pathlib import Path
from typing import Protocol

import numpy as np

from audible_bookmarks.annotations import Annotation
from audible_bookmarks.audio import save_clip
from audible_bookmarks.notes import Note, format_time, load_notes, save_notes
from audible_bookmarks.transcribe import Transcriber

logger = logging.getLogger(__name__)


class ClipSource(Protocol):
    """What the pipeline needs from a book; implemented by :class:`.audio.AudioBook`."""

    def decode_range(self, start_ms: int, end_ms: int) -> np.ndarray: ...

    def chapter_at(self, position_ms: int) -> str | None: ...


def transcribe_annotations(
    book: ClipSource,
    annotations: list[Annotation],
    transcriber: Transcriber,
    notes_file: Path,
    clips_dir: Path | None = None,
    force: bool = False,
    padding_ms: int = 0,
) -> list[Note]:
    """Transcribe ``annotations`` not already in ``notes_file``, saving after each.

    Clips are widened by ``padding_ms`` on both sides; a clip transcribed with a
    different padding is transcribed again. With ``force``, everything is
    transcribed again. With ``clips_dir``, the decoded audio of each annotation is
    also written there as an mp3.
    """
    existing = [] if force else load_notes(notes_file)
    wanted_ids = {a.id for a in annotations}
    by_id = {n.id: n for n in existing if n.id in wanted_ids}

    for index, annotation in enumerate(annotations, start=1):
        label = (
            f"[{index}/{len(annotations)}] {annotation.kind} at "
            f"{format_time(annotation.start_ms)}"
        )
        # Bookmarks get their range from the bookmark window, not the padding.
        padding = padding_ms if annotation.kind == "clip" else 0
        previous = by_id.get(annotation.id)
        if previous is not None and previous.padding_ms == padding:
            print(f"{label}: already transcribed")
            continue

        samples = book.decode_range(
            max(0, annotation.start_ms - padding), annotation.end_ms + padding
        )
        if clips_dir is not None:
            save_clip(
                samples, clips_dir / f"{annotation.kind}_{annotation.start_ms}.mp3"
            )

        print(f"{label}: transcribing")
        text = transcriber.transcribe(samples)

        chapter = book.chapter_at(annotation.start_ms)
        by_id[annotation.id] = Note.from_annotation(annotation, text, chapter, padding)
        save_notes(notes_file, list(by_id.values()))

    notes = list(by_id.values())
    save_notes(notes_file, notes)
    return sorted(notes, key=lambda n: (n.start_ms, n.kind))
