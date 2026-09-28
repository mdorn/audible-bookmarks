"""Requesting a download license and fetching the (still encrypted) audiobook file.

The book is kept exactly as Audible delivers it (``.aaxc``) alongside the decrypted
license voucher; clips are decrypted on the fly by :mod:`.audio`.
"""

import json
import logging
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import audible
from audible.aescipher import decrypt_voucher_from_licenserequest

from audible_bookmarks.errors import LicenseError

logger = logging.getLogger(__name__)

# Headers mirror the Audible iOS app; the license endpoint rejects requests
# that don't look like they come from a registered device.
LICENSE_HEADERS = {
    "X-ADP-SW": "37801821",
    "X-ADP-Transport": "WIFI",
    "X-ADP-LTO": "120",
    "X-Device-Type-Id": "A2CZJZGLK2JJVM",
    "device_idiom": "phone",
}
DOWNLOAD_HEADERS = {"User-Agent": "Audible/671 CFNetwork/1240.0.4 Darwin/20.6.0"}
AUDIO_SUFFIXES = (".aaxc", ".mp3")
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class BookFile:
    """A downloaded audiobook and the key material needed to decrypt it."""

    path: Path
    key: str | None = None
    iv: str | None = None

    @property
    def decryption_options(self) -> dict[str, str]:
        if self.key and self.iv:
            return {"audible_key": self.key, "audible_iv": self.iv}
        return {}


def book_file_from_voucher(voucher_path: Path) -> BookFile | None:
    """Build a :class:`BookFile` from a saved voucher if its audio file exists.

    The voucher is the license response with the decrypted ``license_response``,
    stored next to an audio file sharing its stem.
    """
    for suffix in AUDIO_SUFFIXES:
        audio_path = voucher_path.with_suffix(suffix)
        if audio_path.exists():
            break
    else:
        return None
    voucher = json.loads(voucher_path.read_text(encoding="utf-8"))
    license_response = voucher["content_license"].get("license_response") or {}
    return BookFile(
        path=audio_path, key=license_response.get("key"), iv=license_response.get("iv")
    )


def find_local_book(book_dir: Path) -> BookFile | None:
    if not book_dir.is_dir():
        return None
    for voucher_path in sorted(book_dir.glob("*.voucher")):
        if book_file := book_file_from_voucher(voucher_path):
            return book_file
    return None


def request_license(
    client: audible.Client, auth: audible.Authenticator, asin: str
) -> dict[str, Any]:
    """Request a download license and decrypt its voucher in place."""
    body = {
        "supported_drm_types": ["Mpeg", "Adrm"],
        "quality": "High",
        "consumption_type": "Download",
        "response_groups": "content_reference",
    }
    headers = {"X-Amzn-RequestId": secrets.token_hex(20).upper(), **LICENSE_HEADERS}
    response = client.post(f"content/{asin}/licenserequest", body=body, headers=headers)
    content_license = response["content_license"]

    if content_license["status_code"] == "Denied":
        raise LicenseError(
            f"Audible denied a license for {asin}: {content_license.get('message')}"
        )
    offline_url = (
        content_license["content_metadata"].get("content_url", {}).get("offline_url")
    )
    if offline_url is None:
        raise LicenseError(f"Audible returned no download URL for {asin}.")

    if "license_response" in content_license:
        content_license["license_response"] = decrypt_voucher_from_licenserequest(
            auth, response
        )
    return response


def _stream_to_file(client: audible.Client, url: str, target: Path) -> None:
    partial = target.with_name(target.name + ".part")
    with (
        client.session.stream("GET", url, headers=DOWNLOAD_HEADERS) as resp,
        partial.open("wb") as f,
    ):
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        for chunk in resp.iter_bytes(CHUNK_SIZE):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / total:6.1%} of {total / 1e6:.0f} MB", end="")
    print()
    partial.replace(target)


def download_book(
    client: audible.Client, auth: audible.Authenticator, asin: str, book_dir: Path
) -> BookFile:
    """Return the local book file, downloading it first if needed."""
    if book_file := find_local_book(book_dir):
        logger.info("Using existing download %s", book_file.path)
        return book_file

    license_ = request_license(client, auth, asin)
    content_license = license_["content_license"]
    url = content_license["content_metadata"]["content_url"]["offline_url"]
    suffix = ".aaxc" if content_license.get("drm_type") == "Adrm" else ".mp3"

    book_dir.mkdir(parents=True, exist_ok=True)
    audio_path = book_dir / f"{asin}{suffix}"
    print(f"Downloading to {audio_path}")
    _stream_to_file(client, url, audio_path)

    voucher_path = audio_path.with_suffix(".voucher")
    voucher_path.write_text(json.dumps(license_, indent=4), encoding="utf-8")
    voucher_path.chmod(0o600)

    book_file = book_file_from_voucher(voucher_path)
    assert book_file is not None
    return book_file
