import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
import structlog
from typing import Optional
from dymo_saas_core.core.config import settings

logger = structlog.get_logger(__name__)

def send_brevo_email(
    to_email: str,
    subject: str,
    body: str,
    template_id: Optional[str] = None
) -> bool:
    """Send an email using Brevo REST API, SMTP fallback, or Mock fallback."""
    # 1. Try Brevo REST API if configured
    if settings.BREVO_API_KEY:
        try:
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "sender": {
                    "name": settings.SMTP_FROM_NAME,
                    "email": settings.SMTP_FROM_EMAIL
                },
                "to": [{"email": to_email}],
                "subject": subject
            }
            if template_id:
                payload["templateId"] = int(template_id)
            else:
                payload["htmlContent"] = body

            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
            logger.info("Email sent via Brevo API", to_email=to_email, subject=subject)
            return True
        except Exception as e:
            logger.error("Failed to send email via Brevo API, trying SMTP fallback", to_email=to_email, error=str(e))
            # Fall through to SMTP

    # 2. Try Standard SMTP if SMTP_HOST is configured and not localhost/1025 default if we want real sending
    # Actually, we can check if SMTP_HOST is set and not default mock or just use it.
    if settings.SMTP_HOST and settings.SMTP_HOST != "localhost":
        try:
            msg = MIMEMultipart()
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = to_email
            msg["Subject"] = subject

            msg.attach(MIMEText(body, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0) as server:
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.starttls()
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)

            logger.info("Email sent via SMTP", to_email=to_email, subject=subject)
            return True
        except Exception as e:
            logger.error("Failed to send email via SMTP, falling back to mock", to_email=to_email, error=str(e))

    # 3. Fallback mock log
    logger.info("Sending email (mocked fallback)", to_email=to_email, subject=subject, template_id=template_id)
    return True
