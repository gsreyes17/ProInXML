"""Configuracion local, compartida por API, scripts y worker."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    worker_concurrency: int = int(os.getenv("WORKER_CONCURRENCY", "8"))
    poll_seconds: float = float(os.getenv("WORKER_POLL_SECONDS", "5"))
    max_xml_bytes: int = int(os.getenv("MAX_XML_BYTES", "33554432"))
    circuit_failures: int = int(os.getenv("MEF_CIRCUIT_FAILURES", "5"))
    circuit_pause_seconds: int = int(os.getenv("MEF_CIRCUIT_PAUSE_SECONDS", "30"))
    session_seconds: int = int(os.getenv("SESSION_SECONDS", "28800"))
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "no").lower() == "yes"

    def __post_init__(self):
        if not 1 <= self.worker_concurrency <= 20:
            raise ValueError("WORKER_CONCURRENCY debe estar entre 1 y 20.")
        if (
            min(
                self.poll_seconds,
                self.max_xml_bytes,
                self.circuit_failures,
                self.circuit_pause_seconds,
                self.session_seconds,
            )
            <= 0
        ):
            raise ValueError("Los limites y tiempos deben ser positivos.")


settings = Settings()
