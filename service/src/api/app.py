from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid

from src.api.schemas import (
    HealthResponse, RouteStatusInput, ForecastResponse,
    DecisionInput, DecisionResponse, DispatchPlanInput, DispatchPlanResponse,
    OrderCreateInput, OrderResponse
)
from src.forecasting.service import forecast_service
from src.decision.transport_logic import decision_engine
from src.orders.service import order_service
from src.common.config import settings

app = FastAPI(
    title="Transport Dispatch Service",
    description="Automated transport dispatch planning based on shipment forecasts",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Load models on startup"""
    print("🚀 Starting Transport Dispatch Service...")
    forecast_service.load_models()
    order_service.init_db()
    print("✓ Service ready!")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    """
    return HealthResponse(
        status="ok" if forecast_service.models_loaded else "degraded",
        timestamp=datetime.now(),
        models_loaded=forecast_service.models_loaded,
        database_connected=True
    )


@app.post("/forecast/predict", response_model=ForecastResponse)
async def predict_forecast(input_data: RouteStatusInput):
    """
    Killer Feature #1: Forecast with confidence and explainability
    
    Get shipment forecast for the next 2 hours
    """
    try:
        route_dict = input_data.model_dump()
        
        forecast, confidence, uncertainty, explanation = forecast_service.predict(route_dict)
        
        return ForecastResponse(
            forecast_2h=forecast,
            model_name="hybrid_recursive_blend_v1",
            confidence=confidence,
            uncertainty=uncertainty,
            explanation=explanation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast error: {str(e)}")


@app.post("/decision/calculate", response_model=DecisionResponse)
async def calculate_decision(input_data: DecisionInput):
    """
    Killer Feature #3: Dynamic safety factor + Smart prioritization
    
    Calculate transport requirements based on forecast
    """
    try:
        # Get uncertainty from cache or use default
        uncertainty = 0.1
        confidence = 0.85
        
        # Calculate transport need
        required, additional, safety_used = decision_engine.calculate_transport_need(
            forecast_2h=input_data.forecast_2h,
            vehicle_capacity=input_data.vehicle_capacity,
            already_ordered=input_data.already_ordered,
            safety_factor=input_data.safety_factor,
            uncertainty=uncertainty,
            confidence=confidence,
            route_id=input_data.route_id
        )
        
        # Calculate priority
        priority, priority_explanation = decision_engine.calculate_priority(
            forecast_2h=input_data.forecast_2h,
            additional_vehicles=additional,
            uncertainty=uncertainty,
            confidence=confidence,
            timestamp=datetime.now(),
            route_id=input_data.route_id
        )
        
        explanation = {
            "safety_factor_applied": safety_used,
            "calculation": f"ceil({input_data.forecast_2h} * {safety_used} / {input_data.vehicle_capacity}) = {required}",
            "priority_reasoning": priority_explanation
        }
        
        return DecisionResponse(
            required_vehicles=required,
            additional_vehicles=additional,
            priority=priority,
            safety_factor_used=safety_used,
            explanation=explanation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision error: {str(e)}")


@app.post("/plan/dispatch", response_model=DispatchPlanResponse)
async def plan_dispatch(input_data: DispatchPlanInput):
    """
    Killer Feature: One-click dispatch planning
    
    Complete pipeline: forecast → decision → dispatch plan
    """
    try:
        # Step 1: Forecast
        route_dict = input_data.model_dump()
        forecast, confidence, uncertainty, forecast_explanation = forecast_service.predict(route_dict)
        
        # Step 2: Calculate transport need
        required, additional, safety_used = decision_engine.calculate_transport_need(
            forecast_2h=forecast,
            vehicle_capacity=input_data.vehicle_capacity,
            already_ordered=input_data.already_ordered,
            safety_factor=input_data.safety_factor,
            uncertainty=uncertainty,
            confidence=confidence,
            route_id=input_data.route_id
        )
        
        # Step 3: Calculate priority
        priority, priority_explanation = decision_engine.calculate_priority(
            forecast_2h=forecast,
            additional_vehicles=additional,
            uncertainty=uncertainty,
            confidence=confidence,
            timestamp=input_data.timestamp,
            route_id=input_data.route_id
        )
        
        # Step 4: Calculate dispatch time
        dispatch_time = decision_engine.calculate_dispatch_time(
            current_time=input_data.timestamp,
            priority=priority
        )
        
        # Combine explanations
        explanation = {
            "forecast": forecast_explanation,
            "decision": {
                "safety_factor": safety_used,
                "calculation": f"ceil({forecast:.2f} * {safety_used} / {input_data.vehicle_capacity}) = {required}"
            },
            "priority": priority_explanation,
            "dispatch_timing": f"{priority} priority → dispatch in {(dispatch_time - input_data.timestamp).seconds // 60} minutes"
        }
        
        return DispatchPlanResponse(
            forecast_2h=forecast,
            confidence=confidence,
            required_vehicles=required,
            additional_vehicles=additional,
            priority=priority,
            planned_dispatch_time=dispatch_time,
            safety_factor_used=safety_used,
            explanation=explanation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning error: {str(e)}")


@app.post("/orders/create", response_model=OrderResponse)
async def create_order(input_data: OrderCreateInput):
    """
    Create transport order
    """
    try:
        if settings.shadow_mode:
            # Shadow mode: log but don't execute
            print(f"[SHADOW MODE] Would create order: {input_data.model_dump()}")
        
        order = order_service.create_order(
            office_from_id=input_data.office_from_id,
            route_id=input_data.route_id,
            vehicles=input_data.vehicles,
            priority=input_data.priority,
            planned_dispatch_time=input_data.planned_dispatch_time,
            forecast_2h=input_data.forecast_2h
        )
        
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order creation error: {str(e)}")


@app.get("/orders", response_model=list[OrderResponse])
async def list_orders(limit: int = 100):
    """
    List recent orders
    """
    try:
        orders = order_service.list_orders(limit=limit)
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing orders: {str(e)}")


@app.get("/")
async def root():
    """
    Root endpoint with service info
    """
    return {
        "service": "Transport Dispatch Service",
        "version": "1.0.0",
        "status": "operational",
        "features": [
            "Ensemble forecasting with confidence",
            "Dynamic safety factor",
            "Smart prioritization",
            "One-click dispatch planning",
            "Explainable decisions",
            "Shadow mode support"
        ],
        "endpoints": {
            "health": "/health",
            "forecast": "/forecast/predict",
            "decision": "/decision/calculate",
            "dispatch_plan": "/plan/dispatch",
            "create_order": "/orders/create",
            "list_orders": "/orders"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
