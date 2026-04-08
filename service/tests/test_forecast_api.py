import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from src.api.app import app

client = TestClient(app)


def test_health_check():
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "degraded", "error"]
    assert "models_loaded" in data


def test_forecast_predict():
    """Test forecast endpoint"""
    payload = {
        "route_id": 105,
        "office_from_id": 42,
        "timestamp": "2026-04-10T11:00:00",
        "status_1": 18,
        "status_2": 11,
        "status_3": 9,
        "status_4": 6,
        "status_5": 5,
        "status_6": 4,
        "status_7": 3,
        "status_8": 2
    }
    
    response = client.post("/forecast/predict", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "forecast_2h" in data
    assert "confidence" in data
    assert "model_name" in data
    assert data["forecast_2h"] >= 0
    assert 0 <= data["confidence"] <= 1


def test_decision_calculate():
    """Test decision endpoint"""
    payload = {
        "route_id": 105,
        "office_from_id": 42,
        "forecast_2h": 18.7,
        "vehicle_capacity": 5,
        "already_ordered": 1
    }
    
    response = client.post("/decision/calculate", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "required_vehicles" in data
    assert "additional_vehicles" in data
    assert "priority" in data
    assert data["priority"] in ["critical", "high", "normal", "low"]
    assert data["required_vehicles"] >= 0
    assert data["additional_vehicles"] >= 0


def test_plan_dispatch():
    """Test complete dispatch planning"""
    payload = {
        "route_id": 105,
        "office_from_id": 42,
        "timestamp": "2026-04-10T11:00:00",
        "status_1": 18,
        "status_2": 11,
        "status_3": 9,
        "status_4": 6,
        "status_5": 5,
        "status_6": 4,
        "status_7": 3,
        "status_8": 2,
        "vehicle_capacity": 5,
        "already_ordered": 1
    }
    
    response = client.post("/plan/dispatch", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "forecast_2h" in data
    assert "required_vehicles" in data
    assert "additional_vehicles" in data
    assert "priority" in data
    assert "planned_dispatch_time" in data
    assert "explanation" in data


def test_create_order():
    """Test order creation"""
    payload = {
        "office_from_id": 42,
        "route_id": 105,
        "vehicles": 4,
        "priority": "high",
        "planned_dispatch_time": "2026-04-10T11:30:00"
    }
    
    response = client.post("/orders/create", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "order_id" in data
    assert "status" in data
    assert data["status"] == "created"


def test_list_orders():
    """Test listing orders"""
    response = client.get("/orders")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
