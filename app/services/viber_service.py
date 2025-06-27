import requests
import json
from typing import Dict, List, Optional, Any
from app.config import Settings
from app.database.crud import UserCRUD, MessageCRUD, ConversationCRUD
from app.database.models import BotUser, Message
import logging

logger = logging.getLogger(__name__)

class ViberService:
    def __init__(self):
        self.settings = Settings()
        self.token = self.settings.viber_token
        self.api_url = "https://chatapi.viber.com/pa"
        self.headers = {
            "X-Viber-Auth-Token": self.token,
            "Content-Type": "application/json"
        }
        self.user_crud = UserCRUD()
        self.message_crud = MessageCRUD()
        self.conversation_crud = ConversationCRUD()

    async def send_message(self, user_id: str, message: Dict[str, Any]) -> bool:
        """Send message to Viber user"""
        try:
            url = f"{self.api_url}/send_message"
            payload = {
                "receiver": user_id,
                "min_api_version": 1,
                "sender": {
                    "name": "Myanmar Link",
                    "avatar": "https://example.com/avatar.jpg"
                },
                **message
            }
            
            response = requests.post(url, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("status") == 0
            else:
                logger.error(f"Viber API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return False

    async def send_text(self, user_id: str, text: str) -> bool:
        """Send text message"""
        message = {
            "type": "text",
            "text": text
        }
        return await self.send_message(user_id, message)

    async def send_rich_media(self, user_id: str, rich_media: Dict) -> bool:
        """Send rich media message with buttons"""
        message = {
            "type": "rich_media",
            "rich_media": rich_media
        }
        return await self.send_message(user_id, message)

    async def send_keyboard(self, user_id: str, text: str, buttons: List[Dict]) -> bool:
        """Send message with keyboard buttons"""
        message = {
            "type": "text",
            "text": text,
            "keyboard": {
                "Type": "keyboard",
                "DefaultHeight": True,
                "Buttons": buttons
            }
        }
        return await self.send_message(user_id, message)

    async def create_button(self, text: str, action_type: str = "reply", action_body: str = None) -> Dict:
        """Create button for keyboard"""
        return {
            "Columns": 6,
            "Rows": 1,
            "ActionType": action_type,
            "ActionBody": action_body or text,
            "Text": text,
            "TextSize": "medium",
            "TextHAlign": "center",
            "TextVAlign": "middle"
        }

    async def save_user(self, viber_id: str, user_info: Optional[Dict] = None) -> bool:
        """Save or update user information"""
        try:
            existing_user = await self.user_crud.get_user_by_viber_id(viber_id)
            
            if not existing_user:
                user_data = BotUser(
                    viber_id=viber_id,
                    name=user_info.get("name", "") if user_info else "",
                    language=self.settings.default_language
                )
                await self.user_crud.create_user(user_data)
            else:
                await self.user_crud.update_user_activity(viber_id)
            
            return True
        except Exception as e:
            logger.error(f"Error saving user: {str(e)}")
            return False

    async def save_message(self, conversation_id: str, sender_id: str, 
                          sender_type: str, message_type: str, content: Dict) -> bool:
        """Save message to database"""
        try:
            message_data = Message(
                conversation_id=conversation_id,
                sender_id=sender_id,
                sender_type=sender_type,
                message_type=message_type,
                content=content
            )
            await self.message_crud.save_message(message_data)
            return True
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            return False

    async def get_or_create_conversation(self, user_id: str) -> Optional[str]:
        """Get active conversation or create new one"""
        try:
            conversation = await self.conversation_crud.get_active_conversation(user_id)
            
            if not conversation:
                conversation = await self.conversation_crud.create_conversation(user_id)
            
            return conversation['id'] if conversation else None
        except Exception as e:
            logger.error(f"Error getting conversation: {str(e)}")
            return None

    async def process_message(self, text: str, user_id: str) -> str:
        """Process user message and return appropriate response"""
        text = text.lower().strip()
        
        # Define responses in Myanmar language
        responses = {
            "မင်္ဂလာပါ": "မင်္ဂလာပါ! Myanmar Link မှ ကြိုဆိုပါသည်။ ကျွန်ုပ်တို့ ဘာများကူညီဆောင်ရွက်ပေးရမလဲ?",
            "hello": "Hello! Welcome to Myanmar Link. How can we help you?",
            "help": "ကူညီပေးနိုင်သည့်အရာများ:\n- ဝန်ဆောင်မှုအချက်အလက်များ\n- နည်းပညာပံ့ပိုးမှု\n- ဝန်ထမ်းနှင့်စကားပြော",
            "service": "Myanmar Link ဝန်ဆောင်မှုများ:\n- အင်တာနက် ဝန်ဆောင်မှု\n- ဖုန်း ဝန်ဆောင်မှု\n- နည်းပညာ ပံ့ပိုးမှု",
            "contact": "ဆက်သွယ်ရန်:\n📞 ဖုန်း: +95-1-123-4567\n- အီးမေးလ်: support@myanmarlink.com",
            "about": "Myanmar Link သည် Myanmar နိုင်ငံတွင် ဆက်သွယ်ရေးဝန်ဆောင်မှုများပေးသည့် ကုမ္ပဏီဖြစ်ပါသည်။"
        }
        
        # Check for exact matches first
        for key, response in responses.items():
            if key in text:
                return response
        
        # Default response
        return "ကျေးဇူးပြု၍ menu မှရွေးချယ်ပါ သို့မဟုတ် 'help' ဟုရိုက်ပါ။ ဝန်ထမ်းနှင့်စကားပြောလိုပါက 'agent' ဟုရိုက်ပါ။"

    async def set_webhook(self, webhook_url: str) -> bool:
        """Set webhook URL for Viber bot"""
        try:
            url = f"{self.api_url}/set_webhook"
            payload = {
                "url": webhook_url,
                "event_types": [
                    "delivered",
                    "seen", 
                    "failed",
                    "subscribed",
                    "unsubscribed",
                    "conversation_started"
                ]
            }
            
            response = requests.post(url, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Webhook set successfully: {result}")
                return result.get("status") == 0
            else:
                logger.error(f"Failed to set webhook: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting webhook: {str(e)}")
            return False

    async def get_account_info(self) -> Optional[Dict]:
        """Get bot account information"""
        try:
            url = f"{self.api_url}/get_account_info"
            response = requests.post(url, headers=self.headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get account info: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting account info: {str(e)}")
            return None
