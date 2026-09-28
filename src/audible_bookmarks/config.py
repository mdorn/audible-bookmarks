"""Filesystem layout for credentials, library cache and per-book data."""

from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = Path("data")


@dataclass(frozen=True)
class Paths:
    data_dir: Path = DEFAULT_DATA_DIR

    @property
    def config_dir(self) -> Path:
        return self.data_dir / "audible_configs"

    @property
    def auth_file(self) -> Path:
        return self.config_dir / "audible.json"

    @property
    def library_file(self) -> Path:
        return self.config_dir / "library.json"

    def book_dir(self, asin: str) -> Path:
        return self.data_dir / "audio" / asin

    def notes_file(self, asin: str) -> Path:
        return self.book_dir(asin) / "transcribed_notes.json"

    def annotations_file(self, asin: str) -> Path:
        return self.book_dir(asin) / "annotations.json"

    def clips_dir(self, asin: str) -> Path:
        return self.book_dir(asin) / "clips"
