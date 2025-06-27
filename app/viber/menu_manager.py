from typing import List, Dict
from app.services.supabase_service import SupabaseService
from fastapi import HTTPException

class MenuManager:
    def __init__(self):
        self.db = SupabaseService()

    async def get_active_menu(self) -> List[Dict]:
        """Get currently active menu from database"""
        try:
            menu = await self.db.fetch("bot_menus", filters={"is_active": True})
            return menu[0]['menu_items'] if menu else []
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Menu fetch error: {str(e)}")

    async def update_menu(self, new_menu: List[Dict], updated_by: str) -> bool:
        """Update the bot menu"""
        try:
            # Deactivate current active menu
            await self.db.update(
                "bot_menus",
                {"is_active": False},
                filters={"is_active": True}
            )
            
            # Insert new menu
            await self.db.insert("bot_menus", {
                "menu_items": new_menu,
                "is_active": True,
                "updated_by": updated_by,
                "updated_at": "now()"
            })
            return True
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Menu update error: {str(e)}")
