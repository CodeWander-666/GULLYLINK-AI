import asyncio
import random
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI()

# Mount frontend directory for static files if needed, here we use templates
templates = Jinja2Templates(directory="frontend")

# --- In-Memory Database (Base Model) ---
# 5 Dummy Vendors for Diagnosis
VENDORS = {
    "v1": {"id": "v1", "name": "Chai Point", "lat": 28.6139, "lng": 77.2090, "icon": "☕", "category": "Beverages", "orders": []},
    "v2": {"id": "v2", "name": "Burger Singh", "lat": 28.6129, "lng": 77.2100, "icon": "🍔", "category": "Fast Food", "orders": []},
    "v3": {"id": "v3", "name": "Sharma Sweets", "lat": 28.6145, "lng": 77.2080, "icon": "🍬", "category": "Sweets", "orders": []},
    "v4": {"id": "v4", "name": "Pizza Hut Mobile", "lat": 28.6150, "lng": 77.2110, "icon": "🍕", "category": "Italian", "orders": []},
    "v5": {"id": "v5", "name": "Gully Momos", "lat": 28.6110, "lng": 77.2070, "icon": "🥟", "category": "Street Food", "orders": []},
}

# Dummy Menu (Zomato Style)
MENU = {
    "v1": [{"item": "Masala Chai", "price": 20}, {"item": "Bun Maska", "price": 40}],
    "v2": [{"item": "Veggie Burger", "price": 80}, {"item": "Fries", "price": 60}],
    "v3": [{"item": "Rasgulla", "price": 30}, {"item": "Samosa", "price": 15}],
    "v4": [{"item": "Margherita Pizza", "price": 150}, {"item": "Garlic Bread", "price": 90}],
    "v5": [{"item": "Steamed Momos", "price": 50}, {"item": "Fried Momos", "price": 60}],
}

# --- Connection Manager for Realtime ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# --- Models ---
class Order(BaseModel):
    vendor_id: str
    item: str
    customer_lat: float
    customer_lng: float

# --- Routes ---

@app.get("/")
async def get_user_ui(request: Request):
    return templates.TemplateResponse("user.html", {"request": request})

@app.get("/vendor")
async def get_vendor_ui(request: Request):
    return templates.TemplateResponse("vendor.html", {"request": request})

@app.get("/api/vendors")
async def get_vendors():
    return VENDORS

@app.get("/api/menu/{vendor_id}")
async def get_menu(vendor_id: str):
    return MENU.get(vendor_id, [])

@app.post("/api/order")
async def place_order(order: Order):
    if order.vendor_id in VENDORS:
        order_data = {
            "id": random.randint(1000, 9999),
            "item": order.item,
            "status": "Pending",
            "lat": order.customer_lat,
            "lng": order.customer_lng
        }
        VENDORS[order.vendor_id]["orders"].append(order_data)
        
        # Realtime: Notify everyone (Vendor sees order, User sees status)
        await manager.broadcast({
            "type": "new_order",
            "vendor_id": order.vendor_id,
            "order": order_data
        })
        return {"status": "Order Placed", "order_id": order_data["id"]}
    return {"status": "Vendor not found"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # If Vendor updates location
            if data['type'] == 'location_update':
                vendor_id = data['id']
                if vendor_id in VENDORS:
                    VENDORS[vendor_id]['lat'] = data['lat']
                    VENDORS[vendor_id]['lng'] = data['lng']
                    # Broadcast new location to ALL users immediately
                    await manager.broadcast(data)
            
            # If Vendor updates Order Status (Accept/Reject)
            elif data['type'] == 'order_update':
                await manager.broadcast(data)

    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Start with: uvicorn main:app --reload
