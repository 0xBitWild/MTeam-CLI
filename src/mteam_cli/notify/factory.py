"""Build a per-account NotifierHub — each channel opts in via that account's
own notify config. There is no global notifier."""

from __future__ import annotations

import logging

from mteam_cli.core.config import Account
from mteam_cli.notify.base import Notifier, NotifierHub
from mteam_cli.notify.feishu import FeishuNotifier
from mteam_cli.notify.smtp import SMTPNotifier
from mteam_cli.notify.telegram import TelegramNotifier


def build_notifier_hub(account: Account, logger: logging.Logger) -> NotifierHub:
    notifiers: list[Notifier] = []

    if account.has_telegram:
        notifiers.append(
            TelegramNotifier(
                token=account.telegram_token,
                chat_id=account.telegram_chat_id,
            )
        )

    if account.has_smtp:
        recipients = [r.strip() for r in (account.smtp_to or "").split(",") if r.strip()]
        notifiers.append(
            SMTPNotifier(
                host=account.smtp_host,
                port=account.smtp_port,
                user=account.smtp_user or "",
                password=account.smtp_password or "",
                sender=account.smtp_from,
                recipients=recipients,
                use_tls=account.smtp_use_tls,
            )
        )

    if account.has_feishu:
        notifiers.append(FeishuNotifier(token=account.feishu_token))

    hub = NotifierHub(notifiers, logger)
    if notifiers:
        logger.info("[%s] Notifiers enabled: %s", account.username, ", ".join(hub.enabled_names))
    else:
        logger.info("[%s] 无通知渠道（设置该账户的 NOTIFY_*_<n> 以启用）", account.username)
    return hub
