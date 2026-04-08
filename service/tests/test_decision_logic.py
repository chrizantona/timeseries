import pytest
from datetime import datetime

from src.decision.transport_logic import TransportDecisionEngine


def test_calculate_transport_need():
    """Test transport calculation"""
    engine = TransportDecisionEngine()
    
    required, additional, safety = engine.calculate_transport_need(
        forecast_2h=18.7,
        vehicle_capacity=5,
        already_ordered=1,
        safety_factor=1.1,
        uncertainty=0.1,
        confidence=0.85
    )
    
    assert required > 0
    assert additional >= 0
    assert safety >= 1.0
    assert required >= already_ordered


def test_dynamic_safety_factor():
    """Test dynamic safety factor calculation"""
    engine = TransportDecisionEngine()
    
    # High uncertainty should increase safety factor
    _, _, safety_high = engine.calculate_transport_need(
        forecast_2h=20.0,
        vehicle_capacity=5,
        uncertainty=0.3,
        confidence=0.7
    )
    
    # Low uncertainty should have lower safety factor
    _, _, safety_low = engine.calculate_transport_need(
        forecast_2h=20.0,
        vehicle_capacity=5,
        uncertainty=0.05,
        confidence=0.95
    )
    
    assert safety_high > safety_low


def test_priority_calculation():
    """Test priority calculation"""
    engine = TransportDecisionEngine()
    
    # High forecast + high uncertainty = high priority
    priority, explanation = engine.calculate_priority(
        forecast_2h=60.0,
        additional_vehicles=10,
        uncertainty=0.3,
        confidence=0.7,
        timestamp=datetime(2026, 4, 10, 14, 0),
        route_id=105
    )
    
    assert priority in ["critical", "high", "normal", "low"]
    assert "factors" in explanation
    assert "score" in explanation
    assert explanation["score"] > 0


def test_dispatch_time_calculation():
    """Test dispatch time calculation"""
    engine = TransportDecisionEngine()
    
    current_time = datetime(2026, 4, 10, 11, 0)
    
    # Critical priority should have earliest dispatch
    critical_time = engine.calculate_dispatch_time(current_time, "critical")
    high_time = engine.calculate_dispatch_time(current_time, "high")
    normal_time = engine.calculate_dispatch_time(current_time, "normal")
    
    assert critical_time < high_time < normal_time


def test_route_volatility_update():
    """Test route volatility tracking"""
    engine = TransportDecisionEngine()
    
    route_id = 105
    
    # Update with large error
    engine.update_route_volatility(route_id, actual=30.0, predicted=20.0)
    
    assert route_id in engine.route_volatility_cache
    assert engine.route_volatility_cache[route_id] > 0
    
    # Update again with small error
    engine.update_route_volatility(route_id, actual=21.0, predicted=20.0)
    
    # Volatility should be updated (EMA)
    assert engine.route_volatility_cache[route_id] > 0
