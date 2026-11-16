"""Google Drive URL parsing utilities."""

import re
from urllib.parse import parse_qs, urlparse

from app.errors import AppError

# Matches a valid Drive resource ID.
DRIVE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,100}$")


def is_valid_drive_id(value: str) -> bool:
    """Return True when *value* looks like a valid Drive resource ID."""
    return bool(DRIVE_ID_RE.match(value))


# /drive/folders/<ID>  or  /drive/u/<n>/folders/<ID>
# Strictly anchored: nothing may follow the ID in the path.
_FOLDER_PATH_RE = re.compile(r"^/drive(?:/u/\d+)?/folders/([^/?#]+)$")
# /file/d/<ID>
_FILE_PATH_RE = re.compile(r"^/file/d/([^/?#]+)")


def _invalid(message: str) -> AppError:
    return AppError("INVALID_FOLDER_URL", message, 422)


def extract_folder_id(url: str) -> str:
    """Parse *url* and return the Drive folder ID it references.

    Raises :class:`~app.errors.AppError` (INVALID_FOLDER_URL, 422) for every
    input that is not a valid Google Drive folder URL.  No network calls are
    made.
    """
    url = url.strip()

    if not url:
        raise _invalid("URL must not be empty.")

    try:
        parsed = urlparse(url)
    except Exception:
        raise _invalid("URL could not be parsed.") from None

    # Scheme check
    if parsed.scheme.lower() != "https":
        raise _invalid(
            f"URL scheme must be https, got {parsed.scheme!r}."
            if parsed.scheme
            else "URL scheme must be https."
        )

    # Hostname check – must be exactly drive.google.com with no port.
    # parsed.hostname strips the port, so check netloc directly as well.
    hostname = (parsed.hostname or "").lower()
    if hostname != "drive.google.com" or parsed.port is not None:
        raise _invalid(
            "Host must be exactly drive.google.com."
            f" Got {parsed.netloc!r}."
        )

    path = parsed.path

    # Reject file links with a specific message
    if _FILE_PATH_RE.match(path):
        raise _invalid(
            "This is a file link; a folder link is required"
            " (the URL must contain /drive/folders/)."
        )

    # /drive/folders/<ID> or /drive/u/<n>/folders/<ID>
    folder_match = _FOLDER_PATH_RE.match(path)
    if folder_match:
        raw_id = folder_match.group(1)
        if not is_valid_drive_id(raw_id):
            raise _invalid(
                f"Folder ID {raw_id!r} is not valid;"
                " expected 10–100 alphanumeric, hyphen, or underscore characters."
            )
        return raw_id

    # /open?id=<ID>
    if path.rstrip("/") == "/open":
        qs = parse_qs(parsed.query)
        ids = qs.get("id", [])
        if not ids or not ids[0]:
            raise _invalid("URL uses /open but is missing the 'id' query parameter.")
        raw_id = ids[0]
        if not is_valid_drive_id(raw_id):
            raise _invalid(
                f"Folder ID {raw_id!r} is not valid;"
                " expected 10–100 alphanumeric, hyphen, or underscore characters."
            )
        return raw_id

    raise _invalid(
        "URL does not point to a Drive folder."
        " Expected a path like /drive/folders/<ID> or /open?id=<ID>."
    )
