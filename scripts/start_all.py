#!/usr/bin/env python3
"""Start OpenCode server, Tailscale Funnel, and Jarvis with one command."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from typing import Iterable

from start_all_utils import (
    Redactor,
    check_health,
    check_public_dns,
    configure_logging,
    load_env_file,
    resolve_binary,
    start_process,
    terminate_process,
    wait_process,
)

LOG_NAME = "start-all"
DEFAULT_OPENCODE_URL = "http://localhost:4096"
DEFAULT_WEBHOOK_PORT = "8080"
HEALTH_RETRIES = 60
DNS_RETRIES = 60
FUNNEL_RETRIES = 40


def health_url(opencode_url: str) -> str:
    return opencode_url.rstrip("/") + "/global/health"


def health_url_ipv4(opencode_url: str) -> str:
    parsed = urlparse(opencode_url)
    if parsed.hostname == "localhost":
        parsed = parsed._replace(netloc=f"127.0.0.1:{parsed.port or 4096}")
    return urlunparse(parsed).rstrip("/") + "/global/health"


def main() -> int:
    jarvis_dir = Path(__file__).resolve().parents[1]
    projects_dir = jarvis_dir.parent
    env_path = jarvis_dir / ".env"
    if not env_path.exists():
        print(f"Missing .env at {env_path}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    for key, value in load_env_file(env_path).items():
        if key not in env:
            env[key] = value
    env["PYTHONUNBUFFERED"] = "1"

    secrets = [
        env.get("OPENCODE_SERVER_PASSWORD", ""),
        env.get("OPENCODE_ZEN_API_KEY", ""),
        env.get("TELEGRAM_BOT_ID", ""),
        env.get("TELEGRAM_BOT_TOKEN", ""),
    ]
    logger = configure_logging(LOG_NAME, Redactor(secrets))

    opencode_url = env.get("OPENCODE_URL", DEFAULT_OPENCODE_URL)
    opencode_user = env.get("OPENCODE_SERVER_USERNAME", "opencode")
    opencode_password = env.get("OPENCODE_SERVER_PASSWORD", "")
    telegram_webhook_url = env.get("TELEGRAM_WEBHOOK_URL", "")
    telegram_webhook_port = env.get("TELEGRAM_WEBHOOK_PORT", DEFAULT_WEBHOOK_PORT)

    if not telegram_webhook_url:
        logger.error("TELEGRAM_WEBHOOK_URL is not set")
        return 1

    webhook_host = urlparse(telegram_webhook_url).hostname
    if not webhook_host:
        logger.error("Could not parse host from TELEGRAM_WEBHOOK_URL")
        return 1

    opencode_bin = resolve_binary(
        "opencode",
        fallback=Path.home() / ".opencode" / "bin" / "opencode",
    )
    pdm_bin = resolve_binary("pdm", fallback=Path("/opt/homebrew/bin/pdm"))
    tailscale_bin = resolve_binary(
        "tailscale",
        fallback=Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale"),
    )

    if not opencode_bin:
        logger.error("OpenCode binary not found")
        return 1
    if not pdm_bin:
        logger.error("PDM binary not found")
        return 1
    if not tailscale_bin:
        logger.error("Tailscale binary not found")
        return 1

    logger.info("Installing dependencies with PDM")
    pdm_proc, pdm_threads = start_process(
        [str(pdm_bin), "install"],
        cwd=jarvis_dir,
        env=env,
        logger=logger,
        name="pdm",
    )
    if wait_process(pdm_proc, pdm_threads) != 0:
        logger.error("PDM install failed")
        return 1

    current_health_url = health_url(opencode_url)
    current_health_url_ipv4 = health_url_ipv4(opencode_url)
    opencode_proc = None
    opencode_threads: list[threading.Thread] = []
    if check_health(current_health_url_ipv4, opencode_user, opencode_password):
        logger.info("OpenCode already healthy at %s", current_health_url)
    else:
        logger.info("Starting OpenCode server")
        port = urlparse(opencode_url).port or 4096
        opencode_proc, opencode_threads = start_process(
            [str(opencode_bin), "serve", "--port", str(port)],
            cwd=projects_dir,
            env=env,
            logger=logger,
            name="opencode",
        )
        ready = False
        for _ in range(HEALTH_RETRIES):
            if check_health(current_health_url_ipv4, opencode_user, opencode_password):
                ready = True
                break
            time.sleep(1)
        if not ready:
            logger.error("OpenCode server did not become healthy at %s", current_health_url_ipv4)
            terminate_process(opencode_proc, opencode_threads, logger, "opencode")
            return 1

    logger.info("OpenCode healthy - verify providers loaded at %s", current_health_url)
    logger.info("Config locations: OPENCODE_HOME=%s, XDG_CONFIG_HOME=%s", 
                env.get("OPENCODE_HOME", "default"), 
                env.get("XDG_CONFIG_HOME", "default"))

    funnel_ready = threading.Event()
    funnel_not_enabled = threading.Event()
    funnel_enable_url: list[str] = []

    def monitor_funnel_output(stream: Iterable[str]) -> None:
        enable_pattern = re.compile(r"https://login\.tailscale\.com/\S+")
        for line in stream:
            message = str(line).rstrip("\n")
            if message:
                logger.info("funnel %s", message)
            if "Funnel is not enabled on your tailnet." in message:
                funnel_not_enabled.set()
            match = enable_pattern.search(message)
            if match:
                funnel_enable_url[:] = [match.group(0)]
            if "Available on the internet:" in message:
                funnel_ready.set()

    logger.info("Starting Tailscale Funnel")
    funnel_proc = subprocess.Popen(
        [str(tailscale_bin), "funnel", str(telegram_webhook_port)],
        cwd=str(jarvis_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    funnel_thread = threading.Thread(
        target=monitor_funnel_output,
        args=(funnel_proc.stdout or [],),
        daemon=True,
    )
    funnel_thread.start()
    funnel_threads = [funnel_thread]

    for _ in range(FUNNEL_RETRIES):
        if funnel_not_enabled.is_set():
            logger.error("Funnel is not enabled on your tailnet")
            if funnel_enable_url:
                logger.error("Enable Funnel here: %s", funnel_enable_url[0])
            terminate_process(funnel_proc, funnel_threads, logger, "funnel")
            terminate_process(opencode_proc, opencode_threads, logger, "opencode")
            return 1
        if funnel_ready.is_set():
            break
        time.sleep(0.5)

    if not funnel_ready.is_set():
        logger.error("Funnel did not become ready")
        terminate_process(funnel_proc, funnel_threads, logger, "funnel")
        terminate_process(opencode_proc, opencode_threads, logger, "opencode")
        return 1

    dns_ready = False
    for _ in range(DNS_RETRIES):
        if check_public_dns(webhook_host):
            dns_ready = True
            break
        time.sleep(1)

    if not dns_ready:
        logger.error("Webhook host did not resolve publicly: %s", webhook_host)
        terminate_process(funnel_proc, funnel_threads, logger, "funnel")
        terminate_process(opencode_proc, opencode_threads, logger, "opencode")
        return 1

    logger.info("Starting Jarvis")
    jarvis_proc, jarvis_threads = start_process(
        [str(pdm_bin), "run", "python", "-m", "jarvis"],
        cwd=jarvis_dir,
        env=env,
        logger=logger,
        name="jarvis",
    )

    def handle_signal(signum: int, frame: object) -> None:
        logger.info("Received signal %s", signum)
        terminate_process(jarvis_proc, jarvis_threads, logger, "jarvis")
        terminate_process(funnel_proc, funnel_threads, logger, "funnel")
        terminate_process(opencode_proc, opencode_threads, logger, "opencode")
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    returncode = wait_process(jarvis_proc, jarvis_threads)
    if returncode != 0:
        logger.error("Jarvis exited with code %s", returncode)
    terminate_process(funnel_proc, funnel_threads, logger, "funnel")
    terminate_process(opencode_proc, opencode_threads, logger, "opencode")
    return returncode


if __name__ == "__main__":
    sys.exit(main())
