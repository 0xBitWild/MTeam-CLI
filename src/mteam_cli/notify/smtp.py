"""SMTP email notifier — stdlib smtplib + MIMEText.

From header is ``"MTeam-CLI <{sender}>"`` — sender is expected to be a plain
email address (e.g. ``user@foxmail.com``). If sender already carries a display
name, the double-wrapping produces a syntactically invalid header that smtplib
can't parse into a clean envelope address, and QQ/Foxmail SMTP returns
``502 Invalid paramenters``. Keep NOTIFY_SMTP_FROM as a bare address.

This is the legacy script's proven pattern — MIMEText with a single-layer
display-name From header. It has worked with QQ/Foxmail SMTP for years.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from dataclasses import dataclass, field
from email.mime.text import MIMEText

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
        msg = MIMEText(n.body)
        msg["Subject"] = n.title
        msg["From"] = f"MTeam-CLI <{self.sender}>"
        msg["To"] = ", ".join(self.recipients)

        client_cls = smtplib.SMTP_SSL if self.port == 465 else smtplib.SMTP
        with client_cls(self.host, self.port, timeout=self.timeout_seconds) as client:
            if self.use_tls and self.port != 465:
                client.starttls()
            if self.user:
                client.login(self.user, self.password)
            client.send_message(msg)
        logger.info("SMTP 邮件已发送至 %s", ", ".join(self.recipients))
