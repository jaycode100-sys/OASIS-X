"""
Notification service for Telegram and WhatsApp integration.
Configure environment variables for actual API credentials.
"""
import os
import json
import logging
import httpx
from datetime import datetime, timedelta
from typing import Optional

from config import settings

logger = logging.getLogger("oasis-x.notifications")

# ── Configuration ──────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v17.0")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

# ── Notification Templates ────────────────────────────────────────────────────
INCIDENT_TEMPLATE = """
🚨 *OASIS-X Incident Alert*

*Status:* {status}
*City:* {city}
*Severity:* {severity}
*Time:* {timestamp}

*Summary:*
{summary}

*Recommended Action:*
{action}

---
_OASIS-X Autonomous Fibre Fault Healing System_
"""

DAILY_SUMMARY_TEMPLATE = """
📊 *OASIS-X Network Summary*

*Date:* {date}
*Time:* {timestamp}
*City:* {city}

*Metrics:*
• Total Records: {total_records}
• Normal: {normal_count} ({normal_pct}%)
• Degrading: {degrading_count} ({degrading_pct}%)
• Critical: {critical_count} ({critical_pct}%)

*NCC Compliance:*
• OSNR: {osnr_compliance}%
• BER: {ber_compliance}%
• Latency: {latency_compliance}%
• Overall: {overall_status}

*Top Issues:*
{top_issues}

---
_OASIS-X Autonomous Fibre Fault Healing System_
"""


class NotificationService:
    """Service for sending notifications via Telegram and WhatsApp."""
    
    def __init__(self):
        self.telegram_enabled = bool(TELEGRAM_BOT_TOKEN)
        self.whatsapp_enabled = bool(WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN)
        
        if self.telegram_enabled:
            logger.info("Telegram notifications enabled")
        else:
            logger.info("Telegram notifications disabled (no credentials)")
            
        if self.whatsapp_enabled:
            logger.info("WhatsApp notifications enabled")
        else:
            logger.info("WhatsApp notifications disabled (no credentials)")
    
    async def send_telegram(self, message: str, chat_id: str = None) -> bool:
        """Send a message via Telegram Bot API."""
        if not self.telegram_enabled:
            logger.warning("Telegram not configured, skipping send")
            return False
        
        chat_id = chat_id or TELEGRAM_CHAT_ID
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"Telegram message sent to {chat_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def send_whatsapp(self, message: str, phone_number: str) -> bool:
        """Send a message via WhatsApp Business API."""
        if not self.whatsapp_enabled:
            logger.warning("WhatsApp not configured, skipping send")
            return False
        
        url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": phone_number,
                        "type": "text",
                        "text": {"body": message}
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"WhatsApp message sent to {phone_number}")
                return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False
    
    async def send_incident_alert(
        self,
        status: str,
        city: str,
        severity: str,
        summary: str,
        action: str,
        telegram_chat_id: str = None,
        whatsapp_number: str = None
    ) -> dict:
        """Send incident alert to configured channels."""
        message = INCIDENT_TEMPLATE.format(
            status=status,
            city=city,
            severity=severity,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary=summary,
            action=action
        )
        
        results = {"telegram": False, "whatsapp": False}
        
        if telegram_chat_id or self.telegram_enabled:
            results["telegram"] = await self.send_telegram(message, telegram_chat_id)
        
        if whatsapp_number or self.whatsapp_enabled:
            results["whatsapp"] = await self.send_whatsapp(message, whatsapp_number)
        
        return results
    
    async def send_daily_summary(
        self,
        city: str,
        summary_data: dict,
        telegram_chat_id: str = None,
        whatsapp_number: str = None
    ) -> dict:
        """Send daily network summary to configured channels."""
        total = summary_data.get("total_records", 0)
        distribution = summary_data.get("state_distribution", {})
        normal = distribution.get("NORMAL", 0)
        degrading = distribution.get("DEGRADING", 0)
        critical = distribution.get("CRITICAL", 0)
        
        ncc = summary_data.get("ncc_compliance", {})
        
        # Calculate percentages
        normal_pct = round((normal / total * 100) if total > 0 else 0, 1)
        degrading_pct = round((degrading / total * 100) if total > 0 else 0, 1)
        critical_pct = round((critical / total * 100) if total > 0 else 0, 1)
        
        # Get top issues
        issues = summary_data.get("top_issues", [])
        top_issues = "\n".join(f"• {issue}" for issue in issues[:5]) if issues else "• No major issues"
        
        message = DAILY_SUMMARY_TEMPLATE.format(
            date=datetime.now().strftime("%Y-%m-%d"),
            timestamp=datetime.now().strftime("%H:%M:%S WAT"),
            city=city,
            total_records=total,
            normal_count=normal,
            normal_pct=normal_pct,
            degrading_count=degrading,
            degrading_pct=degrading_pct,
            critical_count=critical,
            critical_pct=critical_pct,
            osnr_compliance=ncc.get("osnr_compliance_pct", 0),
            ber_compliance=ncc.get("ber_compliance_pct", 0),
            latency_compliance=ncc.get("latency_compliance_pct", 0),
            overall_status=ncc.get("overall_status", "UNKNOWN"),
            top_issues=top_issues
        )
        
        results = {"telegram": False, "whatsapp": False}
        
        if telegram_chat_id or self.telegram_enabled:
            results["telegram"] = await self.send_telegram(message, telegram_chat_id)
        
        if whatsapp_number or self.whatsapp_enabled:
            results["whatsapp"] = await self.send_whatsapp(message, whatsapp_number)
        
        return results


# Singleton instance
notification_service = NotificationService()
