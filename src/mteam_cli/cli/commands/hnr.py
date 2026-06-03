"""Hit-and-run (H&R) / crime records for a member.

This endpoint rejects the API key (無許可權) — it needs the web session JWT.
We reuse the token persisted by ``mteam-cli login``/``run`` (localStorage
snapshot). Run login first if there is no session yet.
"""

from __future__ import annotations

import argparse
import logging

from mteam_cli.api import MTeamAPIError, get_hnr, load_session
from mteam_cli.api.public import as_list
from mteam_cli.cli._account import add_account_arg, resolve_account_or_exit
from mteam_cli.cli._emit import add_format_arg, add_raw_arg, auto_fields, emit_raw, emit_rows
from mteam_cli.core.config import Settings


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "hnr", help="H&R（Hit and Run）记录。注意：M-Team 对该端点启用请求签名，CLI 不支持（网页端专用）。"
    )
    p.add_argument("--uid", default=None, help="查看指定用户（默认：自己）。")
    add_account_arg(p)
    add_format_arg(p)
    add_raw_arg(p)
    p.set_defaults(func=handle)


async def handle(
    args: argparse.Namespace, settings: Settings, logger: logging.Logger
) -> int:
    account = resolve_account_or_exit(args, settings)
    session = load_session(account.storage_path(settings.auth_dir))
    if session is None:
        print(
            f"该端点需要登录会话。请先运行 `mteam-cli login --account {account.username}`，"
            "再执行本命令。"
        )
        return 1

    uid = args.uid or session.uid
    if not uid:
        print("无法确定 uid（会话未携带，且未指定 --uid）。")
        return 1

    try:
        data = await get_hnr(
            uid,
            base_url=settings.api_base_url,
            auth_token=session.auth_token,
            did=session.did,
            visitorid=session.visitorid,
        )
    except MTeamAPIError as exc:
        print(f"错误: {exc}")
        return 1

    if args.raw:
        emit_raw(data)
        return 0

    rows = as_list(data)
    if not rows:
        print("无 H&R 记录。")
        return 0
    emit_rows(rows, auto_fields(rows), fmt=args.output_format)
    return 0
