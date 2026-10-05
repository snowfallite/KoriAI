"""e-disclosure.ru behind DisclosurePort (tech.md §8.5)."""

import re

UNSAFE = re.compile(r"[\\/:*?\"<>|]+")


def download_key(file_id: int, filename: str) -> str:
    """FilesPort key of a downloaded file. ponytail: §8.7 lists no key for it yet; add
    downloads/edisclosure/ there with the next contract change (owner's call, S1-09)."""
    return f"downloads/edisclosure/{file_id}/{UNSAFE.sub('_', filename).strip(' .') or 'file'}"
