"""Inbox / private messages (API key).

⚠ PROBE-VERIFY: columns are auto-derived from the response until the endpoint
shape is confirmed.
"""

from __future__ import annotations

import argparse
import logging

from mteam_cli.api import MTeamAPIError, get_messages
from mteam_cli.api.public import as_list
from mteam_cli.cli._account import add_account_arg, require_query, resolve_account_or_exit
from mteam_cli.cli._emit import add_format_arg, auto_fields, emit_rows
from mteam_cli.core.config import Settings


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "messages", help="站内信（收件箱）。注意：M-Team 该端点需完整登录会话，API key 通常不支持。"
    )
    p.add_argument("-n", "--limit", type=int, default=20, help="每页数量 (默认: 20)")
    p.add_argument("--page", type=int, default=1, help="页码 (默认: 1)")
    p.add_argument("--box", type=int, default=None, help="信箱 ID（默认：全部）。")
    add_account_arg(p)
    add_format_arg(p)
    p.set_defaults(func=handle)


async def handle(
    args: argparse.Namespace, settings: Settings, logger: logging.Logger
) -> int:
    account = resolve_account_or_exit(args, settings)
    require_query(account)
    try:
        data = await get_messages(
            account.api_key,
            base_url=settings.api_base_url,
            box_id=args.box,
            page_number=args.page,
            page_size=args.limit,
        )
    except MTeamAPIError as exc:
        print(f"错误: {exc}")
        return 1

    rows = as_list(data)
    if not rows:
        print("无站内信。")
        return 0
    emit_rows(rows, auto_fields(rows), fmt=args.output_format)
    return 0
