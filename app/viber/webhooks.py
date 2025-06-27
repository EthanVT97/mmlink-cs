from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
from app.services.viber_service import ViberService
from app.services.human_handoff import HumanHandoffService
from app.viber.menu_manager import MenuManager
from app.database.crud import UserCRUD, ConversationCRUD, MessageCRUD
from app.database.models import Message
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
viber = ViberService()
handoff = HumanHandoffService()
menu_manager = MenuManager()
user_crud = UserCRUD()
conversation_crud = ConversationCRUD()
message_crud = MessageCRUD()

class WebhookError(Exception):
    """Custom exception for webhook processing errors"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

@router.post("/webhook")
async def handle_viber_webhook(request: Request):
    """Handle incoming Viber webhook events"""
    try:
        # Parse and validate request
        data = await request.json()
        event = data.get("event")
        
        if not event:
            raise WebhookError("Missing event type", status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Received Viber event: {event}")
        
        # Handle webhook verification
        if event == "webhook":
            return JSONResponse(content={"status": "ok"})
        
        # Extract and validate user information
        sender_id = await _extract_sender_id(event, data)
        if not sender_id and event in ["subscribed", "conversation_started", "message"]:
            raise WebhookError("Missing sender ID for user event", status.HTTP_400_BAD_REQUEST)
        
        # Route to appropriate handler
        await _route_event(event, sender_id, data)
        
        return JSONResponse(content={"status": "ok"})
    
    except WebhookError as e:
        logger.error(f"Webhook validation error: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected webhook error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

async def _extract_sender_id(event: str, data: Dict[str, Any]) -> Optional[str]:
    """Extract sender ID from webhook data based on event type"""
    if event in ["subscribed", "conversation_started"]:
        user_info = data.get("user", {})
        return user_info.get("id")
    elif event == "message":
        sender_info = data.get("sender", {})
        return sender_info.get("id")
    elif event in ["delivered", "seen", "failed"]:
        return data.get("user_id")
    return None

async def _route_event(event: str, sender_id: Optional[str], data: Dict[str, Any]):
    """Route webhook event to appropriate handler"""
    handlers = {
        "subscribed": lambda: handle_user_subscription(sender_id, data.get("user", {})),
        "unsubscribed": lambda: handle_user_unsubscription(sender_id),
        "conversation_started": lambda: handle_conversation_start(sender_id, data.get("user", {})),
        "message": lambda: handle_user_message(sender_id, data),
        "delivered": lambda: handle_message_delivered(data),
        "seen": lambda: handle_message_seen(data),
        "failed": lambda: handle_message_failed(data)
    }
    
    handler = handlers.get(event)
    if handler:
        await handler()
    else:
        logger.warning(f"Unhandled event type: {event}")

async def handle_user_subscription(user_id: str, user_info: Dict[str, Any]):
    """Handle new user subscription"""
    try:
        logger.info(f"New user subscribed: {user_id}")
        
        # Save user to database
        await viber.save_user(user_id, user_info)
        
        # Send welcome message
        welcome_text = """မင်္ဂလာပါ! Myanmar Link မှ ကြိုဆိုပါသည်။

🔹 အင်တာနက် ဝန်ဆောင်မှု
🔹 ဖုန်း ဝန်ဆောင်မှု  
🔹 နည်းပညာ ပံ့ပိုးမှု

