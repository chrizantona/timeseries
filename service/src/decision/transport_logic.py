import math
from typing import Tuple, Dict, Literal
from datetime import datetime, timedelta

from src.common.config import settings


class TransportDecisionEngine:
    """
    Killer Features:
    1. Dynamic safety factor based on uncertainty
    2. Smart prioritization
    3. Route volatility tracking
    """
    
    def __init__(self):
        self.route_volatility_cache = {}  # In production: Redis/DB
    
    def calculate_transport_need(
        self,
        forecast_2h: float,
        vehicle_capacity: int,
        already_ordered: int = 0,
        safety_factor: float = None,
        uncertainty: float = 0.1,
        confidence: float = 1.0,
        route_id: int = None
    ) -> Tuple[int, int, float]:
        """
        Killer Feature #3: Dynamic safety factor
        
        Returns:
            required_vehicles: total vehicles needed
            additional_vehicles: additional vehicles to order
            safety_factor_used: actual safety factor applied
        """
        # Calculate dynamic safety factor
        if safety_factor is None and settings.enable_dynamic_safety_factor:
            safety_factor = self._calculate_dynamic_safety_factor(
                uncertainty=uncertainty,
                confidence=confidence,
                route_id=route_id
            )
        elif safety_factor is None:
            safety_factor = settings.safety_factor_base
        
        # Calculate required vehicles
        adjusted_forecast = forecast_2h * safety_factor
        required_vehicles = math.ceil(adjusted_forecast / vehicle_capacity)
        
        # Calculate additional need
        additional_vehicles = max(0, required_vehicles - already_ordered)
        
        return required_vehicles, additional_vehicles, safety_factor
    
    def _calculate_dynamic_safety_factor(
        self,
        uncertainty: float,
        confidence: float,
        route_id: int = None
    ) -> float:
        """
        Killer Feature: Smart safety factor that adapts to uncertainty
        
        Formula: safety_factor = base + beta * uncertainty - gamma * confidence
        """
        base = settings.safety_factor_base
        beta = settings.safety_factor_beta
        
        # Increase safety factor with uncertainty
        dynamic_factor = base + beta * uncertainty
        
        # Reduce if confidence is very high
        if confidence > 0.95:
            dynamic_factor *= 0.98
        
        # Check route volatility
        if route_id and route_id in self.route_volatility_cache:
            volatility = self.route_volatility_cache[route_id]
            if volatility > 0.3:  # High volatility
                dynamic_factor *= 1.05
        
        # Bounds
        return max(1.0, min(1.3, dynamic_factor))
    
    def calculate_priority(
        self,
        forecast_2h: float,
        additional_vehicles: int,
        uncertainty: float,
        confidence: float,
        timestamp: datetime,
        route_id: int = None
    ) -> Tuple[Literal["critical", "high", "normal", "low"], Dict]:
        """
        Killer Feature #2: Smart prioritization with business rules
        
        Returns:
            priority: priority level
            explanation: dict explaining the priority decision
        """
        explanation = {
            "factors": [],
            "score": 0
        }
        
        priority_score = 0
        
        # Factor 1: Forecast magnitude
        if forecast_2h > 50:
            priority_score += 3
            explanation["factors"].append("High forecast volume (>50)")
        elif forecast_2h > 30:
            priority_score += 2
            explanation["factors"].append("Medium forecast volume (30-50)")
        elif forecast_2h > 15:
            priority_score += 1
            explanation["factors"].append("Moderate forecast volume (15-30)")
        
        # Factor 2: Additional vehicles needed
        if additional_vehicles >= 5:
            priority_score += 3
            explanation["factors"].append(f"Large vehicle need ({additional_vehicles} vehicles)")
        elif additional_vehicles >= 3:
            priority_score += 2
            explanation["factors"].append(f"Moderate vehicle need ({additional_vehicles} vehicles)")
        elif additional_vehicles >= 1:
            priority_score += 1
        
        # Factor 3: Uncertainty
        if uncertainty > 0.3:
            priority_score += 2
            explanation["factors"].append("High uncertainty - risk of underestimation")
        elif uncertainty > 0.2:
            priority_score += 1
            explanation["factors"].append("Moderate uncertainty")
        
        # Factor 4: Low confidence
        if confidence < 0.7:
            priority_score += 1
            explanation["factors"].append("Low confidence prediction")
        
        # Factor 5: Time criticality
        hour = timestamp.hour
        if 10 <= hour <= 16:  # Peak hours
            priority_score += 1
            explanation["factors"].append("Peak hours - high activity expected")
        
        # Factor 6: Route volatility
        if route_id and route_id in self.route_volatility_cache:
            volatility = self.route_volatility_cache[route_id]
            if volatility > 0.3:
                priority_score += 2
                explanation["factors"].append(f"Volatile route (volatility: {volatility:.2f})")
        
        explanation["score"] = priority_score
        
        # Map score to priority
        if priority_score >= 8:
            return "critical", explanation
        elif priority_score >= 5:
            return "high", explanation
        elif priority_score >= 2:
            return "normal", explanation
        else:
            return "low", explanation
    
    def calculate_dispatch_time(
        self,
        current_time: datetime,
        priority: str
    ) -> datetime:
        """
        Killer Feature: Smart dispatch timing based on priority
        """
        if priority == "critical":
            # Immediate dispatch
            return current_time + timedelta(minutes=15)
        elif priority == "high":
            # Within 30 minutes
            return current_time + timedelta(minutes=30)
        elif priority == "normal":
            # Within 1 hour
            return current_time + timedelta(minutes=60)
        else:
            # Within 2 hours
            return current_time + timedelta(minutes=120)
    
    def update_route_volatility(self, route_id: int, actual: float, predicted: float):
        """
        Killer Feature: Learn from errors to improve future decisions
        """
        error = abs(actual - predicted) / (predicted + 1e-6)
        
        if route_id in self.route_volatility_cache:
            # Exponential moving average
            old_volatility = self.route_volatility_cache[route_id]
            new_volatility = 0.7 * old_volatility + 0.3 * error
            self.route_volatility_cache[route_id] = new_volatility
        else:
            self.route_volatility_cache[route_id] = error


# Global instance
decision_engine = TransportDecisionEngine()
