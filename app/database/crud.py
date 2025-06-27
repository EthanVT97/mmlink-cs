from typing import Optional, List, Dict, Any
from app.database.models import (
    BotUser, BotMenu, Conversation, Message, 
    SupportTicket, Staff, UserStatus, TicketStatus
)
from app.services.supabase_service import SupabaseService
from datetime import datetime, timedelta
import uuid

class UserCRUD:
    def __init__(self):
        self.db = SupabaseService()
        self.table = "bot_users"

    async def create_user(self, user_data: BotUser) -> Optional[Dict]:
        """Create new bot user"""
        data = user_data.dict()
        data['created_at'] = datetime.utcnow().isoformat()
        return await self.db.insert(self.table, data)

    async def get_user_by_viber_id(self, viber_id: str) -> Optional[Dict]:
        """Get user by Viber ID"""
        users = await self.db.fetch(self.table, filters={"viber_id": viber_id})
        return users[0] if users else None

    async def update_user_activity(self, viber_id: str) -> bool:
        """Update user's last activity timestamp"""
        try:
            await self.db.update(
                self.table,
                {"last_active": datetime.utcnow().isoformat()},
                filters={"viber_id": viber_id}
            )
            return True
        except Exception:
            return False

    async def get_active_users(self) -> List[Dict]:
        """Get all active users"""
        return await self.db.fetch(self.table, filters={"status": UserStatus.ACTIVE})

class MenuCRUD:
    def __init__(self):
        self.db = SupabaseService()
        self.table = "bot_menus"

    async def get_active_menu(self) -> Optional[Dict]:
        """Get currently active menu"""
        menus = await self.db.fetch(
            self.table, 
            filters={"is_active": True},
            order_by="created_at desc",
            limit=1
        )
        return menus[0] if menus else None

    async def create_menu(self, menu_data: BotMenu) -> Optional[Dict]:
        """Create new menu version"""
        # Deactivate existing menus
        await self.db.update(
            self.table,
            {"is_active": False},
            filters={"is_active": True}
        )
        
        # Create new menu
        data = menu_data.dict()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        return await self.db.insert(self.table, data)

    async def get_menu_history(self, limit: int = 10) -> List[Dict]:
        """Get menu version history"""
        return await self.db.fetch(
            self.table,
            order_by="created_at desc",
            limit=limit
        )

class ConversationCRUD:
    def __init__(self):
        self.db = SupabaseService()
        self.table = "conversations"

    async def create_conversation(self, user_id: str) -> Optional[Dict]:
        """Create new conversation"""
        data = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "status": "active",
            "started_at": datetime.utcnow().isoformat()
        }
        return await self.db.insert(self.table, data)

    async def get_active_conversation(self, user_id: str) -> Optional[Dict]:
        """Get user's active conversation"""
        conversations = await self.db.fetch(
            self.table,
            filters={"user_id": user_id, "status": "active"},
            order_by="started_at desc",
            limit=1
        )
        return conversations[0] if conversations else None

    async def escalate_conversation(self, conversation_id: str, agent_id: str) -> bool:
        """Escalate conversation to human agent"""
        try:
            await self.db.update(
                self.table,
                {
                    "status": "escalated",
                    "agent_id": agent_id,
                    "escalated_at": datetime.utcnow().isoformat()
                },
                filters={"id": conversation_id}
            )
            return True
        except Exception:
            return False

class MessageCRUD:
    def __init__(self):
        self.db = SupabaseService()
        self.table = "messages"

    async def save_message(self, message_data: Message) -> Optional[Dict]:
        """Save message to database"""
        data = message_data.dict()
        data['id'] = str(uuid.uuid4())
        data['timestamp'] = datetime.utcnow().isoformat()
        return await self.db.insert(self.table, data)

    async def get_conversation_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """Get messages for a conversation"""
        return await self.db.fetch(
            self.table,
            filters={"conversation_id": conversation_id},
            order_by="timestamp asc",
            limit=limit
        )

class TicketCRUD:
    def __init__(self):
        self.db = SupabaseService()
        self.table = "support_tickets"

    async def create_ticket(self, ticket_data: SupportTicket) -> Optional[Dict]:
        """Create new support ticket"""
        data = ticket_data.dict()
        data['id'] = str(uuid.uuid4())
        data['escalated_at'] = datetime.utcnow().isoformat()
        if ticket_data.timeout_at is None:
            data['timeout_at'] = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        return await self.db.insert(self.table, data)

    async def get_pending_tickets(self) -> List[Dict]:
        """Get all pending tickets"""
        return await self.db.fetch(
            self.table,
            filters={"status": TicketStatus.PENDING},
            order_by="escalated_at asc"
        )

    async def assign_ticket(self, ticket_id: str, agent_id: str) -> bool:
        """Assign ticket to agent"""
        try:
            await self.db.update(
                self.table,
                {
                    "status": TicketStatus.ASSIGNED,
                    "agent_id": agent_id
                },
                filters={"id": ticket_id}
            )
            return True
        except Exception:
            return False

    async def resolve_ticket(self, ticket_id: str) -> bool:
        """Mark ticket as resolved"""
        try:
            await self.db.update(
                self.table,
                {
                    "status": TicketStatus.RESOLVED,
                    "resolved_at": datetime.utcnow().isoformat()
                },
                filters={"id": ticket_id}
            )
            return True
        except Exception:
            return False

class StaffCRUD:
    def __init__(self):
        self.db = SupabaseService()
        self.table = "staff"

    async def get_available_agents(self) -> List[Dict]:
        """Get available customer service agents"""
        return await self.db.fetch(
            self.table,
            filters={"is_available": True, "role": "customer_support"}
        )

    async def get_agent_with_capacity(self) -> Optional[Dict]:
        """Get agent with available capacity"""
        agents = await self.db.fetch(
            self.table,
            filters={"is_available": True, "role": "customer_support"}
        )
        
        for agent in agents:
            if agent.get('current_chats', 0) < agent.get('max_concurrent_chats', 5):
                return agent
        return None

    async def update_agent_chat_count(self, agent_id: str, increment: int = 1) -> bool:
        """Update agent's current chat count"""
        try:
            agent = await self.db.fetch(self.table, filters={"id": agent_id})
            if agent:
                current_chats = agent[0].get('current_chats', 0) + increment
                await self.db.update(
                    self.table,
                    {"current_chats": max(0, current_chats)},
                    filters={"id": agent_id}
                )
            return True
        except Exception:
            return False
