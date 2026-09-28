"""Command-line interface: ``audible-bookmarks {login,logout,list,transcribe}``."""

import argparse
import getpass
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

import audible

from audible_bookmarks import auth, library
from audible_bookmarks.annotations import (
    fetch_annotations,
    parse_annotations,
)
from audible_bookmarks.audio import open_book
from audible_bookmarks.config import DEFAULT_DATA_DIR, Paths
from audible_bookmarks.download import download_book
from audible_bookmarks.errors import TranscriberError
from audible_bookmarks.pipeline import transcribe_annotations
from audible_bookmarks.transcribe import DEFAULT_MODEL, WhisperTranscriber


def _prompt_auth_password() -> str:
    return getpass.getpass("Password for your encrypted Audible credentials: ")


def _prompt_country() -> str:
    print("Choose the country of your Audible account:")
    for code, description in auth.COUNTRY_CODES.items():
        print(f"  {code}: {description}")
    while (code := input("Country code: ").strip().lower()) not in auth.COUNTRY_CODES:
        print("Invalid country code, please pick one from the list above.")
    return code


def cmd_login(args: argparse.Namespace, paths: Paths) -> int:
    if paths.auth_file.exists():
        print(
            f"Already logged in ({paths.auth_file}). "
            "Run `audible-bookmarks logout` first to switch accounts."
        )
        return 0
    country = args.country or _prompt_country()
    password = None
    if args.encrypt:
        password = getpass.getpass("Choose a password to encrypt your credentials: ")
    auth.login(paths.auth_file, country, password)
    print("Logged in successfully.")
    return 0


def cmd_logout(args: argparse.Namespace, paths: Paths) -> int:
    authenticator = auth.load_auth(paths.auth_file, _prompt_auth_password)
    auth.logout(authenticator, paths.auth_file)
    print("Logged out and deregistered this device.")
    return 0


def cmd_list(args: argparse.Namespace, paths: Paths) -> int:
    authenticator = auth.load_auth(paths.auth_file, _prompt_auth_password)
    with audible.Client(auth=authenticator) as client:
        books = library.fetch_library(client, paths.library_file)
    auth.save_auth(authenticator)

    print(f"{'ASIN':<12} {'Title':<50} Author")
    for book in books:
        print(f"{book['asin']:<12} {book['title'][:50]:<50} {library.authors(book)}")
    return 0


def cmd_transcribe(args: argparse.Namespace, paths: Paths) -> int:
    asin: str = args.asin
    authenticator = auth.load_auth(paths.auth_file, _prompt_auth_password)
    with audible.Client(auth=authenticator) as client:
        books = library.load_library(paths.library_file)
        if not any(book["asin"] == asin for book in books):
            books = library.fetch_library(client, paths.library_file)
        book = library.find_book(books, asin)
        print(f"Book: {book['title']}")

        book_file = download_book(client, authenticator, asin, paths.book_dir(asin))
        sidecar = fetch_annotations(client, asin, paths.annotations_file(asin))
    auth.save_auth(authenticator)

    transcriber = WhisperTranscriber(model=args.model)
    with open_book(book_file.path, book_file.decryption_options) as audio_book:
        annotations = parse_annotations(
            sidecar,
            bookmark_window_ms=round(args.bookmark_window * 1000),
            duration_ms=audio_book.duration_ms,
        )
        if not annotations:
            print("No clips or bookmarks found for this book.")
            return 0
        print(f"Found {len(annotations)} clips/bookmarks.")
        transcribe_annotations(
            audio_book,
            annotations,
            transcriber,
            paths.notes_file(asin),
            clips_dir=paths.clips_dir(asin) if args.save_clips else None,
            force=args.force,
            padding_ms=round(args.clip_padding * 1000),
        )
    print(f"Done. Notes saved to {paths.notes_file(asin)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audible-bookmarks",
        description="Transcribe the clips and bookmarks from your Audible books.",
    )
    parser.add_argument(
        "--data-dir",
        type=lambda value: Paths(Path(value)),
        default=Paths(DEFAULT_DATA_DIR),
        dest="paths",
        metavar="DIR",
        help=f"credentials and downloads location (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    commands = parser.add_subparsers(dest="command", required=True)

    login = commands.add_parser("login", help="sign in to Audible in your browser")
    login.add_argument(
        "--country", choices=sorted(auth.COUNTRY_CODES), help="marketplace"
    )
    login.add_argument(
        "--encrypt", action="store_true", help="password-protect saved credentials"
    )
    login.set_defaults(func=cmd_login)

    logout = commands.add_parser("logout", help="deregister and delete credentials")
    logout.set_defaults(func=cmd_logout)

    list_ = commands.add_parser("list", help="list the books in your library")
    list_.set_defaults(func=cmd_list)

    transcribe = commands.add_parser(
        "transcribe", help="transcribe a book's clips and bookmarks"
    )
    transcribe.add_argument("asin", help="book ASIN (see `list`)")
    transcribe.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"mlx-whisper model repo (default: {DEFAULT_MODEL})",
    )
    transcribe.add_argument(
        "--bookmark-window",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="audio to transcribe after a plain bookmark (default: 30)",
    )
    transcribe.add_argument(
        "--clip-padding",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="extra audio to transcribe before and after each clip (default: 0)",
    )
    transcribe.add_argument(
        "--save-clips", action="store_true", help="also save each clip as an mp3"
    )
    transcribe.add_argument(
        "--force", action="store_true", help="re-transcribe existing notes"
    )
    transcribe.set_defaults(func=cmd_transcribe)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args, args.paths)
    except TranscriberError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
