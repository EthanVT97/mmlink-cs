from typing import Optional, Dict
from app.services.supabase_service import SupabaseService
from datetime import datetime, timedelta

class HumanHandoffService:
    def __init__(self):
        self.db = SupabaseService()
        self.escalation_timeout = 300  # 5 minutes

    async def escalate_to_human(self, user_id: str, conversation_id: str) -> bool:
        """Escalate conversation to human agent"""
        try:
            # Create support ticket
            ticket = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "status": "pending",
                "escalated_at": datetime.utcnow().isoformat(),
                "timeout_at": (datetime.utcnow() + timedelta(seconds=self.escalation_timeout)).isoformat()
            }
            
            await self.db.insert("support_tickets", ticket)
            
            # Notify available agents via internal system
            await self._notify_agents()
            
            return True
        except Exception as e:
            print(f"Escalation failed: {str(e)}")
            return False

    async def _notify_agents(self):
        """Notify available customer service agents"""
        # Implementation depends on your notification system
        pass

    async def check_agent_availability(self) -> bool:
        """Check if human agents are available"""
        agents = await self.db.fetch("staff", filters={"is_available": True, "role": "customer_support"})
        return len(agents) > 0
