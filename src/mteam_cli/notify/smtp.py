"""SMTP email notifier — stdlib smtplib + email.message.EmailMessage.

Follows the Weread-CLI pattern (proven working with QQ SMTP): modern
``EmailMessage`` + ``set_content()`` for clean UTF-8 encoding; bare sender
address on the envelope so QQ's strict auth check passes. Recipients are
fixed at construction time (per-account).
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage

from mteam_cli.notify.base import Notification

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SMTPNotifier:
    host: str
    port: int
    user: str
    password: str
    sender: str
    recipients: list[str] = field(default_factory=list)
    use_tls: bool = True
    name: str = "smtp"
    timeout_seconds: int = 30

    async def send(self, n: Notification) -> None:
        if not self.recipients:
            logger.info("SMTP: 无收件人，跳过。")
            return
        await asyncio.to_thread(self._sync_send, n)

    def _sync_send(self, n: Notification) -> None:
        msg = EmailMessage()
        msg["Subject"] = n.title
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.set_content(n.body)

        client_cls = smtplib.SMTP_SSL if self.port == 465 else smtplib.SMTP
        with client_cls(self.host, self.port, timeout=self.timeout_seconds) as client:
            if self.use_tls and self.port != 465:
                client.starttls()
            if self.user:
                client.login(self.user, self.password)
            client.send_message(msg)
        logger.info("SMTP 邮件已发送至 %s", ", ".join(self.recipients))
