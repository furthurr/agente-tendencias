"""Cliente HTTP pequeño y compartido para las fuentes públicas.

La infraestructura está aislada aquí para que los colectores no dupliquen
User-Agent, timeout, reintentos ni manejo de rate limits.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)


class HttpError(RuntimeError):
    """Error de transporte, estado HTTP o decodificación de una respuesta."""

    def __init__(self, message: str, *, url: str = "", status_code: int | None = None):
        super().__init__(message)
        self.url = url
        self.status_code = status_code


@dataclass
class HttpClient:
    """Cliente configurable; se crea una única instancia en el composition root."""

    user_agent: str
    timeout: float = 25.0
    retries: int = 2
    backoff_initial: float = 1.0
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
            }
        )

    def _request(self, url: str, *, params: dict[str, Any] | None = None) -> requests.Response:
        assert self.session is not None
        attempts = max(0, self.retries) + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                retryable = response.status_code == 429 or response.status_code >= 500
                if response.ok:
                    return response
                if not retryable or attempt == attempts - 1:
                    raise HttpError(
                        f"HTTP {response.status_code} en {response.url}",
                        url=response.url,
                        status_code=response.status_code,
                    )
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else self.backoff_initial * (2**attempt)
                LOGGER.warning("Rate limit/servidor en %s; reintento en %.1fs", response.url, delay)
                time.sleep(delay)
            except requests.RequestException as exc:
                last_error = exc
                if attempt == attempts - 1:
                    break
                delay = self.backoff_initial * (2**attempt)
                LOGGER.warning("Error HTTP en %s (%s); reintento en %.1fs", url, exc, delay)
                time.sleep(delay)

        raise HttpError(f"No se pudo obtener {url}: {last_error}", url=url) from last_error

    def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._request(url, params=params)
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise HttpError(f"JSON inválido en {response.url}", url=response.url, status_code=response.status_code) from exc

    def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str:
        response = self._request(url, params=params)
        return response.text


def guardar_crudo(path: str | Path, payload: Any, *, texto: bool = False) -> None:
    """Persiste una respuesta cruda sin introducir secretos en el contenido."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if texto:
        target.write_text(str(payload), encoding="utf-8")
        return
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
