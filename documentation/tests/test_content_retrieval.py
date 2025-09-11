#!/usr/bin/env python
"""
Test for documentation content retrieval.

This test validates that documentation can be retrieved from files or URLs
and supports multiple formats (HTML, Markdown, PDF, TXT).
"""
from __future__ import annotations

import sys
import os
import re
from typing import List
from dataclasses import dataclass
from urllib.parse import urlparse

# Add parent directory to path for imports  
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import libraries with safe fallbacks
try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


@dataclass
class LintIssue:
    """Represents a validation issue found during documentation linting."""
    severity: str  # 'ERROR' or 'WARNING' or 'INFO'
    message: str
    context: str | None = None

    def format(self) -> str:
        """Format the issue for human-readable output."""
        context_info = f" ({self.context})" if self.context else ""
        return f"{self.severity}: {self.message}{context_info}"


def detect_format(path_or_url: str) -> str:
    """Detect documentation format based on file extension or URL."""
    path_lower = path_or_url.lower()
    
    if path_lower.endswith('.html') or path_lower.endswith('.htm'):
        return 'html'
    elif path_lower.endswith('.md') or path_lower.endswith('.markdown'):
        return 'markdown'
    elif path_lower.endswith('.pdf'):
        return 'pdf'
    elif path_lower.endswith('.txt'):
        return 'txt'
    else:
        # Default to text for unknown formats
        return 'txt'


def is_url(path_or_url: str) -> bool:
    """Check if the input is a URL."""
    parsed = urlparse(path_or_url)
    return parsed.scheme in ('http', 'https')


def retrieve_file_content(file_path: str) -> tuple[str, str]:
    """Retrieve content from a local file.
    
    Returns:
        Tuple of (content, error_message). Error message is empty on success.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read(), ""
    except FileNotFoundError:
        return "", f"File not found: {file_path}"
    except PermissionError:
        return "", f"Permission denied: {file_path}"
    except UnicodeDecodeError:
        # Try binary mode for PDFs
        try:
            with open(file_path, 'rb') as f:
                return f.read(), ""
        except Exception as e:
            return "", f"Failed to read file (encoding issue): {str(e)}"
    except Exception as e:
        return "", f"Failed to read file: {str(e)}"


def retrieve_url_content(url: str) -> tuple[str, str]:
    """Retrieve content from a URL.
    
    Returns:
        Tuple of (content, error_message). Error message is empty on success.
    """
    if requests is None:
        return "", "requests library not available - install with: pip install requests"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Handle binary content (like PDFs)
        if 'application/pdf' in response.headers.get('content-type', ''):
            return response.content, ""
        else:
            return response.text, ""
            
    except requests.exceptions.ConnectionError:
        return "", f"Failed to connect to URL: {url}"
    except requests.exceptions.Timeout:
        return "", f"Timeout while accessing URL: {url}"
    except requests.exceptions.HTTPError as e:
        return "", f"HTTP error accessing URL: {e}"
    except Exception as e:
        return "", f"Failed to retrieve URL content: {str(e)}"


def extract_text_from_html(html_content: str) -> str:
    """Extract text content from HTML."""
    if BeautifulSoup is None:
        # Fallback: simple HTML tag removal
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception:
        # Fallback to simple tag removal
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


def extract_text_from_pdf(pdf_content: bytes) -> str:
    """Extract text content from PDF."""
    if PyPDF2 is None:
        return ""  # Cannot extract text without PyPDF2
    
    try:
        import io
        pdf_file = io.BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text_content = []
        for page in pdf_reader.pages:
            text_content.append(page.extract_text())
        
        return "\n".join(text_content)
    except Exception:
        return ""  # Failed to extract text


def process_content(content, doc_format: str) -> str:
    """Process content based on format to extract plain text."""
    if doc_format == 'html':
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        return extract_text_from_html(content)
    elif doc_format == 'pdf':
        if isinstance(content, str):
            content = content.encode('utf-8')
        return extract_text_from_pdf(content)
    elif doc_format in ('markdown', 'txt'):
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        return content
    else:
        # Default to plain text
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        return content


def run_test(doc_path_or_url: str, shared_context: dict) -> List[LintIssue]:
    """
    Test documentation content retrieval.
    
    Args:
        doc_path_or_url: Path to documentation file or URL
        shared_context: Mutable dict with test context
        
    Returns:
        List of LintIssue objects for any retrieval failures
    """
    issues: List[LintIssue] = []
    
    # Detect format
    doc_format = detect_format(doc_path_or_url)
    shared_context['doc_format'] = doc_format
    
    # Check if it's a URL or file
    is_url_input = is_url(doc_path_or_url)
    shared_context['is_url'] = is_url_input
    
    # Check required dependencies based on format
    if doc_format == 'html' and BeautifulSoup is None:
        issues.append(LintIssue(
            "WARNING",
            "beautifulsoup4 library not available - HTML parsing will be limited",
            "Install with: pip install beautifulsoup4"
        ))
    
    if doc_format == 'pdf' and PyPDF2 is None:
        issues.append(LintIssue(
            "ERROR",
            "PyPDF2 library not available - cannot parse PDF files",
            "Install with: pip install PyPDF2"
        ))
        return issues
    
    if is_url_input and requests is None:
        issues.append(LintIssue(
            "ERROR",
            "requests library not available - cannot fetch URLs",
            "Install with: pip install requests"
        ))
        return issues
    
    # Retrieve content
    if is_url_input:
        content, error = retrieve_url_content(doc_path_or_url)
    else:
        # Check if file exists first
        if not os.path.exists(doc_path_or_url):
            issues.append(LintIssue(
                "ERROR",
                f"Documentation file does not exist: {doc_path_or_url}"
            ))
            return issues
        
        content, error = retrieve_file_content(doc_path_or_url)
    
    if error:
        issues.append(LintIssue(
            "ERROR",
            f"Failed to retrieve documentation: {error}"
        ))
        return issues
    
    if not content:
        issues.append(LintIssue(
            "ERROR",
            "Documentation is empty"
        ))
        return issues
    
    # Process content based on format
    try:
        processed_content = process_content(content, doc_format)
        shared_context['doc_content'] = processed_content
        shared_context['raw_content'] = content
        
        if not processed_content.strip():
            issues.append(LintIssue(
                "WARNING",
                f"No text content extracted from {doc_format.upper()} document",
                "Document may be empty or format not supported"
            ))
        else:
            issues.append(LintIssue(
                "INFO",
                f"Successfully retrieved {len(processed_content)} characters from {doc_format.upper()} document"
            ))
            
    except Exception as e:
        issues.append(LintIssue(
            "ERROR",
            f"Failed to process {doc_format.upper()} content: {str(e)}"
        ))
        return issues
    
    return issues
