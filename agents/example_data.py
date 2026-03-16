"""
Example data resolution for the module generation pipeline.

Validates and normalises --data items (local paths or URLs) into
ExampleDataItem objects that downstream agents can consume uniformly.
"""
import sys
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.logger import Logger


class ExampleDataItem:
    """Represents a single example data file (local path or URL)."""

    def __init__(
        self,
        original: str,
        resolved: str,
        is_url: bool,
        extension: str,
        filename: str,
        local_path: Optional[str] = None,
    ):
        self.original = original        # Original value as supplied by the user
        self.resolved = resolved        # Resolved value: absolute path for local files, original URL for URLs
        self.is_url = is_url            # True if this item came from a URL
        self.extension = extension      # File extension, e.g. '.bam'
        self.filename = filename        # Basename, e.g. 'sample.bam'
        self.local_path = local_path    # Absolute local filesystem path; set after download for URLs

    @property
    def has_local(self) -> bool:
        """Return True if a local file path is available."""
        return self.local_path is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'original': self.original,
            'resolved': self.resolved,
            'is_url': self.is_url,
            'extension': self.extension,
            'filename': self.filename,
            'local_path': self.local_path,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ExampleDataItem':
        return cls(
            original=d['original'],
            resolved=d['resolved'],
            is_url=d['is_url'],
            extension=d['extension'],
            filename=d['filename'],
            local_path=d.get('local_path'),
        )


class ExampleDataResolver:
    """Validates and normalises --data items into ExampleDataItem objects."""

    def __init__(self, logger: Logger):
        self.logger = logger

    def resolve(self, items: List[str]) -> List[ExampleDataItem]:
        """Validate and normalise a list of paths/URLs into ExampleDataItem objects."""
        result = []
        for item in items:
            if item.startswith('http://') or item.startswith('https://'):
                resolved = self._resolve_url(item)
            else:
                resolved = self._resolve_local(item)
            if resolved:
                result.append(resolved)
        return result

    def _resolve_url(self, url: str) -> Optional[ExampleDataItem]:
        filename = url.split('?')[0].rstrip('/').split('/')[-1] or 'data'
        ext = Path(filename).suffix.lower()
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code >= 400:
                self.logger.print_status(
                    f"URL returned HTTP {resp.status_code}: {url} — continuing without this item",
                    "WARNING"
                )
                return None
        except Exception as e:
            self.logger.print_status(
                f"Could not reach URL {url} ({e}) — continuing without this item",
                "WARNING"
            )
            return None
        return ExampleDataItem(
            original=url, resolved=url, is_url=True,
            extension=ext, filename=filename, local_path=None
        )

    def _resolve_local(self, path: str) -> Optional[ExampleDataItem]:
        p = Path(path).resolve()
        if not p.exists():
            print(f"Error: Example data file not found: {path}")
            sys.exit(1)
        return ExampleDataItem(
            original=path, resolved=str(p), is_url=False,
            extension=p.suffix.lower(), filename=p.name, local_path=str(p)
        )

