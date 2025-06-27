from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"

class TicketStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ESCALATED = "escalated"
    CLOSED = "closed"

class BotUser(BaseModel):
    viber_id: str = Field(..., description="Viber user ID")
    name: Optional[str] = Field(None, description="User display name")
    language: str = Field(default="my", description="Preferred language")
    phone: Optional[str] = Field(None, description="User phone number")
    status: UserStatus = Field(default=UserStatus.ACTIVE)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    last_active: Optional[datetime] = Field(default_factory=datetime.utcnow)

class BotMenu(BaseModel):
    id: Optional[str] = Field(None, description="Menu ID")
    menu_items: List[Dict[str, Any]] = Field(..., description="Menu button items")
    is_active: bool = Field(default=True, description="Whether menu is active")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_by: str = Field(..., description="Admin who updated the menu")
    version: int = Field(default=1, description="Menu version number")

class MenuItem(BaseModel):
    text: str = Field(..., description="Button text")
    action_type: str = Field(..., description="Action type (text, url, callback)")
    action_value: str = Field(..., description="Action value")
    order: int = Field(..., description="Display order")

class Conversation(BaseModel):
    id: Optional[str] = Field(None, description="Conversation ID")
    user_id: str = Field(..., description="Viber user ID")
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    started_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = Field(None)
    agent_id: Optional[str] = Field(None, description="Assigned agent ID")
    escalated_at: Optional[datetime] = Field(None)

class Message(BaseModel):
    id: Optional[str] = Field(None, description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    sender_id: str = Field(..., description="Sender ID")
    sender_type: str = Field(..., description="user or agent")
    message_type: str = Field(..., description="Message type")
    content: Dict[str, Any] = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)

class SupportTicket(BaseModel):
    id: Optional[str] = Field(None, description="Ticket ID")
    user_id: str = Field(..., description="User ID")
    conversation_id: str = Field(..., description="Conversation ID")
    agent_id: Optional[str] = Field(None, description="Assigned agent ID")
    status: TicketStatus = Field(default=TicketStatus.PENDING)
    priority: str = Field(default="normal", description="Ticket priority")
    subject: Optional[str] = Field(None, description="Ticket subject")
    description: Optional[str] = Field(None, description="Ticket description")
    escalated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = Field(None)
    timeout_at: Optional[datetime] = Field(None)

class Staff(BaseModel):
    id: Optional[str] = Field(None, description="Staff ID")
    name: str = Field(..., description="Staff name")
    email: str = Field(..., description="Staff email")
    role: str = Field(..., description="Staff role")
    is_available: bool = Field(default=True, description="Availability status")
    max_concurrent_chats: int = Field(default=5, description="Max concurrent chats")
    current_chats: int = Field(default=0, description="Current active chats")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

class AdminUser(BaseModel):
    username: str = Field(..., description="Admin username")
    password: str = Field(..., description="Admin password")
    role: str = Field(default="admin", description="Admin role")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
