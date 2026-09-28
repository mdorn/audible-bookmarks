from audible_bookmarks.annotations import Annotation, parse_annotations


def _sidecar(*records: dict) -> dict:
    return {"payload": {"type": "AUDI", "key": "B000TEST", "records": list(records)}}


CLIP = {
    "annotationId": "clip-1",
    "type": "audible.clip",
    "startPosition": "10000",
    "endPosition": "40000",
    "metadata": {"c_version": "2", "title": ""},
    "creationTime": "2025-08-30 00:33:40.0",
}
PAIRED_BOOKMARK = {
    "annotationId": "bm-paired",
    "type": "audible.bookmark",
    "startPosition": "10000",
}
LONE_BOOKMARK = {
    "annotationId": "bm-lone",
    "type": "audible.bookmark",
    "startPosition": "5000",
}
LAST_HEARD = {"type": "audible.last_heard", "startPosition": "1"}


def test_clip_is_parsed_with_its_range():
    [clip] = parse_annotations(_sidecar(CLIP), bookmark_window_ms=30_000)
    assert clip == Annotation(
        id="clip-1",
        kind="clip",
        start_ms=10_000,
        end_ms=40_000,
        note="",
        created="2025-08-30 00:33:40.0",
    )


def test_bookmark_at_clip_position_is_dropped():
    result = parse_annotations(_sidecar(CLIP, PAIRED_BOOKMARK), bookmark_window_ms=1)
    assert [a.id for a in result] == ["clip-1"]


def test_lone_bookmark_gets_window_and_results_are_sorted():
    result = parse_annotations(
        _sidecar(CLIP, LONE_BOOKMARK, LAST_HEARD), bookmark_window_ms=20_000
    )
    assert [(a.id, a.kind, a.start_ms, a.end_ms) for a in result] == [
        ("bm-lone", "bookmark", 5_000, 25_000),
        ("clip-1", "clip", 10_000, 40_000),
    ]


def test_bookmark_window_is_clamped_to_duration():
    [bookmark] = parse_annotations(
        _sidecar(LONE_BOOKMARK), bookmark_window_ms=30_000, duration_ms=6_000
    )
    assert bookmark.end_ms == 6_000


def test_note_text_is_taken_from_metadata():
    clip = {**CLIP, "metadata": {"note": "  remember this  ", "title": "ignored"}}
    [parsed] = parse_annotations(_sidecar(clip), bookmark_window_ms=0)
    assert parsed.note == "remember this"
