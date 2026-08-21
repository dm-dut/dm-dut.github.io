"""
Send Paper Monitor HTML digest email.

Required environment variables:
MAIL_USERNAME
MAIL_PASSWORD
MAIL_TO

The program skips sending when no email HTML exists.
"""

import os
import smtplib

from pathlib import Path
from email.message import EmailMessage
from email.utils import formataddr

ROOT = Path(__file__).resolve().parent.parent
HTML_FILE = ROOT / "web" / "daily_papers_email.html"

if not HTML_FILE.exists():
    print("No email digest found. Skip sending.")
    raise SystemExit(0)


username = "zhenzhang_cn@ieee.org"
password = "zicjxpvrcvkxrtso"
receiver = "zhen.zhang.dut@vip.163.com"

if not username or not password or not receiver:
    raise RuntimeError(
        "Missing MAIL_USERNAME, MAIL_PASSWORD or MAIL_TO"
    )

html = HTML_FILE.read_text(encoding="utf-8")

msg = EmailMessage()
msg["Subject"] = "[Paper Monitor] Daily New Papers"
msg["From"] = formataddr(
    ("Paper Monitor", username)
)
msg["To"] = receiver

msg.set_content(
    "Please view this email in HTML format."
)

msg.add_alternative(
    html,
    subtype="html"
)

with smtplib.SMTP_SSL(
    "smtp.gmail.com",
    465
) as smtp:
    smtp.login(username, password)
    smtp.send_message(msg)

print("Email sent successfully.")
