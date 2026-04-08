from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class RouteStatusInput(BaseModel):
    route_id: int
    office_from_id: int
    timestamp: datetime
    status_1: int = Field(ge=0)
    status_2: int = Field(ge=0)
    status_3: int = Field(ge=0)
    status_4: int = Field(ge=0)
    status_5: int = Field(ge=0)
    status_6: int = Field(ge=0)
    status_7: int = Field(ge=0)
    status_8: int = Field(ge=0)


class ForecastResponse(BaseModel):
    forecast_2h: float
    model_name: str
    confidence: float
    uncertainty: Optional[float] = None
    explanation: Optional[dict] = None


class DecisionInput(BaseModel):
    route_id: int
    office_from_id: int
    forecast_2h: float
    vehicle_capacity: int = 5
    already_ordered: int = 0
    safety_factor: Optional[float] = None


class DecisionResponse(BaseModel):
    required_vehicles: int
    additional_vehicles: int
    priority: Literal["critical", "high", "normal", "low"]
    safety_factor_used: float
    explanation: dict


class DispatchPlanInput(RouteStatusInput):
    vehicle_capacity: int = 5
    already_ordered: int = 0
    safety_factor: Optional[float] = None


class DispatchPlanResponse(BaseModel):
    forecast_2h: float
    confidence: float
    required_vehicles: int
    additional_vehicles: int
    priority: Literal["critical", "high", "normal", "low"]
    planned_dispatch_time: datetime
    safety_factor_used: float
    explanation: dict


class OrderCreateInput(BaseModel):
    office_from_id: int
    route_id: int
    vehicles: int
    priority: Literal["critical", "high", "normal", "low"]
    planned_dispatch_time: datetime
    forecast_2h: Optional[float] = None


class OrderResponse(BaseModel):
    order_id: str
    status: Literal["created", "pending", "dispatched", "completed", "cancelled"]
    created_at: datetime
    office_from_id: int
    route_id: int
    vehicles: int
    priority: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    timestamp: datetime
    models_loaded: bool
    database_connected: bool
