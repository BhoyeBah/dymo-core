import httpx
import structlog
from dymo_saas_core.core.config import settings

logger = structlog.get_logger(__name__)

def send_twilio_sms(to_phone: str, message: str) -> bool:
    """Send an SMS using Twilio REST API or fallback to Mock logging."""
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_PHONE:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            data = {
                "To": to_phone,
                "From": settings.TWILIO_FROM_PHONE,
                "Body": message
            }
            
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, data=data, auth=auth)
                response.raise_for_status()
                
            logger.info("SMS sent via Twilio API", to_phone=to_phone)
            return True
        except Exception as e:
            logger.error("Failed to send SMS via Twilio API, falling back to mock", to_phone=to_phone, error=str(e))
            # Fall through to Mock

    # Fallback mock log
    logger.info("Sending SMS (mocked fallback)", to_phone=to_phone, message=message)
    return True
