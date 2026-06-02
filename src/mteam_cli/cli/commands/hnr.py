"""Hit-and-run (H&R) / crime records for a member (API key).

Endpoint: POST /member/getCrimeRecords?uid=. Resolves own uid first unless
--uid is given. Columns are auto-derived until the shape is curated.
"""

from __future__ import annotations

import argparse
import logging

from mteam_cli.api import MTeamAPIError, get_hnr, get_own_uid
from mteam_cli.api.public import as_list
from mteam_cli.cli._account import add_account_arg, require_query, resolve_account_or_exit
from mteam_cli.cli._emit import add_format_arg, auto_fields, emit_rows
from mteam_cli.core.config import Settings


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "hnr", help="H&R（Hit and Run）记录。注意：可能需要会话/权限，API key 未必支持。"
    )
    p.add_argument("--uid", default=None, help="查看指定用户（默认：自己）。")
    add_account_arg(p)
    add_format_arg(p)
    p.set_defaults(func=handle)


async def handle(
    args: argparse.Namespace, settings: Settings, logger: logging.Logger
) -> int:
    account = resolve_account_or_exit(args, settings)
    require_query(account)
    base = settings.api_base_url
    try:
        uid = args.uid or await get_own_uid(account.api_key, base_url=base)
        data = await get_hnr(account.api_key, uid, base_url=base)
    except MTeamAPIError as exc:
        print(f"错误: {exc}")
        return 1

    rows = as_list(data)
    if not rows:
        print("无 H&R 记录。")
        return 0
    emit_rows(rows, auto_fields(rows), fmt=args.output_format)
    return 0
