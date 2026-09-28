import av
import numpy as np

from audible_bookmarks.audio import SAMPLE_RATE, open_book, save_clip


def _rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(samples**2)))


def test_decode_range_returns_exact_length_at_16khz(tone_file):
    with open_book(tone_file) as book:
        samples = book.decode_range(500, 1_750)

    assert samples.dtype == np.float32
    assert samples.shape == (round(1.25 * SAMPLE_RATE),)


def test_decode_range_selects_the_right_audio(tone_file):
    with open_book(tone_file) as book:
        silence = book.decode_range(200, 1_800)
        tone = book.decode_range(2_200, 3_800)

    assert _rms(silence) < 0.01
    assert _rms(tone) > 0.2


def test_ranges_can_be_decoded_in_any_order(tone_file):
    with open_book(tone_file) as book:
        tone = book.decode_range(2_200, 3_000)
        silence = book.decode_range(0, 1_000)

    assert _rms(tone) > 0.2
    assert _rms(silence) < 0.01


def test_duration(tone_file):
    with open_book(tone_file) as book:
        assert book.duration_ms is not None
        assert abs(book.duration_ms - 4_000) < 100


def test_save_clip_writes_playable_mp3(tmp_path):
    samples = np.zeros(SAMPLE_RATE, dtype=np.float32)
    path = tmp_path / "clips" / "clip.mp3"

    save_clip(samples, path)

    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        assert stream.codec_context.codec.id == av.Codec("mp3").id
        assert container.duration is not None
        assert abs(container.duration / 1_000_000 - 1.0) < 0.1
