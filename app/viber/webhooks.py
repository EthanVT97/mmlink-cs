from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from app.services.viber_service import ViberService
from app.services.human_handoff import HumanHandoffService
from app.viber.menu_manager import MenuManager
from datetime import datetime

router = APIRouter()
viber = ViberService()
handoff = HumanHandoffService()
menu_manager = MenuManager()

@router.post("/webhook")
async def handle_viber_webhook(request: Request):
    try:
        data = await request.json()
        event = data.get("event")
        
        if event == "webhook":
            return JSONResponse(content={"status": "ok"})
        
        sender_id = data["user"]["id"] if event == "subscribed" else data["sender"]["id"]
        
        # Handle different event types
        if event == "subscribed":
            await handle_new_user(sender_id)
        elif event == "message":
            await handle_user_message(sender_id, data)
        elif event == "conversation_started":
            await handle_conversation_start(sender_id)
            
        return {"status": "ok"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def handle_new_user(user_id: str):
    """Handle new user subscription"""
    # Save user to database
    await viber.save_user(user_id)
    
    # Send welcome message with current menu
    menu_items = await menu_manager.get_active_menu()
    await viber.send_rich_message(user_id, {
        "type": "rich_media",
        "text": "မြန်မာလင်း၀က်ဘ်ဆိုက်မှ ကြိုဆိုပါသည်။ အောက်ပါ menu မှ ရွေးချယ်ပါ။",
        "buttons": menu_items
    })

async def handle_user_message(user_id: str, data: dict):
    """Process user messages"""
    message_type = data["message"]["type"]
    
    if message_type == "text":
        text = data["message"]["text"].lower().strip()
        
        # Check for human handoff request
        if text in ["agent", "human", "representative", "ဝန်ထမ်းနဲ့ပြော"]:
            if await handoff.check_agent_availability():
                await handoff.escalate_to_human(user_id, data["message_token"])
                await viber.send_text(user_id, "ဝန်ထမ်းနှင့်ချိတ်ဆက်နေပါသည်...")
            else:
                await viber.send_text(user_id, "ဝန်ထမ်းများ အလုပ်များနေပါသည်။ ကျေးဇူးပြု၍ နောက်မှပြန်လည်ဆက်သွယ်ပါ။")
            return
        
        # Process normal message
        response = await viber.process_message(text)
        await viber.send_text(user_id, response)
