from __future__ import annotations

import httpx

from llmx_advocate.settings import get_settings


def get_client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(base_url=settings.llmx_api_base_url, timeout=300.0)


class APIError(Exception):
    pass


def call(method: str, path: str, **kwargs) -> dict | list:
    """Thin sync wrapper for CLI commands. Re-raises HTTP errors with the API's detail message."""
    with get_client() as c:
        try:
            r = c.request(method, path, **kwargs)
            r.raise_for_status()
        except httpx.ConnectError as e:
            raise APIError(
                f"cannot reach API at {get_settings().llmx_api_base_url} — is it running?\n"
                f"Start it with: docker compose up -d api  (or: uvicorn llmx_advocate.api.main:app)"
            ) from e
        except httpx.HTTPStatusError as e:
            detail = _extract_detail(e.response)
            raise APIError(f"API {e.response.status_code}: {detail}") from e
        return r.json()


def _extract_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except (ValueError, httpx.DecodingError):
        return response.text
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])
    return str(body)
