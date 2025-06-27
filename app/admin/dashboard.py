from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from app.admin.auth import get_current_admin
from app.viber.menu_manager import MenuManager
from app.services.supabase_service import SupabaseService

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: dict = Depends(get_current_admin)):
    db = SupabaseService()
    
    # Get stats for dashboard
    stats = {
        "active_users": await db.count("bot_users", filters={"is_active": True}),
        "pending_tickets": await db.count("support_tickets", filters={"status": "pending"}),
        "resolved_today": await db.count("support_tickets", filters={
            "status": "resolved",
            "resolved_at": f"gte.{datetime.utcnow().date().isoformat()}"
        }),
        "top_menus": await db.fetch("bot_menus", order_by="created_at", limit=3)
    }
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "admin": admin,
        "stats": stats
    })

@router.post("/update-menu")
async def update_menu(menu_data: dict, admin: dict = Depends(get_current_admin)):
    menu_manager = MenuManager()
    try:
        await menu_manager.update_menu(menu_data['items'], admin['id'])
        return {"status": "success", "message": "Menu updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
