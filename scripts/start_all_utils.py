"""Utility helpers for start_all runner."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import threading
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class Redactor(logging.Filter):
    _token_pattern = re.compile(r"bot\d+:[A-Za-z0-9_-]+")

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = [secret for secret in secrets if secret]

    def _redact(self, text: str) -> str:
        redacted = self._token_pattern.sub("bot<redacted>", text)
        for secret in self._secrets:
            redacted = redacted.replace(secret, "<redacted>")
        return redacted

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            record.args = tuple(self._redact(str(arg)) for arg in record.args)
        return True


def configure_logging(name: str, redactor: Redactor) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(asctime)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(redactor)
    return logging.getLogger(name)


def load_env_file(env_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and value[0] in {'"', "'"} and value[-1] == value[0]:
            value = value[1:-1]
        env[key] = value
    return env


def resolve_binary(name: str, fallback: Path | None = None) -> Path | None:
    found = shutil.which(name)
    if found:
        return Path(found)
    if fallback and fallback.exists():
        return fallback
    return None


def check_health(url: str, username: str, password: str) -> bool:
    request = Request(url)
    if password:
        token = f"{username}:{password}".encode("utf-8")
        auth = base64.b64encode(token).decode("utf-8")
        request.add_header("Authorization", f"Basic {auth}")
    try:
        with urlopen(request, timeout=2) as response:
            payload = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError):
        return False
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return False
    return data.get("healthy") is True


def check_public_dns(host: str) -> bool:
    dig = shutil.which("dig")
    if dig:
        resolvers = ["1.1.1.1", "8.8.8.8"]
        record_types = ["A", "AAAA"]
        for resolver in resolvers:
            for record_type in record_types:
                try:
                    output = subprocess.check_output(
                        [dig, "+short", f"@{resolver}", host, record_type],
                        text=True,
                    )
                except Exception:
                    continue
                if output.strip():
                    return True
        return False
    try:
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        return False


def stream_output(
    stream: Iterable[str],
    logger: logging.Logger,
    level: int,
    prefix: str,
) -> None:
    for line in stream:
        message = line.rstrip("\n")
        if message:
            logger.log(level, f"{prefix} {message}")


def start_process(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    logger: logging.Logger,
    name: str,
    combine_stderr: bool = False,
) -> tuple[subprocess.Popen[str], list[threading.Thread]]:
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if combine_stderr else subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    threads: list[threading.Thread] = []
    if process.stdout is not None:
        thread = threading.Thread(
            target=stream_output,
            args=(process.stdout, logger, logging.INFO, name),
            daemon=True,
        )
        thread.start()
        threads.append(thread)
    if not combine_stderr and process.stderr is not None:
        thread = threading.Thread(
            target=stream_output,
            args=(process.stderr, logger, logging.ERROR, name),
            daemon=True,
        )
        thread.start()
        threads.append(thread)
    return process, threads


def wait_process(process: subprocess.Popen[str], threads: list[threading.Thread]) -> int:
    returncode = process.wait()
    for thread in threads:
        thread.join(timeout=1)
    return returncode


def terminate_process(
    process: subprocess.Popen[str] | None,
    threads: list[threading.Thread],
    logger: logging.Logger,
    name: str,
) -> None:
    if not process or process.poll() is not None:
        return
    logger.info("Stopping %s", name)
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=1)
