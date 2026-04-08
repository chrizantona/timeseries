from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Models
    model_dir: Path = Path("../timeseries/models_recursive")
    hybrid_model_path: Path = Path("../timeseries/out/recursive/recursive_model.joblib")
    blend_weights_path: Path = Path("../timeseries/models_recursive/blend_weights.json")
    
    # Business parameters
    vehicle_capacity_default: int = 5
    safety_factor_base: float = 1.1
    safety_factor_beta: float = 0.05
    replan_interval_minutes: int = 30
    
    # Database
    database_url: str = "sqlite:///./transport_orders.db"
    
    # Monitoring
    log_level: str = "INFO"
    enable_metrics: bool = True
    
    # Feature flags
    enable_dynamic_safety_factor: bool = True
    enable_smart_prioritization: bool = True
    enable_auto_replan: bool = False
    shadow_mode: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