အောက်ပါ menu မှ ရွေးချယ်ပါ။"""
        
        await viber.send_text(user_id, welcome_text)
        
        # Send interactive menu
        await _send_main_menu(user_id)
        
    except Exception as e:
        logger.error(f"Subscription handling error for user {user_id}: {str(e)}")
        # Don't re-raise - we want to return 200 to Viber even if internal processing fails
        await _send_error_message(user_id, "ကြိုဆိုမှု ပို့ရာတွင် အမှားရှိပါသည်။ ထပ်မံကြိုးစားပါ။")

async def handle_user_unsubscription(user_id: str):
    """Handle user unsubscription"""
    try:
        logger.info(f"User unsubscribed: {user_id}")
        
        # Update user status to inactive
        await user_crud.update_user_status(user_id, "inactive")
        
        # Close any active conversations
        await conversation_crud.close_user_conversations(user_id)
        
        # Log the unsubscription
        await message_crud.create_system_message(
            user_id=user_id,
            content="User unsubscribed",
            message_type="system"
        )
        
    except Exception as e:
        logger.error(f"Unsubscription handling error for user {user_id}: {str(e)}")

async def handle_conversation_start(user_id: str, user_info: Dict[str, Any]):
    """Handle conversation start event"""
    try:
        logger.info(f"Conversation started with user: {user_id}")
        
        # Ensure user exists in database
        await viber.save_user(user_id, user_info)
        
        # Create or reactivate conversation
        conversation = await conversation_crud.get_or_create_conversation(user_id)
        
        # Send main menu
        await _send_main_menu(user_id)
        
    except Exception as e:
        logger.error(f"Conversation start error for user {user_id}: {str(e)}")
        await _send_error_message(user_id, "စကားဝိုင်း စတင်ရာတွင် အမှားရှိပါသည်။")

async def handle_user_message(user_id: str, data: Dict[str, Any]):
    """Handle incoming user message"""
    try:
        message_data = data.get("message", {})
        message_text = message_data.get("text", "")
        message_type = message_data.get("type", "text")
        
        logger.info(f"Received message from {user_id}: {message_text[:50]}...")
        
        # Save incoming message
        await message_crud.create_message(
            user_id=user_id,
            content=message_text,
            message_type="incoming",
            platform_data=message_data
        )
        
        # Check if user is in human handoff mode
        if await handoff.is_user_in_handoff(user_id):
            await handoff.forward_to_human(user_id, message_text)
            return
        
        # Process message based on type
        if message_type == "text":
            await _process_text_message(user_id, message_text)
        elif message_type in ["picture", "video", "file"]:
            await _process_media_message(user_id, message_data)
        else:
            await viber.send_text(user_id, "ဤအမျိုးအစား မက်ဆေ့ချ် ကို လက်ခံမထားပါ။")
        
    except Exception as e:
        logger.error(f"Message handling error for user {user_id}: {str(e)}")
        await _send_error_message(user_id, "မက်ဆေ့ချ် လုပ်ဆောင်ရာတွင် အမှားရှိပါသည်။")

async def handle_message_delivered(data: Dict[str, Any]):
    """Handle message delivery confirmation"""
    try:
        message_token = data.get("message_token")
        user_id = data.get("user_id")
        
        if message_token:
            await message_crud.update_message_status(message_token, "delivered")
            logger.debug(f"Message {message_token} delivered to {user_id}")
            
    except Exception as e:
        logger.error(f"Delivery handling error: {str(e)}")

async def handle_message_seen(data: Dict[str, Any]):
    """Handle message seen confirmation"""
    try:
        message_token = data.get("message_token")
        user_id = data.get("user_id")
        
        if message_token:
            await message_crud.update_message_status(message_token, "seen")
            logger.debug(f"Message {message_token} seen by {user_id}")
            
    except Exception as e:
        logger.error(f"Seen handling error: {str(e)}")

async def handle_message_failed(data: Dict[str, Any]):
    """Handle message failure notification"""
    try:
        message_token = data.get("message_token")
        user_id = data.get("user_id")
        failure_reason = data.get("failure_reason", "unknown")
        
        if message_token:
            await message_crud.update_message_status(message_token, "failed", failure_reason)
            logger.warning(f"Message {message_token} failed for {user_id}: {failure_reason}")
            
    except Exception as e:
        logger.error(f"Failure handling error: {str(e)}")

# Helper functions
async def _send_main_menu(user_id: str):
    """Send the main interactive menu to user"""
    try:
        menu_items = await menu_manager.get_active_menu()
        if menu_items:
            buttons = []
            for item in menu_items[:6]:  # Viber limits to 6 buttons
                button = await viber.create_button(
                    text=item.get('text', ''),
                    action_type=item.get('action_type', 'reply'),
                    action_body=item.get('action_value', item.get('text', ''))
                )
                buttons.append(button)
            
            await viber.send_keyboard(user_id, "ရွေးချယ်ပါ:", buttons)
        else:
            await viber.send_text(user_id, "Menu ရရှိရာတွင် အမှားရှိပါသည်။ စီမံခန့်ခွဲမှုနှင့် ဆက်သွယ်ပါ။")
            
    except Exception as e:
        logger.error(f"Menu sending error for user {user_id}: {str(e)}")
        await _send_error_message(user_id, "Menu ပြသရာတွင် အမှားရှိပါသည်။")

async def _process_text_message(user_id: str, message_text: str):
    """Process incoming text message"""
    # Implement your business logic here
    # This could include menu handling, AI responses, etc.
    
    # Example: Handle menu selections
    if message_text in ["အင်တာနက် ဝန်ဆောင်မှု", "Internet Service"]:
        await _handle_internet_service_inquiry(user_id)
    elif message_text in ["ဖုန်း ဝန်ဆောင်မှု", "Phone Service"]:
        await _handle_phone_service_inquiry(user_id)
    elif message_text in ["နည်းပညာ ပံ့ပိုးမှု", "Technical Support"]:
        await _handle_technical_support(user_id)
    else:
        # Default response or AI processing
        await viber.send_text(user_id, "ကျေးဇူးပြု၍ Menu မှ ရွေးချယ်ပါ သို့မဟုတ် အကူအညီအတွက် 'အကူအညီ' ဟု ရိုက်ထည့်ပါ။")
        await _send_main_menu(user_id)

async def _process_media_message(user_id: str, message_data: Dict[str, Any]):
    """Process incoming media message"""
    media_type = message_data.get("type")
    await viber.send_text(user_id, f"{media_type} ကို လက်ခံရရှိပါသည်။ ကျေးဇူးပြု၍ စာသားဖြင့် ပြန်လည်ဆက်သွယ်ပါ။")

async def _handle_internet_service_inquiry(user_id: str):
    """Handle internet service inquiry"""
    response = """🌐 အင်တာနက် ဝန်ဆောင်မှု

