from supabase import create_client, Client
from typing import Optional, List, Dict
import os

class SupabaseService:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.client: Client = create_client(url, key)
    
    async def fetch(self, table: str, filters: Optional[Dict] = None, order_by: Optional[str] = None, limit: Optional[int] = None):
        query = self.client.table(table)
        
        if filters:
            for key, value in filters.items():
                if isinstance(value, list):
                    query = query.in_(key, value)
                else:
                    query = query.eq(key, value)
        
        if order_by:
            query = query.order(order_by)
            
        if limit:
            query = query.limit(limit)
            
        result = query.execute()
        return result.data
    
    async def insert(self, table: str, data: Dict):
        result = self.client.table(table).insert(data).execute()
        return result.data[0] if result.data else None
    
    async def update(self, table: str, data: Dict, filters: Dict):
        query = self.client.table(table).update(data)
        
        for key, value in filters.items():
            query = query.eq(key, value)
            
        result = query.execute()
        return result.data
    
    async def count(self, table: str, filters: Optional[Dict] = None) -> int:
        query = self.client.table(table).select("count", count="exact")
        
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
                
        result = query.execute()
        return result.count
