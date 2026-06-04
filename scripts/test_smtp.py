#!/usr/bin/env python3
r"""SMTP 发送测试 —— 隔离不同 API 组合，定位 QQ 邮箱报错根源。

测试 4 种发送方式，每种都单独捕错，输出明确的结果：

  A) MIMEText          + 显示名 From + 无显式 from/to
  B) MIMEText          + 裸 From     + 无显式 from/to
  C) EmailMessage      + 裸 From     + 无显式 from/to
  D) EmailMessage      + 裸 From     + 显式 from_addr/to_addrs

用法：
    source .venv/bin/activate && python scripts/test_smtp.py
"""

import asyncio
import logging
import smtplib
import sys
from email.message import EmailMessage
from email.mime.text import MIMEText

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test_smtp")


def _conf():
    """Read SMTP config directly from .env — no mteam_cli dependency needed
    (keeps the test self-contained, no accidental package re-import)."""
    from dotenv import load_dotenv
    import os

    load_dotenv()
    cfg = {
        "host": os.getenv("NOTIFY_SMTP_HOST", "").strip(),
        "port": int(os.getenv("NOTIFY_SMTP_PORT", "465")),
        "user": os.getenv("NOTIFY_SMTP_USER", "").strip(),
        "password": os.getenv("NOTIFY_SMTP_PASSWORD", ""),
        "sender": os.getenv("NOTIFY_SMTP_FROM", "").strip(),
        # use account 1's SMTP_TO as test recipient
        "to": os.getenv("NOTIFY_SMTP_TO_1") or os.getenv("NOTIFY_EMAIL_1") or os.getenv("NOTIFY_EMAIL") or "",
    }
    cfg["to"] = cfg["to"].strip()
    if not cfg["host"] or not cfg["sender"] or not cfg["to"]:
        logger.error("SMTP 未配置（NOTIFY_SMTP_HOST / _FROM / _TO_1 至少一项缺失）")
        sys.exit(1)
    logger.info(
        "连接: %s:%s  user=%s  from=%s  to=%s",
        cfg["host"], cfg["port"], cfg["user"], cfg["sender"], cfg["to"],
    )
    return cfg


BODY = "MTeam-CLI SMTP 测试邮件 —— 如果你能收到，说明该 API 组合正常。"


def _client(cfg):
    return (
        smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15)
        if cfg["port"] == 465
        else smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
    )


# ── 四组独立测试 ──────────────────────────────────────────────


def test_a_mimetext_with_display(cfg) -> bool:
    """A) MIMEText + 显示名 From + send_message() 无显式参数"""
    msg = MIMEText(BODY)
    msg["Subject"] = "[A] MIMEText + 显示名"
    msg["From"] = f"MTeam-CLI <{cfg['sender']}>"
    msg["To"] = cfg["to"]
    with _client(cfg) as c:
        c.login(cfg["user"], cfg["password"])
        c.send_message(msg)
    return True


def test_b_mimetext_bare(cfg) -> bool:
    """B) MIMEText + 裸 From + send_message() 无显式参数"""
    msg = MIMEText(BODY)
    msg["Subject"] = "[B] MIMEText + 裸From"
    msg["From"] = cfg["sender"]
    msg["To"] = cfg["to"]
    with _client(cfg) as c:
        c.login(cfg["user"], cfg["password"])
        c.send_message(msg)
    return True


def test_c_emailmessage_bare(cfg) -> bool:
    """C) EmailMessage + set_content + 裸 From + send_message() 无显式参数"""
    msg = EmailMessage()
    msg["Subject"] = "[C] EmailMessage + 裸From"
    msg["From"] = cfg["sender"]
    msg["To"] = cfg["to"]
    msg.set_content(BODY)
    with _client(cfg) as c:
        c.login(cfg["user"], cfg["password"])
        c.send_message(msg)
    return True


def test_d_emailmessage_explicit(cfg) -> bool:
    """D) EmailMessage + set_content + 裸 From + 显式 from_addr/to_addrs"""
    msg = EmailMessage()
    msg["Subject"] = "[D] EmailMessage + 显式from/to"
    msg["From"] = cfg["sender"]
    msg["To"] = cfg["to"]
    msg.set_content(BODY)
    with _client(cfg) as c:
        c.login(cfg["user"], cfg["password"])
        c.send_message(msg, from_addr=cfg["sender"], to_addrs=[cfg["to"]])
    return True


# ── 发送 profile 正文（最接近生产场景）────────────────────────


def test_real_body(cfg) -> bool:
    """用真实 keep-alive 通知正文（含 profile 完整转储）测试。

    旧 A 通过 → 正文不是问题；旧 A 也挂 → 正文是 550 触发器。
    """
    real_body = (
        "riddd 保活签到成功。\n\n"
        "用户ID: 278577\n"
        "用户名: riddd\n"
        "用户Email: ridddzl@gmail.com\n"
        "登录IP: 171.15.221.46\n"
        "账户创建时间: 2022-10-02 23:01:17\n"
        "会员最新登录时间: 2026-06-04 09:22:24\n"
        "会员最新浏览时间: 2026-06-04 09:22:24\n"
        "上传量: 20.4 TiB\n"
        "下载量: 5.6 TiB\n"
        "魔力值: 1631.7\n"
        "分享率: 3.633\n"
    )
    msg = MIMEText(real_body)
    msg["Subject"] = "[prod] MTeam-CLI 保活成功"
    msg["From"] = f"MTeam-CLI <{cfg['sender']}>"
    msg["To"] = cfg["to"]
    with _client(cfg) as c:
        c.login(cfg["user"], cfg["password"])
        c.send_message(msg)
    return True


# ── runner ────────────────────────────────────────────────────


async def main() -> None:
    cfg = _conf()
    tests = [
        ("A) MIMEText + 显示名", test_a_mimetext_with_display),
        ("B) MIMEText + 裸From", test_b_mimetext_bare),
        ("C) EmailMessage + 裸From", test_c_emailmessage_bare),
        ("D) EmailMessage + 显式from/to", test_d_emailmessage_explicit),
    ]

    results = {}
    for label, fn in tests:
        try:
            await asyncio.to_thread(fn, cfg)
            logger.info("  [%s] ✅ 发送成功", label[:2])
            results[label[:2]] = True
        except Exception as exc:
            logger.warning("  [%s] ❌ %s", label[:2], exc)
            results[label[:2]] = False

    # 真实正文测试 —— 只在 A 通过时才跑（避免白挨 QQ 限制）
    label = "[prod] 真实正文"
    try:
        await asyncio.to_thread(test_real_body, cfg)
        logger.info("  %s ✅ 发送成功", label)
        results[label] = True
    except Exception as exc:
        logger.warning("  %s ❌ %s", label, exc)
        results[label] = False

    print("\n=== 结果汇总 ===")
    for k, ok in results.items():
        print(f"  {k}: {'✅ 通过' if ok else '❌ 失败'}")

    # 推荐
    passed = [k for k, ok in results.items() if ok]
    if passed:
        print(f"\n可用的 API 组合: {', '.join(passed)}")
        if "A" in results and results["A"] and "[prod]" in results and results["[prod]"]:
            print("→ A) MIMEText + 显示名 对真实正文也通过，直接用它。")
    else:
        print("\n⚠ 全部失败 — 检查 Credential 或网络。")


if __name__ == "__main__":
    asyncio.run(main())
