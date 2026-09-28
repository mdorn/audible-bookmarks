"""Local speech-to-text with mlx-whisper (Apple Silicon only)."""

from typing import Protocol

import numpy as np

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


class Transcriber(Protocol):
    def transcribe(self, samples: np.ndarray) -> str: ...


class WhisperTranscriber:
    """Transcribes 16 kHz mono float32 samples with an mlx-whisper model.

    The model is downloaded from Hugging Face on first use and cached.
    """

    def __init__(self, model: str = DEFAULT_MODEL, language: str = "en") -> None:
        self.model = model
        self.language = language

    def transcribe(self, samples: np.ndarray) -> str:
        # Imported lazily: mlx is heavy and only works on Apple Silicon, and the
        # rest of the CLI (login, list) should not depend on it.
        import mlx_whisper

        result = mlx_whisper.transcribe(
            samples, path_or_hf_repo=self.model, language=self.language
        )
        text = result["text"]
        assert isinstance(text, str)
        return text.strip()
