import uuid
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, asdict

from src.api.schemas import OrderResponse


@dataclass
class Order:
    order_id: str
    status: str
    created_at: datetime
    office_from_id: int
    route_id: int
    vehicles: int
    priority: str
    planned_dispatch_time: datetime
    forecast_2h: Optional[float] = None
    actual_2h: Optional[float] = None


class OrderService:
    """
    Killer Feature: Order tracking and history
    In production: use PostgreSQL/MongoDB
    For MVP: in-memory storage
    """
    
    def __init__(self):
        self.orders = []  # In-memory storage
        self.order_counter = 1
    
    def init_db(self):
        """Initialize database (for MVP: just clear memory)"""
        print("✓ Order service initialized")
    
    def create_order(
        self,
        office_from_id: int,
        route_id: int,
        vehicles: int,
        priority: str,
        planned_dispatch_time: datetime,
        forecast_2h: Optional[float] = None
    ) -> OrderResponse:
        """
        Create a new transport order
        """
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d')}-{self.order_counter:06d}"
        self.order_counter += 1
        
        order = Order(
            order_id=order_id,
            status="created",
            created_at=datetime.now(),
            office_from_id=office_from_id,
            route_id=route_id,
            vehicles=vehicles,
            priority=priority,
            planned_dispatch_time=planned_dispatch_time,
            forecast_2h=forecast_2h
        )
        
        self.orders.append(order)
        
        return OrderResponse(**asdict(order))
    
    def list_orders(self, limit: int = 100) -> List[OrderResponse]:
        """
        List recent orders
        """
        recent_orders = sorted(
            self.orders,
            key=lambda x: x.created_at,
            reverse=True
        )[:limit]
        
        return [OrderResponse(**asdict(order)) for order in recent_orders]
    
    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        """
        Get specific order
        """
        for order in self.orders:
            if order.order_id == order_id:
                return OrderResponse(**asdict(order))
        return None
    
    def update_order_status(self, order_id: str, status: str):
        """
        Update order status
        """
        for order in self.orders:
            if order.order_id == order_id:
                order.status = status
                return True
        return False
    
    def record_actual(self, order_id: str, actual_2h: float):
        """
        Killer Feature: Record actual shipments for monitoring
        """
        for order in self.orders:
            if order.order_id == order_id:
                order.actual_2h = actual_2h
                return True
        return False


# Global instance
order_service = OrderService()
