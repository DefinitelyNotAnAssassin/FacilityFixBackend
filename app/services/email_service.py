from typing import List, Dict, Any, Optional
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import logging
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class EmailService:
    """Email service using SendGrid for transactional emails"""
    
    def __init__(self):
        self.api_key = os.getenv('SENDGRID_API_KEY')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@facilityfix.com')
        self.from_name = os.getenv('FROM_NAME', 'FacilityFix')
        self.mock_mode = os.getenv('EMAIL_MOCK_MODE', 'true').lower() == 'true'
        
        # Initialize SendGrid client if not in mock mode
        if not self.mock_mode and self.api_key:
            self.sg = sendgrid.SendGridAPIClient(api_key=self.api_key)
        else:
            self.sg = None
            logger.info("Email service running in MOCK mode")
        
        # Setup Jinja2 template environment
        template_dir = Path(__file__).parent.parent / 'templates' / 'email'
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    async def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None
    ) -> bool:
        """Send an email using SendGrid"""
        try:
            if self.mock_mode:
                # Mock implementation - log email details
                logger.info(f"[MOCK EMAIL] To: {to_name} <{to_email}>")
                logger.info(f"[MOCK EMAIL] Subject: {subject}")
                logger.info(f"[MOCK EMAIL] HTML Content: {html_content[:200]}...")
                return True
            
            if not self.sg:
                logger.error("SendGrid client not initialized")
                return False
            
            # Create email
            from_email = Email(self.from_email, self.from_name)
            to_email_obj = To(to_email, to_name)
            
            mail = Mail(from_email, to_email_obj, subject, plain_content or "")
            if html_content:
                mail.add_content(Content("text/html", html_content))
            
            # Send email
            response = self.sg.send(mail)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email. Status: {response.status_code}")
                return False
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    async def send_bulk_email(
        self,
        recipients: List[Dict[str, str]],  # [{"email": "...", "name": "..."}]
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send emails to multiple recipients"""
        try:
            if self.mock_mode:
                logger.info(f"[MOCK BULK EMAIL] Recipients: {len(recipients)}")
                logger.info(f"[MOCK BULK EMAIL] Subject: {subject}")
                return {"success_count": len(recipients), "failure_count": 0}
            
            success_count = 0
            failure_count = 0
            
            for recipient in recipients:
                success = await self.send_email(
                    recipient["email"],
                    recipient["name"],
                    subject,
                    html_content,
                    plain_content
                )
                
                if success:
                    success_count += 1
                else:
                    failure_count += 1
            
            return {
                "success_count": success_count,
                "failure_count": failure_count,
                "total_recipients": len(recipients)
            }
            
        except Exception as e:
            logger.error(f"Error sending bulk email: {str(e)}")
            return {"success_count": 0, "failure_count": len(recipients), "error": str(e)}
    
    def render_template(self, template_name: str, **kwargs) -> str:
        """Render email template with data"""
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            logger.error(f"Error rendering email template {template_name}: {str(e)}")
            return f"<html><body>Error rendering template: {str(e)}</body></html>"
    
    async def send_work_order_notification(self, work_order_data: Dict[str, Any], notification_type: str) -> bool:
        """Send work order related email notifications"""
        try:
            recipient_email = work_order_data.get('recipient_email')
            recipient_name = work_order_data.get('recipient_name')
            
            if not recipient_email:
                logger.warning("No recipient email provided for work order notification")
                return False
            
            # Determine template and subject based on notification type
            template_map = {
                "work_order_created": {
                    "template": "work_order_created.html",
                    "subject": "New Work Order Created - FacilityFix"
                },
                "work_order_assigned": {
                    "template": "work_order_assigned.html",
                    "subject": "Work Order Assigned to You - FacilityFix"
                },
                "work_order_completed": {
                    "template": "work_order_completed.html",
                    "subject": "Work Order Completed - FacilityFix"
                },
                "work_order_status_update": {
                    "template": "work_order_status_update.html",
                    "subject": "Work Order Status Update - FacilityFix"
                }
            }
            
            template_info = template_map.get(notification_type)
            if not template_info:
                logger.error(f"Unknown work order notification type: {notification_type}")
                return False
            
            # Render email content
            html_content = self.render_template(
                template_info["template"],
                work_order=work_order_data,
                notification_type=notification_type,
                timestamp=datetime.now()
            )
            
            # Send email
            success = await self.send_email(
                recipient_email,
                recipient_name,
                template_info["subject"],
                html_content
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending work order email notification: {str(e)}")
            return False
    
    async def send_maintenance_notification(self, maintenance_data: Dict[str, Any], notification_type: str) -> bool:
        """Send maintenance related email notifications"""
        try:
            recipient_email = maintenance_data.get('recipient_email')
            recipient_name = maintenance_data.get('recipient_name')
            
            if not recipient_email:
                logger.warning("No recipient email provided for maintenance notification")
                return False
            
            template_map = {
                "maintenance_scheduled": {
                    "template": "maintenance_scheduled.html",
                    "subject": "Maintenance Scheduled - FacilityFix"
                },
                "maintenance_reminder": {
                    "template": "maintenance_reminder.html",
                    "subject": "Maintenance Reminder - FacilityFix"
                },
                "maintenance_overdue": {
                    "template": "maintenance_overdue.html",
                    "subject": "URGENT: Overdue Maintenance - FacilityFix"
                },
                "maintenance_completed": {
                    "template": "maintenance_completed.html",
                    "subject": "Maintenance Completed - FacilityFix"
                }
            }
            
            template_info = template_map.get(notification_type)
            if not template_info:
                logger.error(f"Unknown maintenance notification type: {notification_type}")
                return False
            
            html_content = self.render_template(
                template_info["template"],
                maintenance=maintenance_data,
                notification_type=notification_type,
                timestamp=datetime.now()
            )
            
            success = await self.send_email(
                recipient_email,
                recipient_name,
                template_info["subject"],
                html_content
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending maintenance email notification: {str(e)}")
            return False
    
    async def send_inventory_notification(self, inventory_data: Dict[str, Any], notification_type: str) -> bool:
        """Send inventory related email notifications"""
        try:
            recipient_email = inventory_data.get('recipient_email')
            recipient_name = inventory_data.get('recipient_name')
            
            if not recipient_email:
                logger.warning("No recipient email provided for inventory notification")
                return False
            
            template_map = {
                "low_stock_alert": {
                    "template": "low_stock_alert.html",
                    "subject": "Low Stock Alert - FacilityFix"
                },
                "inventory_request_approved": {
                    "template": "inventory_request_approved.html",
                    "subject": "Inventory Request Approved - FacilityFix"
                },
                "inventory_request_denied": {
                    "template": "inventory_request_denied.html",
                    "subject": "Inventory Request Denied - FacilityFix"
                },
                "reorder_reminder": {
                    "template": "reorder_reminder.html",
                    "subject": "Reorder Reminder - FacilityFix"
                }
            }
            
            template_info = template_map.get(notification_type)
            if not template_info:
                logger.error(f"Unknown inventory notification type: {notification_type}")
                return False
            
            html_content = self.render_template(
                template_info["template"],
                inventory=inventory_data,
                notification_type=notification_type,
                timestamp=datetime.now()
            )
            
            success = await self.send_email(
                recipient_email,
                recipient_name,
                template_info["subject"],
                html_content
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending inventory email notification: {str(e)}")
            return False
    
    async def send_announcement_email(self, announcement_data: Dict[str, Any], recipients: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send announcement emails to multiple recipients"""
        try:
            subject = f"Announcement: {announcement_data.get('title', 'FacilityFix Update')}"
            
            html_content = self.render_template(
                "announcement.html",
                announcement=announcement_data,
                timestamp=datetime.now()
            )
            
            result = await self.send_bulk_email(recipients, subject, html_content)
            return result
            
        except Exception as e:
            logger.error(f"Error sending announcement email: {str(e)}")
            return {"success_count": 0, "failure_count": len(recipients), "error": str(e)}

# Create global service instance
email_service = EmailService()
