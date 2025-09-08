#!/usr/bin/env python
"""
GenePattern Dockerfile builder/linter.

Usage:
  python dockerfile/linter.py /path/to/Dockerfile [-t IMAGE_NAME] [-c "command to run"]

Behavior:
1. Builds the Dockerfile into a Docker image (using the provided tag if given, otherwise generates one).
2. If a command is provided, runs it in a container from the built image.

Output:
- On any error (build or run), prints a detailed error report including commands executed, exit codes,
  working directories, and the full stdout/stderr from Docker.
- On success, prints only clear success statements:
    BUILD SUCCESS: Image '...' built from '...'.
    COMMAND SUCCESS: Ran in container '...': <command>
  (If no command is provided, only the BUILD SUCCESS line is printed.)

Exit codes:
- 0 on success
- non-zero on failure
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class CmdResult:
    cmd: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str


def run(cmd: list[str], cwd: Optional[str] = None, env: Optional[dict] = None) -> CmdResult:
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate()
    return CmdResult(cmd=" ".join(shlex.quote(c) for c in cmd), cwd=os.getcwd() if cwd is None else cwd, returncode=proc.returncode, stdout=out, stderr=err)


def ensure_docker_available() -> Tuple[bool, Optional[str]]:
    try:
        res = run(["docker", "version", "--format", "{{.Server.Version}}"])
        if res.returncode != 0:
            return False, format_error("docker version failed", res)
        return True, None
    except FileNotFoundError:
        return False, "ERROR: Docker CLI not found. Ensure Docker is installed and 'docker' is on PATH."


def format_error(context: str, res: CmdResult) -> str:
    lines = [
        f"ERROR during {context}",
        f"Command: {res.cmd}",
        f"CWD: {res.cwd}",
        f"Exit code: {res.returncode}",
        "----- STDOUT -----",
        res.stdout.rstrip(),
        "----- STDERR -----",
        res.stderr.rstrip(),
        "-------------------",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_image(dockerfile_path: str, tag: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    dockerfile_path = os.path.abspath(dockerfile_path)
    if not os.path.exists(dockerfile_path):
        return False, None, f"ERROR: Dockerfile does not exist: {dockerfile_path}\n"
    if not os.path.isfile(dockerfile_path):
        return False, None, f"ERROR: Path is not a regular file: {dockerfile_path}\n"

    context_dir = os.path.dirname(dockerfile_path) or "."

    # Generate a tag if not supplied
    if not tag:
        base = os.path.basename(context_dir) or "image"
        ts = time.strftime("%Y%m%d-%H%M%S")
        tag = f"gpmod/{base}:{ts}"

    # Build command
    cmd = [
        "docker", "build",
        "-t", tag,
        "-f", dockerfile_path,
        context_dir,
    ]

    try:
        res = run(cmd, cwd=context_dir)
    except FileNotFoundError:
        return False, None, "ERROR: Docker CLI not found. Ensure Docker Desktop/Engine is installed and docker is on PATH.\n"

    if res.returncode != 0:
        return False, None, format_error("docker build", res)

    return True, tag, None


def run_command(tag: str, command: str) -> Tuple[bool, Optional[str]]:
    # Run command inside a shell for broader command compatibility.
    # We set entrypoint to 'sh' to avoid image CMD/ENTRYPOINT interference.
    # Note: If the image does not include a POSIX shell, this will fail and report accordingly.
    cmd = [
        "docker", "run", "--rm", "--entrypoint", "sh", tag, "-lc", command,
    ]
    try:
        res = run(cmd)
    except FileNotFoundError:
        return False, "ERROR: Docker CLI not found. Ensure Docker Desktop/Engine is installed and docker is on PATH.\n"

    if res.returncode != 0:
        return False, format_error("docker run", res)

    return True, None


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GenePattern Dockerfile builder/linter")
    p.add_argument("dockerfile", help="Path to the Dockerfile to build")
    p.add_argument("-t", "--tag", help="Name:tag for the built image (optional)")
    p.add_argument("-c", "--cmd", help="Command to run in the built container (optional)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    ok, err = ensure_docker_available()
    if not ok:
        assert err is not None
        sys.stderr.write(err)
        return 2

    build_ok, tag, build_err = build_image(args.dockerfile, args.tag)
    if not build_ok:
        sys.stderr.write(build_err or "Unknown build error\n")
        return 1

    # Success build message printed only on full success output path. However, spec requires
    # minimal output on success, but detailed diagnostics on failure. We'll accumulate success lines
    # and print at end only when fully successful.
    success_lines = [f"BUILD SUCCESS: Image '{tag}' built from '{os.path.abspath(args.dockerfile)}'."]

    if args.cmd:
        run_ok, run_err = run_command(tag, args.cmd)
        if not run_ok:
            sys.stderr.write(run_err or "Unknown run error\n")
            return 1
        success_lines.append(f"COMMAND SUCCESS: Ran in container '{tag}': {args.cmd}")

    # Print minimal success lines and exit 0
    for line in success_lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
