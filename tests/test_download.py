import json
from typing import Any

import pytest

from audible_bookmarks import download
from audible_bookmarks.download import (
    BookFile,
    download_book,
    find_local_book,
    request_license,
)
from audible_bookmarks.errors import LicenseError


def _license(status: str = "Granted", **content_license: Any) -> dict[str, Any]:
    return {
        "content_license": {
            "status_code": status,
            "drm_type": "Adrm",
            "content_metadata": {"content_url": {"offline_url": "https://cdn/x"}},
            **content_license,
        }
    }


class FakeClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.posts: list[str] = []

    def post(self, path: str, body: Any, **kwargs: Any) -> dict[str, Any]:
        self.posts.append(path)
        return self.response


def test_voucher_next_to_audio_is_recognised(tmp_path):
    (tmp_path / "Book-AAX_22_64.aaxc").write_bytes(b"")
    voucher = _license(license_response={"key": "k", "iv": "i", "rules": []})
    (tmp_path / "Book-AAX_22_64.voucher").write_text(json.dumps(voucher))

    book_file = find_local_book(tmp_path)

    assert book_file is not None
    assert book_file == BookFile(tmp_path / "Book-AAX_22_64.aaxc", key="k", iv="i")
    assert book_file.decryption_options == {"audible_key": "k", "audible_iv": "i"}


def test_voucher_without_audio_is_ignored(tmp_path):
    (tmp_path / "B1.voucher").write_text(json.dumps(_license()))
    assert find_local_book(tmp_path) is None
    assert find_local_book(tmp_path / "missing") is None


def test_unencrypted_book_has_no_decryption_options(tmp_path):
    (tmp_path / "B1.mp3").write_bytes(b"")
    (tmp_path / "B1.voucher").write_text(json.dumps(_license(drm_type="Mpeg")))

    book_file = find_local_book(tmp_path)

    assert book_file is not None
    assert book_file.decryption_options == {}


def test_denied_license_raises():
    client = FakeClient(_license("Denied", message="Not owned"))
    with pytest.raises(LicenseError, match="Not owned"):
        request_license(client, auth=None, asin="B1")  # type: ignore[arg-type]


def test_license_without_url_raises():
    response = _license()
    response["content_license"]["content_metadata"] = {}
    with pytest.raises(LicenseError, match="no download URL"):
        request_license(FakeClient(response), auth=None, asin="B1")  # type: ignore[arg-type]


def test_license_voucher_is_decrypted(monkeypatch):
    monkeypatch.setattr(
        download,
        "decrypt_voucher_from_licenserequest",
        lambda auth, lr: {"key": "k", "iv": "i"},
    )
    client = FakeClient(_license(license_response="ENCRYPTED"))

    result = request_license(client, auth=None, asin="B1")  # type: ignore[arg-type]

    assert client.posts == ["content/B1/licenserequest"]
    assert result["content_license"]["license_response"] == {"key": "k", "iv": "i"}


def test_existing_download_is_reused(tmp_path):
    (tmp_path / "B1.aaxc").write_bytes(b"")
    (tmp_path / "B1.voucher").write_text(json.dumps(_license()))
    client = FakeClient(_license())

    download_book(client, auth=None, asin="B1", book_dir=tmp_path)  # type: ignore[arg-type]

    assert client.posts == []