📊 အမျိုးအစားများ:
• Fiber Broadband
• ADSL 
• 4G/5G Plans

💰 စျေးနှုန်း နှင့် အသေးစိတ်အတွက် ဆက်သွယ်ပါ။"""
    
    await viber.send_text(user_id, response)

async def _handle_phone_service_inquiry(user_id: str):
    """Handle phone service inquiry"""
    response = """📞 ဖုန်း ဝန်ဆောင်မှု

📋 ဝန်ဆောင်မှုများ:
• Mobile Plans
• Fixed Line
• International Calls

📞 ဆက်သွယ်ရန်: ၀၉-၁၂၃-၄၅၆-၇၈၉"""
    
    await viber.send_text(user_id, response)

async def _handle_technical_support(user_id: str):
    """Handle technical support request"""
    response = """🔧 နည်းပညာ ပံ့ပိုးမှု

❓ ပြဿနာ အမျိုးအစား:
• Internet Connection
• Device Setup  
• Account Issues

👨‍💻 Technical Team နှင့် ဆက်သွယ်ရန် 'TECH' ဟု ရိုက်ပါ။"""
    
    await viber.send_text(user_id, response)
    
    # Check if user wants human handoff for technical support
    if "TECH" in response:
        await handoff.initiate_handoff(user_id, "technical_support")

async def _send_error_message(user_id: str, error_message: str):
    """Send error message to user"""
    try:
        await viber.send_text(user_id, f"❌ {error_message}")
    except Exception as e:
        logger.error(f"Failed to send error message to {user_id}: {str(e)}")
