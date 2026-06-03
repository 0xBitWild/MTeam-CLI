"""Account profile + counters (uploaded/downloaded/bonus/share-ratio)."""

from __future__ import annotations

import argparse
import logging
from typing import Any

from mteam_cli.api import MTeamAPIError, get_profile
from mteam_cli.api import humanize as hz
from mteam_cli.cli._account import add_account_arg, require_query, resolve_account_or_exit
from mteam_cli.cli._emit import Field, add_format_arg, add_raw_arg, emit_raw, emit_record
from mteam_cli.core.config import Settings

_FIELDS = [
    Field("id", "用户ID"),
    Field("username", "用户名"),
    Field("email", "Email"),
    Field("ip", "登录IP"),
    Field("uploaded", "上传量"),
    Field("downloaded", "下载量"),
    Field("bonus", "魔力值"),
    Field("shareRate", "分享率"),
    Field("lastLogin", "最近登录"),
    Field("lastBrowse", "最近浏览"),
    Field("createdDate", "注册时间"),
]


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("profile", help="账户详情与统计（上传/下载/魔力/分享率）。")
    p.add_argument("--uid", default=None, help="查看指定用户的 profile（默认：自己）。")
    add_account_arg(p)
    add_format_arg(p)
    add_raw_arg(p)
    p.set_defaults(func=handle)


async def handle(
    args: argparse.Namespace, settings: Settings, logger: logging.Logger
) -> int:
    account = resolve_account_or_exit(args, settings)
    require_query(account)
    try:
        data = await get_profile(account.api_key, base_url=settings.api_base_url, uid=args.uid)
    except MTeamAPIError as exc:
        print(f"错误: {exc}")
        return 1
    if not data:
        print("未获取到 profile 数据。")
        return 1

    if args.raw:
        emit_raw(data)
        return 0

    record = _shape(data)
    emit_record(record, _FIELDS, fmt=args.output_format)
    return 0


def _shape(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten the nested profile payload into one record for emit."""
    status = data.get("memberStatus") or {}
    count = data.get("memberCount") or {}
    return {
        "id": data.get("id"),
        "username": data.get("username"),
        "email": data.get("email"),
        "ip": data.get("ip"),
        "uploaded": hz.naturalsize(count.get("uploaded")),
        "downloaded": hz.naturalsize(count.get("downloaded")),
        "bonus": hz.num(count.get("bonus")),
        "shareRate": hz.ratio(count.get("shareRate")),
        "lastLogin": status.get("lastLogin"),
        "lastBrowse": status.get("lastBrowse"),
        "createdDate": data.get("createdDate"),
    }
