"""
email_utils.py
==============
Модуль для отправки email-сообщений через SMTP.
Используется для отправки кодов подтверждения при сбросе пароля.
"""

import aiosmtplib
from email.mime.text import MIMEText
from config import EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD


async def send_reset_code_email(to_email: str, code: str):
    """
    Отправляет код сброса пароля на указанный email.
    
    Args:
        to_email (str): Email получателя
        code (str): 6-значный код подтверждения
    """
    msg = MIMEText(
        f"Ваш код для сброса пароля: {code}\n"
        f"Код действителен 10 минут.\n"
        f"Если вы не запрашивали сброс пароля, проигнорируйте это письмо.",
        'plain',
        'utf-8'
    )
    
    msg["Subject"] = "Сброс пароля в Secretariat"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    
    await aiosmtplib.send(
        msg,
        hostname=EMAIL_HOST,
        port=EMAIL_PORT,
        start_tls=True,
        username=EMAIL_USER,
        password=EMAIL_PASSWORD
    )