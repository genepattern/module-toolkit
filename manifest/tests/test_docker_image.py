#!/usr/bin/env python
"""
Test for Docker image field validation.

This test ensures that the job.docker.image field is present and follows
a reasonable format for Docker image names. This is a REQUIRED field.
"""
from __future__ import annotations

import re
import sys
import os
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linter import LintIssue

# Regex for Docker image format: [registry/]name[:tag]
# This is a simplified check - full Docker validation is complex
# Accepts both escaped (\:) and unescaped (:) colons
DOCKER_IMAGE_REGEX = re.compile(r'^[a-z0-9][a-z0-9._/-]*[a-z0-9]((:|\\:)[a-z0-9._-]+)?$', re.IGNORECASE)


def run_test(lines: List[str]) -> List[LintIssue]:
    """
    Test Docker image field validation.

    Args:
        lines: List of lines from the manifest file

    Returns:
        List of LintIssue objects for any Docker image format violations
    """
    issues: List[LintIssue] = []
    docker_image_found = False
    docker_image_value = None
    docker_image_line = None
    docker_image_idx = None

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        # Skip empty lines and comments
        if stripped == "" or stripped.startswith("#") or stripped.startswith("!"):
            continue

        # Skip lines that don't have = separator
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Skip empty keys
        if key == "":
            continue

        # Check job.docker.image field
        if key == "job.docker.image":
            docker_image_found = True
            docker_image_value = value
            docker_image_line = line
            docker_image_idx = idx

    # Check if job.docker.image is present (REQUIRED)
    if not docker_image_found:
        issues.append(LintIssue(
            "ERROR",
            "Missing required field 'job.docker.image'. This field must specify the Docker image tag for the module (e.g., job.docker.image=genepattern/mymodule\\:1)",
            None,
            None,
        ))
    elif not docker_image_value:
        issues.append(LintIssue(
            "ERROR",
            "Field 'job.docker.image' is present but empty. Must specify a valid Docker image tag.",
            docker_image_idx,
            docker_image_line,
        ))
    elif not DOCKER_IMAGE_REGEX.match(docker_image_value):
        issues.append(LintIssue(
            "WARNING",
            f"Docker image name '{docker_image_value}' may not follow standard format. Expected format: [registry/]name[:tag] (colon should be escaped as \\:)",
            docker_image_idx,
            docker_image_line,
        ))

    return issues
