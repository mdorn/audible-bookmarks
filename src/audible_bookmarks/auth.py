"""Audible authentication using the ``audible`` library's external browser login."""

import contextlib
import logging
from collections.abc import Callable
from pathlib import Path

import audible
from audible.aescipher import detect_file_encryption

from audible_bookmarks.errors import NotLoggedInError

logger = logging.getLogger(__name__)

COUNTRY_CODES: dict[str, str] = {
    "us": "US and all other countries not listed",
    "ca": "Canada",
    "uk": "UK and Ireland",
    "au": "Australia and New Zealand",
    "fr": "France, Belgium, Switzerland",
    "de": "Germany, Austria, Switzerland",
    "jp": "Japan",
    "it": "Italy",
    "in": "India",
    "es": "Spain",
    "br": "Brazil",
}


def _login_url_callback(url: str) -> str:
    # Without readline, input() reads through the terminal's canonical mode, which
    # silently caps a line at 1024 bytes on macOS (MAX_CANON). Amazon's redirect
    # URL is longer than that, so the paste would hang. Importing readline makes
    # input() read the line itself, lifting the limit.
    with contextlib.suppress(ImportError):
        import readline  # noqa: F401
    print(
        "Open the following URL in your browser and sign in to Amazon/Audible.\n"
        "After signing in you will land on a 'page not found' page; copy the full "
        "URL from the address bar and paste it below.\n"
    )
    print(url)
    return input("\nPaste the URL here: ").strip()


def login(auth_file: Path, country_code: str, password: str | None = None) -> None:
    """Register a new device with Audible and save the credentials to ``auth_file``.

    If ``password`` is given, the credentials file is encrypted with it.
    """
    auth = audible.Authenticator.from_login_external(
        locale=country_code, login_url_callback=_login_url_callback
    )
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    if password:
        auth.to_file(auth_file, password=password, encryption="json")
    else:
        auth.to_file(auth_file, encryption=False)
    auth_file.chmod(0o600)
    logger.info("Saved credentials to %s", auth_file)


def load_auth(
    auth_file: Path, password_prompt: Callable[[], str] | None = None
) -> audible.Authenticator:
    """Load previously saved credentials, raising if the user has not logged in.

    ``password_prompt`` is only called when the credentials file is encrypted.
    """
    if not auth_file.exists():
        raise NotLoggedInError
    password = None
    if detect_file_encryption(auth_file) and password_prompt is not None:
        password = password_prompt()
    return audible.Authenticator.from_file(auth_file, password=password)


def save_auth(auth: audible.Authenticator) -> None:
    """Persist refreshed access tokens back to the file the auth was loaded from."""
    auth.to_file()


def logout(auth: audible.Authenticator, auth_file: Path) -> None:
    """Deregister the device with Audible and delete the credentials file."""
    auth.deregister_device()
    auth_file.unlink()
