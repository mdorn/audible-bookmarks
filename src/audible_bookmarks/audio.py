"""Decrypting and decoding time ranges of an audiobook with PyAV."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import av
import numpy as np
from av.audio.stream import AudioStream
from av.container import InputContainer

# Whisper models expect 16 kHz mono float32 PCM.
SAMPLE_RATE = 16_000


class AudioBook:
    """An open (optionally encrypted) audiobook that can decode arbitrary ranges."""

    def __init__(self, container: InputContainer) -> None:
        self._container = container
        self._stream: AudioStream = container.streams.audio[0]

    @property
    def duration_ms(self) -> int | None:
        if self._container.duration is None:
            return None
        return self._container.duration // 1000

    def chapter_at(self, position_ms: int) -> str | None:
        for chapter in self._container.chapters():
            time_base = chapter["time_base"]
            if time_base is None:
                continue
            start = float(chapter["start"] * time_base) * 1000
            end = float(chapter["end"] * time_base) * 1000
            if start <= position_ms < end:
                return chapter["metadata"].get("title")
        return None

    def decode_range(self, start_ms: int, end_ms: int) -> np.ndarray:
        """Return ``[start_ms, end_ms)`` as 16 kHz mono float32 samples."""
        # Seeking lands on the keyframe at or before the target, so decode from
        # there and trim to the exact sample range afterwards.
        self._container.seek(start_ms * 1000)
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
        time_base = self._stream.time_base
        assert time_base is not None

        chunks: list[np.ndarray] = []
        first_sample_ms: float | None = None
        for frame in self._container.decode(self._stream):
            if frame.pts is None:
                continue
            frame_ms = float(frame.pts * time_base) * 1000
            if frame_ms >= end_ms:
                break
            if first_sample_ms is None:
                first_sample_ms = frame_ms
            for resampled in resampler.resample(frame):
                chunks.append(resampled.to_ndarray()[0])
        for resampled in resampler.resample(None):
            chunks.append(resampled.to_ndarray()[0])

        if not chunks or first_sample_ms is None:
            return np.zeros(0, dtype=np.float32)
        samples = np.concatenate(chunks)
        offset = max(0, round((start_ms - first_sample_ms) * SAMPLE_RATE / 1000))
        length = round((end_ms - start_ms) * SAMPLE_RATE / 1000)
        return samples[offset : offset + length].astype(np.float32, copy=False)


@contextmanager
def open_book(
    path: Path, decryption_options: dict[str, str] | None = None
) -> Iterator[AudioBook]:
    options: dict[str, Any] = dict(decryption_options or {})
    with av.open(str(path), options=options) as container:
        assert isinstance(container, InputContainer)
        yield AudioBook(container)


def save_clip(samples: np.ndarray, path: Path) -> None:
    """Write mono float32 samples at :data:`SAMPLE_RATE` to an audio file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("libmp3lame", rate=SAMPLE_RATE, layout="mono")
        assert isinstance(stream, AudioStream)
        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1), format="flt", layout="mono"
        )
        frame.sample_rate = SAMPLE_RATE
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
