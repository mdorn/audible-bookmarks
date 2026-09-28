from pathlib import Path

import av
import numpy as np
import pytest

SOURCE_RATE = 22_050


@pytest.fixture(scope="session")
def tone_file(tmp_path_factory) -> Path:
    """A 4 s mono AAC file: silence for 0-2 s, a 440 Hz tone for 2-4 s.

    Stands in for a (decrypted) audiobook, which is AAC in an MP4 container.
    """
    path = tmp_path_factory.mktemp("audio") / "tone.m4a"
    t = np.arange(4 * SOURCE_RATE) / SOURCE_RATE
    samples = np.where(t >= 2, 0.5 * np.sin(2 * np.pi * 440 * t), 0.0)

    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("aac", rate=SOURCE_RATE, layout="mono")
        frame = av.AudioFrame.from_ndarray(
            samples.astype(np.float32).reshape(1, -1), format="flt", layout="mono"
        )
        frame.sample_rate = SOURCE_RATE
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return path
