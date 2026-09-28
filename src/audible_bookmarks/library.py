"""Fetching and caching the user's Audible library."""

import json
from pathlib import Path
from typing import Any

import audible

from audible_bookmarks.errors import BookNotFoundError

Book = dict[str, Any]


def fetch_library(client: audible.Client, library_file: Path) -> list[Book]:
    """Download the library from Audible and cache it to ``library_file``."""
    response = client.get(
        "1.0/library",
        params={
            "num_results": 1000,
            "response_groups": "product_desc, product_attrs, contributors",
            "sort_by": "-PurchaseDate",
        },
    )
    items: list[Book] = response["items"]
    library_file.parent.mkdir(parents=True, exist_ok=True)
    library_file.write_text(
        json.dumps(items, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    return items


def load_library(library_file: Path) -> list[Book]:
    if not library_file.exists():
        return []
    return json.loads(library_file.read_text(encoding="utf-8"))


def find_book(library: list[Book], asin: str) -> Book:
    for book in library:
        if book["asin"] == asin:
            return book
    raise BookNotFoundError(asin)


def authors(book: Book) -> str:
    return ", ".join(author["name"] for author in book.get("authors") or [])
