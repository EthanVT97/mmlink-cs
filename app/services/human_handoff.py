from typing import Optional, Dict
from app.services.supabase_service import SupabaseService
from app.database.crud import TicketCRUD, StaffCRUD, ConversationCRUD
from app.database.models import SupportTicket
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class HumanHandoffService:
    def __init__(self):
        self.db = SupabaseService()
        self.ticket_crud = TicketCRUD()
        self.staff_crud = StaffCRUD()
        self.conversation_crud = ConversationCRUD()
        self.escalation_timeout = 300  # 5 minutes

    async def escalate_to_human(self, user_id: str, conversation_id: str, 
                               subject: str = None, description: str = None) -> Dict[str, any]:
        """Escalate conversation to human agent"""
        try:
            # Check agent availability
            available_agent = await self.staff_crud.get_agent_with_capacity()
            
            if not available_agent:
                return {
                    "success": False,
                    "message": "No agents available at the moment",
                    "status": "queue"
                }
            
            # Create support ticket
            ticket_data = SupportTicket(
                user_id=user_id,
                conversation_id=conversation_id,
                subject=subject or "Customer Service Request",
                description=description or "User requested human assistance",
                timeout_at=datetime.utcnow() + timedelta(seconds=self.escalation_timeout)
            )
            
            ticket = await self.ticket_crud.create_ticket(ticket_data)
            
            if ticket:
                # Assign to available agent
                assignment_success = await self.ticket_crud.assign_ticket(
                    ticket['id'], 
                    available_agent['id']
                )
                
                if assignment_success:
                    # Update conversation status
                    await self.conversation_crud.escalate_conversation(
                        conversation_id, 
                        available_agent['id']
                    )
                    
                    # Update agent's chat count
                    await self.staff_crud.update_agent_chat_count(
                        available_agent['id'], 
                        increment=1
                    )
                    
                    # Notify agent (implement based on your notification system)
                    await self._notify_agent(available_agent, ticket)
                    
                    return {
                        "success": True,
                        "message": "Connected to human agent",
                        "agent_name": available_agent.get('name', 'Customer Service'),
                        "ticket_id": ticket['id']
                    }
            
            return {
                "success": False,
                "message": "Failed to create support ticket",
                "status": "error"
            }
            
        except Exception as e:
            logger.error(f"Escalation failed: {str(e)}")
            return {
                "success": False,
                "message": "System error during escalation",
                "status": "error"
            }

    async def check_agent_availability(self) -> bool:
        """Check if human agents are available"""
        try:
            agents = await self.staff_crud.get_available_agents()
            return len(agents) > 0
        except Exception as e:
            logger.error(f"Error checking agent availability: {str(e)}")
            return False

    async def get_agent_workload(self) -> Dict[str, any]:
        """Get current agent workload statistics"""
        try:
            agents = await self.staff_crud.get_available_agents()
            pending_tickets = await self.ticket_crud.get_pending_tickets()
            
            total_capacity = sum(agent.get('max_concurrent_chats', 5) for agent in agents)
            current_load = sum(agent.get('current_chats', 0) for agent in agents)
            
            return {
                "available_agents": len(agents),
                "pending_tickets": len(pending_tickets),
                "total_capacity": total_capacity,
                "current_load": current_load,
                "utilization_rate": (current_load / total_capacity * 100) if total_capacity > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting agent workload: {str(e)}")
            return {}

    async def end_conversation(self, conversation_id: str, ticket_id: str = None) -> bool:
        """End conversation and update agent availability"""
        try:
            # Get conversation details
            conversation = await self.db.fetch(
                "conversations", 
                filters={"id": conversation_id}
            )
            
            if conversation and conversation[0].get('agent_id'):
                agent_id = conversation[0]['agent_id']
                
                # Update agent chat count
                await self.staff_crud.update_agent_chat_count(
                    agent_id, 
                    increment=-1
                )
                
                # Mark conversation as closed
                await self.db.update(
                    "conversations",
                    {
                        "status": "closed",
                        "ended_at": datetime.utcnow().isoformat()
                    },
                    filters={"id": conversation_id}
                )
                
                # Resolve ticket if provided
                if ticket_id:
                    await self.ticket_crud.resolve_ticket(ticket_id)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error ending conversation: {str(e)}")
            return False

    async def handle_timeout(self, ticket_id: str) -> bool:
        """Handle ticket timeout scenarios"""
        try:
            # Get ticket details
            tickets = await self.db.fetch("support_tickets", filters={"id": ticket_id})
            
            if not tickets:
                return False
                
            ticket = tickets[0]
            
            # Check if ticket has timed out
            timeout_at = datetime.fromisoformat(ticket['timeout_at'].replace('Z', '+00:00'))
            
            if datetime.utcnow() > timeout_at.replace(tzinfo=None):
                # Move ticket back to queue or close
                if ticket['status'] == 'pending':
                    # Close unassigned ticket
                    await self.db.update(
                        "support_tickets",
                        {
                            "status": "closed",
                            "resolved_at": datetime.utcnow().isoformat()
                        },
                        filters={"id": ticket_id}
                    )
                    
                    # Notify user about timeout
                    await self._notify_user_timeout(ticket['user_id'])
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling timeout: {str(e)}")
            return False

    async def get_queue_position(self, user_id: str) -> Optional[int]:
        """Get user's position in support queue"""
        try:
            pending_tickets = await self.ticket_crud.get_pending_tickets()
            
            for index, ticket in enumerate(pending_tickets):
                if ticket['user_id'] == user_id:
                    return index + 1
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting queue position: {str(e)}")
            return None

    async def _notify_agent(self, agent: Dict, ticket: Dict) -> bool:
        """Notify agent about new ticket assignment"""
        try:
            # Implementation depends on your notification system
            # This could be email, Slack, internal dashboard notification, etc.
            logger.info(f"New ticket {ticket['id']} assigned to agent {agent['name']}")
            
            # Here you could integrate with:
            # - Email service
            # - Slack API
            # - Push notifications
            # - WebSocket for real-time dashboard updates
            
            return True
            
        except Exception as e:
            logger.error(f"Error notifying agent: {str(e)}")
            return False

    async def _notify_user_timeout(self, user_id: str) -> bool:
        """Notify user about support timeout"""
        try:
            # This should integrate with your Viber service
            # to send a message to the user
            logger.info(f"Notifying user {user_id} about support timeout")
            return True
            
        except Exception as e:
            logger.error(f"Error notifying user: {str(e)}")
            return False

    async def transfer_conversation(self, conversation_id: str, from_agent_id: str, 
                                   to_agent_id: str, reason: str = None) -> bool:
        """Transfer conversation between agents"""
        try:
            # Update conversation
            await self.conversation_crud.escalate_conversation(conversation_id, to_agent_id)
            
            # Update agent chat counts
            await self.staff_crud.update_agent_chat_count(from_agent_id, increment=-1)
            await self.staff_crud.update_agent_chat_count(to_agent_id, increment=1)
            
            # Update ticket if exists
            tickets = await self.db.fetch(
                "support_tickets", 
                filters={"conversation_id": conversation_id, "status": "assigned"}
            )
            
            if tickets:
                await self.db.update(
                    "support_tickets",
                    {"agent_id": to_agent_id},
                    filters={"id": tickets[0]['id']}
                )
            
            # Log transfer
            logger.info(f"Conversation {conversation_id} transferred from {from_agent_id} to {to_agent_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error transferring conversation: {str(e)}")
            return False
