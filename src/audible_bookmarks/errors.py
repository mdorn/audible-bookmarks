"""Exceptions surfaced to the user by the CLI."""


class TranscriberError(Exception):
    """Base class for errors that the CLI reports without a traceback."""


class NotLoggedInError(TranscriberError):
    def __init__(self) -> None:
        super().__init__(
            "Not logged in. Run `audible-bookmarks login` to authenticate."
        )


class BookNotFoundError(TranscriberError):
    def __init__(self, asin: str) -> None:
        super().__init__(
            f"Book {asin} not found in your library. "
            "Run `audible-bookmarks list` to see available ASINs."
        )


class LicenseError(TranscriberError):
    """Audible refused a license or returned no download URL."""
