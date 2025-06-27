from fastapi import APIRouter, Request, Depends, HTTPException, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.admin.auth import get_current_admin, auth_service, create_admin_token
from app.viber.menu_manager import MenuManager
from app.services.supabase_service import SupabaseService
from app.database.crud import UserCRUD, TicketCRUD, StaffCRUD, ConversationCRUD
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)

# Initialize templates
templates = Jinja2Templates(directory="app/admin/templates")

# Initialize services
menu_manager = MenuManager()
db = SupabaseService()
user_crud = UserCRUD()
ticket_crud = TicketCRUD()
staff_crud = StaffCRUD()
conversation_crud = ConversationCRUD()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle admin login"""
    try:
        admin = auth_service.authenticate_admin(username, password)
        
        if not admin:
            return templates.TemplateResponse(
                "login.html", 
                {
                    "request": request, 
                    "error": "Invalid username or password"
                }
            )
        
        # Create access token
        access_token = create_admin_token(username, admin['role'])
        
        # Redirect to dashboard with token
        response = RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="access_token", 
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=86400  # 24 hours
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return templates.TemplateResponse(
            "login.html", 
            {
                "request": request, 
                "error": "Login failed. Please try again."
            }
        )

@router.get("/logout")
async def logout():
    """Handle admin logout"""
    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: dict = Depends(get_current_admin)):
    """Display admin dashboard"""
    try:
        # Get dashboard statistics
        today = datetime.utcnow().date()
        
        stats = {
            "total_users": await user_crud.get_user_count(),
            "active_users": await user_crud.get_active_user_count(),
            "pending_tickets": await ticket_crud.get_ticket_count("pending"),
            "resolved_today": await ticket_crud.get_tickets_resolved_today(today),
            "active_conversations": await conversation_crud.get_active_conversation_count(),
            "available_agents": len(await staff_crud.get_available_agents())
        }
        
        # Get recent activities
        recent_tickets = await ticket_crud.get_recent_tickets(limit=5)
        recent_users = await user_crud.get_recent_users(limit=5)
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "admin": admin,
            "stats": stats,
            "recent_tickets": recent_tickets,
            "recent_users": recent_users
        })
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail="Dashboard loading failed")

@router.get("/menu", response_class=HTMLResponse)
async def menu_management(request: Request, admin: dict = Depends(get_current_admin)):
    """Display menu management page"""
    try:
        # Get current active menu
        current_menu = await menu_manager.get_active_menu()
        menu_history = await menu_manager.get_menu_history(limit=10)
        
        return templates.TemplateResponse("menu_editor.html", {
            "request": request,
            "admin": admin,
            "current_menu": current_menu,
            "menu_history": menu_history
        })
        
    except Exception as e:
        logger.error(f"Menu management error: {str(e)}")
        raise HTTPException(status_code=500, detail="Menu management loading failed")

@router.post("/api/menu/update")
async def update_menu(menu_data: dict, admin: dict = Depends(get_current_admin)):
    """Update bot menu"""
    try:
        success = await menu_manager.update_menu(
            menu_data.get('items', []), 
            admin['username']
        )
        
        if success:
            return {"status": "success", "message": "Menu updated successfully"}
        else:
            raise HTTPException(status_code=400, detail="Menu update failed")
            
    except Exception as e:
        logger.error(f"Menu update error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tickets", response_class=HTMLResponse)
async def ticket_management(request: Request, admin: dict = Depends(get_current_admin)):
    """Display ticket management page"""
    try:
        # Get tickets by status
        pending_tickets = await ticket_crud.get_tickets_by_status("pending")
        assigned_tickets = await ticket_crud.get_tickets_by_status("assigned")
        resolved_tickets = await ticket_crud.get_tickets_by_status("resolved", limit=20)
        
        # Get available agents
        available_agents = await staff_crud.get_available_agents()
        
        return templates.TemplateResponse("tickets.html", {
            "request": request,
            "admin": admin,
            "pending_tickets": pending_tickets,
            "assigned_tickets": assigned_tickets,
            "resolved_tickets": resolved_tickets,
            "available_agents": available_agents
        })
        
    except Exception as e:
        logger.error(f"Ticket management error: {str(e)}")
        raise HTTPException(status_code=500, detail="Ticket management loading failed")

@router.post("/api/ticket/{ticket_id}/assign")
async def assign_ticket(ticket_id: str, agent_id: str = Form(...), 
                       admin: dict = Depends(get_current_admin)):
    """Assign ticket to agent"""
    try:
        success = await ticket_crud.assign_ticket(ticket_id, agent_id)
        
        if success:
            # Update agent chat count
            await staff_crud.update_agent_chat_count(agent_id, increment=1)
            return {"status": "success", "message": "Ticket assigned successfully"}
        else:
            raise HTTPException(status_code=400, detail="Ticket assignment failed")
            
    except Exception as e:
        logger.error(f"Ticket assignment error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/ticket/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, admin: dict = Depends(get_current_admin)):
    """Mark ticket as resolved"""
    try:
        success = await ticket_crud.resolve_ticket(ticket_id)
        
        if success:
            return {"status": "success", "message": "Ticket resolved successfully"}
        else:
            raise HTTPException(status_code=400, detail="Ticket resolution failed")
            
    except Exception as e:
        logger.error(f"Ticket resolution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users", response_class=HTMLResponse)
async def user_management(request: Request, admin: dict = Depends(get_current_admin)):
    """Display user management page"""
    try:
        # Get users with pagination
        users = await user_crud.get_users_with_stats(limit=50)
        user_stats = await user_crud.get_user_statistics()
        
        return templates.TemplateResponse("users.html", {
            "request": request,
            "admin": admin,
            "users": users,
            "user_stats": user_stats
        })
        
    except Exception as e:
        logger.error(f"User management error: {str(e)}")
        raise HTTPException(status_code=500, detail="User management loading failed")

@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request, admin: dict = Depends(get_current_admin)):
    """Display analytics dashboard"""
    try:
        # Get analytics data
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)
        
        analytics_data = {
            "user_growth": await user_crud.get_user_growth_data(start_date, end_date),
            "ticket_trends": await ticket_crud.get_ticket_trends(start_date, end_date),
            "response_times": await ticket_crud.get_response_time_stats(),
            "menu_interactions": await menu_manager.get_menu_interaction_stats(),
            "peak_hours": await conversation_crud.get_peak_hours_data()
        }
        
        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "admin": admin,
            "analytics": analytics_data
        })
        
    except Exception as e:
        logger.error(f"Analytics dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail="Analytics loading failed")

@router.get("/api/stats")
async def get_dashboard_stats(admin: dict = Depends(get_current_admin)):
    """Get real-time dashboard statistics (API endpoint)"""
    try:
        stats = {
            "online_users": await user_crud.get_online_user_count(),
            "pending_tickets": await ticket_crud.get_ticket_count("pending"),
            "active_conversations": await conversation_crud.get_active_conversation_count(),
            "agent_availability": await staff_crud.get_agent_availability_stats()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Stats API error: {str(e)}")
        raise HTTPException(status_code=500, detail="Statistics loading failed")

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, admin: dict = Depends(get_current_admin)):
    """Display settings page"""
    try:
        # Get current settings
        bot_settings = await db.fetch("bot_settings") or {}
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "admin": admin,
            "settings": bot_settings
        })
        
    except Exception as e:
        logger.error(f"Settings page error: {str(e)}")
        raise HTTPException(status_code=500, detail="Settings loading failed")

@router.post("/api/settings/update")
async def update_settings(settings_data: dict, admin: dict = Depends(get_current_admin)):
    """Update bot settings"""
    try:
        # Update settings in database
        await db.upsert("bot_settings", settings_data)
        
        return {"status": "success", "message": "Settings updated successfully"}
        
    except Exception as e:
        logger.error(f"Settings update error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
