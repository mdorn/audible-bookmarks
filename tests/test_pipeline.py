import numpy as np

from audible_bookmarks.annotations import Annotation
from audible_bookmarks.notes import load_notes
from audible_bookmarks.pipeline import transcribe_annotations

CLIP = Annotation(id="c1", kind="clip", start_ms=1_000, end_ms=2_000)
BOOKMARK = Annotation(id="b1", kind="bookmark", start_ms=500, end_ms=1_500)


class FakeBook:
    def __init__(self) -> None:
        self.decoded: list[tuple[int, int]] = []

    def decode_range(self, start_ms: int, end_ms: int) -> np.ndarray:
        self.decoded.append((start_ms, end_ms))
        return np.zeros(16, dtype=np.float32)

    def chapter_at(self, position_ms: int) -> str | None:
        return "Chapter 1"


class FakeTranscriber:
    def __init__(self) -> None:
        self.calls = 0

    def transcribe(self, samples: np.ndarray) -> str:
        self.calls += 1
        return f"text {self.calls}"


def test_transcribes_and_saves_all(tmp_path):
    notes_file = tmp_path / "notes.json"
    transcriber = FakeTranscriber()

    notes = transcribe_annotations(
        FakeBook(), [CLIP, BOOKMARK], transcriber, notes_file
    )

    assert [(n.id, n.chapter, n.text) for n in notes] == [
        ("b1", "Chapter 1", "text 2"),
        ("c1", "Chapter 1", "text 1"),
    ]
    assert load_notes(notes_file) == notes


def test_resumes_without_retranscribing(tmp_path):
    notes_file = tmp_path / "notes.json"
    transcribe_annotations(FakeBook(), [CLIP], FakeTranscriber(), notes_file)

    book, transcriber = FakeBook(), FakeTranscriber()
    transcribe_annotations(book, [CLIP, BOOKMARK], transcriber, notes_file)

    assert book.decoded == [(500, 1_500)]
    assert transcriber.calls == 1


def test_force_retranscribes_everything(tmp_path):
    notes_file = tmp_path / "notes.json"
    transcribe_annotations(FakeBook(), [CLIP], FakeTranscriber(), notes_file)

    transcriber = FakeTranscriber()
    transcribe_annotations(FakeBook(), [CLIP], transcriber, notes_file, force=True)

    assert transcriber.calls == 1


def test_saves_clips_when_requested(tmp_path, monkeypatch):
    saved = []
    monkeypatch.setattr(
        "audible_bookmarks.pipeline.save_clip",
        lambda samples, path: saved.append(path.name),
    )

    transcribe_annotations(
        FakeBook(),
        [CLIP],
        FakeTranscriber(),
        tmp_path / "notes.json",
        clips_dir=tmp_path / "clips",
    )

    assert saved == ["clip_1000.mp3"]


def test_padding_widens_clips_but_not_bookmarks(tmp_path):
    book = FakeBook()

    notes = transcribe_annotations(
        book, [CLIP, BOOKMARK], FakeTranscriber(), tmp_path / "n.json", padding_ms=300
    )

    assert book.decoded == [(700, 2_300), (500, 1_500)]
    assert {n.id: n.padding_ms for n in notes} == {"c1": 300, "b1": 0}
    assert {n.id: (n.start_ms, n.end_ms) for n in notes}["c1"] == (1_000, 2_000)


def test_padding_is_clamped_at_book_start(tmp_path):
    book = FakeBook()

    transcribe_annotations(
        book, [CLIP], FakeTranscriber(), tmp_path / "n.json", padding_ms=5_000
    )

    assert book.decoded == [(0, 7_000)]


def test_changed_padding_retranscribes_clip(tmp_path):
    notes_file = tmp_path / "notes.json"
    transcribe_annotations(FakeBook(), [CLIP, BOOKMARK], FakeTranscriber(), notes_file)

    book = FakeBook()
    transcribe_annotations(
        book, [CLIP, BOOKMARK], FakeTranscriber(), notes_file, padding_ms=1_000
    )
    assert book.decoded == [(0, 3_000)]

    book = FakeBook()
    transcribe_annotations(
        book, [CLIP, BOOKMARK], FakeTranscriber(), notes_file, padding_ms=1_000
    )
    assert book.decoded == []
