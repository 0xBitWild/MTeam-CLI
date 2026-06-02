"""Shared HTTP plumbing for the M-Team data API.

Transport: the official ``api.m-team.io`` API, authenticated with an
``x-api-key`` header (generated in the M-Team control panel). Pure urllib in a
thread pool — zero browser, zero extra deps — so data commands stay light and
usable even where Chromium is not installed.

Verified against the M-Team OpenAPI spec (``/api/v3/api-docs``) + a live test
server probe:
  * every endpoint is **POST**;
  * some take **query parameters** (``uid`` / ``id``), others a **JSON body**;
  * responses wrap data in ``{code, message, data}`` where ``code == 0``
    (integer) means success; non-zero is an error (``"key無效"`` ⇒ bad key).
The transport (POST + ``x-api-key`` + JSON content-type) was confirmed accepted
by the server. Everything endpoint-specific lives here or in ``public.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MTEAM_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_SUCCESS_CODES = {"0", "200"}
_AUTH_CODES = {"401", "403"}
# Substrings in the API ``message`` that indicate an auth/permission problem.
# Includes endpoints the API key can't reach (need a full web session): these
# return "Full authentication is required" / "無許可權" / 401.
_AUTH_HINTS = (
    "key無效", "key无效", "key invalid",
    "未登", "登入", "登录", "鉴权", "鑒權",
    "權限", "权限", "許可權", "许可权",
    "authentication", "permission", "unauthor",
)

logger = logging.getLogger("mteam_cli.api")


class MTeamAPIError(Exception):
    """Raised when the M-Team API returns an error or unexpected response."""


class MTeamAuthError(MTeamAPIError):
    """Raised when the API key is missing, invalid, or expired."""


async def api_post(
    path: str,
    *,
    api_key: str,
    base_url: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    form: dict[str, Any] | None = None,
    timeout: int = 20,
) -> Any:
    """POST ``{base_url}{path}`` with ``x-api-key`` and return the ``data`` field.

    Body encoding (pick one to match the endpoint):
      * ``params`` → query string (``/member/profile?uid=``, ``/member/getCrimeRecords?uid=``)
      * ``form``   → ``application/x-www-form-urlencoded`` (``/torrent/detail``, ``/torrent/genDlToken``)
      * ``body``   → JSON (``/torrent/search``, ``/member/getUserTorrentList``)
    ``params`` may combine with either body form.

    Raises ``MTeamAuthError`` on auth failure (HTTP 401/403 or an auth code /
    message), ``MTeamAPIError`` on any other non-success response.
    """
    url = f"{base_url}{path}"
    if params:
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean:
            url = f"{url}?{urlencode(clean)}"

    headers = {
        "x-api-key": api_key,
        "User-Agent": MTEAM_UA,
        "Accept": "application/json",
    }
    if form is not None:
        data = urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    else:
        data = json.dumps(body or {}).encode("utf-8")
        headers["Content-Type"] = "application/json"

    def _sync() -> Any:
        req = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise MTeamAuthError(
                    "M-Team API key 无效或已过期，请检查 MTEAM_API_KEY_<n>。"
                ) from exc
            raise MTeamAPIError(f"M-Team API 返回 HTTP {exc.code}（{path}）") from exc
        except URLError as exc:
            raise MTeamAPIError(f"网络错误，无法访问 {url}: {exc.reason}") from exc

        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MTeamAPIError(f"{path} 返回了非 JSON 响应: {exc}") from exc

        return _unwrap(payload, path)

    return await asyncio.to_thread(_sync)


def _unwrap(payload: Any, path: str) -> Any:
    """Validate the ``{code, message, data}`` envelope and return ``data``."""
    if not isinstance(payload, dict):
        return payload

    code = payload.get("code")
    code_str = str(code) if code is not None else None
    message = str(payload.get("message", ""))

    if code_str is None:
        return payload.get("data", payload)

    if code_str in _SUCCESS_CODES:
        return payload.get("data")

    # Non-success: classify auth/permission vs generic.
    msg_lower = message.lower()
    if code_str in _AUTH_CODES or any(h.lower() in msg_lower for h in _AUTH_HINTS):
        raise MTeamAuthError(
            f"M-Team API 鉴权/权限不足 (code={code_str}): {message}。"
            f"该端点可能需要完整登录会话，API key 不支持 [{path}]"
        )

    raise MTeamAPIError(f"M-Team API 错误 (code={code_str}): {message} [{path}]")
