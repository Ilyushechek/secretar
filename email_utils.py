# email_utils.py

import aiosmtplib
from email.mime.text import MIMEText
from config import EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD

async def send_reset_code_email(to_email: str, code: str):
    """Отправляет код сброса пароля на email"""
    msg = MIMEText(f"Ваш код для сброса пароля: {code}\nКод действителен 10 минут.")
    msg["Subject"] = "Сброс пароля в Secretariat"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email

    await aiosmtplib.send(
        msg,
        hostname=EMAIL_HOST,
        port=EMAIL_PORT,
        start_tls=True,
        username=EMAIL_USER,
        password=EMAIL_PASSWORD,
    )