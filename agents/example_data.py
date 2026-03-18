"""
Example data resolution for the module generation pipeline.

Validates and normalises --data items (local paths or URLs) into
ExampleDataItem objects that downstream agents can consume uniformly.

Items may carry an optional semantic hint supplied via the ``::`` separator:

    sample1.bam::tumor_sample
    hg38.fasta::reference
    foo.vcf::germline_resource

The hint is stored on the item and propagated to LLM prompts and the runtime
file-matching logic so downstream code can distinguish files that share the
same extension.
"""
import sys
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.logger import Logger

# Separator between path/URL and the optional semantic hint
_HINT_SEP = "::"


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
        hint: Optional[str] = None,
    ):
        self.original = original        # Original value as supplied by the user
        self.resolved = resolved        # Resolved value: absolute path for local files, original URL for URLs
        self.is_url = is_url            # True if this item came from a URL
        self.extension = extension      # File extension, e.g. '.bam'
        self.filename = filename        # Basename, e.g. 'sample.bam'
        self.local_path = local_path    # Absolute local filesystem path; set after download for URLs
        self.hint = hint                # Optional semantic hint, e.g. 'tumor_sample', 'reference'

    @property
    def has_local(self) -> bool:
        """Return True if a local file path is available."""
        return self.local_path is not None

    @property
    def hint_label(self) -> str:
        """Return a human-readable label string, e.g. ' [hint: tumor_sample]', or '' if no hint."""
        return f" [hint: {self.hint}]" if self.hint else ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'original': self.original,
            'resolved': self.resolved,
            'is_url': self.is_url,
            'extension': self.extension,
            'filename': self.filename,
            'local_path': self.local_path,
            'hint': self.hint,
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
            hint=d.get('hint'),          # graceful default for pre-hint status.json files
        )


class ExampleDataResolver:
    """Validates and normalises --data items into ExampleDataItem objects."""

    def __init__(self, logger: Logger):
        self.logger = logger

    def resolve(self, items: List[str]) -> List[ExampleDataItem]:
        """Validate and normalise a list of paths/URLs into ExampleDataItem objects.

        Each item may carry an optional semantic hint separated by ``::``::

            sample1.bam::tumor_sample
            https://example.com/hg38.fa.gz::reference

        Items without ``::`` are handled exactly as before.
        """
        result = []
        for raw in items:
            # Split off the optional hint before any URL/path processing
            if _HINT_SEP in raw:
                path_part, hint = raw.split(_HINT_SEP, 1)
                hint = hint.strip() or None
            else:
                path_part = raw
                hint = None

            if path_part.startswith('http://') or path_part.startswith('https://'):
                resolved = self._resolve_url(path_part, hint=hint)
            else:
                resolved = self._resolve_local(path_part, hint=hint)
            if resolved:
                result.append(resolved)
        return result

    def _resolve_url(self, url: str, *, hint: Optional[str] = None) -> Optional['ExampleDataItem']:
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
            extension=ext, filename=filename, local_path=None,
            hint=hint,
        )

    def _resolve_local(self, path: str, *, hint: Optional[str] = None) -> Optional['ExampleDataItem']:
        p = Path(path).resolve()
        if not p.exists():
            print(f"Error: Example data file not found: {path}")
            sys.exit(1)
        return ExampleDataItem(
            original=path, resolved=str(p), is_url=False,
            extension=p.suffix.lower(), filename=p.name, local_path=str(p),
            hint=hint,
        )
