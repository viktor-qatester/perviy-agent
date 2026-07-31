"""Email notifications via SMTP (Gmail app password)."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(
    *,
    subject: str,
    body: str,
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    mail_from: str,
    mail_to: str,
    use_tls: bool = True,
) -> None:
    if not all([smtp_host, username, password, mail_from, mail_to]):
        raise ValueError("Email: заполните SMTP_* и EMAIL_* в .env")

    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = mail_from
    message["To"] = mail_to
    message.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.sendmail(mail_from, [mail_to], message.as_string())
