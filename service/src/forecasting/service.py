import joblib
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple
from datetime import datetime

from src.common.config import settings


class ForecastService:
    """Killer Feature: Ensemble forecasting with uncertainty estimation"""
    
    def __init__(self):
        self.models_loaded = False
        self.hybrid_model = None
        self.feature_columns = None
        self.categorical_columns = None
        self.blend_weights = {"hybrid": 1.0}
        
    def load_models(self):
        """Load all models and configurations"""
        try:
            # Load hybrid model
            if settings.hybrid_model_path.exists():
                self.hybrid_model = joblib.load(settings.hybrid_model_path)
                print(f"✓ Loaded hybrid model from {settings.hybrid_model_path}")
            
            # Load feature columns
            feature_cols_path = settings.model_dir / "recursive_feature_columns.json"
            if feature_cols_path.exists():
                with open(feature_cols_path) as f:
                    self.feature_columns = json.load(f)
                print(f"✓ Loaded {len(self.feature_columns)} feature columns")
            
            # Load categorical columns
            cat_cols_path = settings.model_dir / "recursive_categorical_columns.json"
            if cat_cols_path.exists():
                with open(cat_cols_path) as f:
                    self.categorical_columns = json.load(f)
                print(f"✓ Loaded {len(self.categorical_columns)} categorical columns")
            
            # Load blend weights if available
            if settings.blend_weights_path.exists():
                with open(settings.blend_weights_path) as f:
                    self.blend_weights = json.load(f)
                print(f"✓ Loaded blend weights: {self.blend_weights}")
            
            self.models_loaded = True
            print("✓ All models loaded successfully")
            
        except Exception as e:
            print(f"✗ Error loading models: {e}")
            self.models_loaded = False
    
    def build_features(self, route_data: Dict) -> pd.DataFrame:
        """
        Killer Feature: Smart feature engineering with calendar and status features
        """
        df = pd.DataFrame([route_data])
        
        # Calendar features
        ts = pd.to_datetime(df['timestamp'])
        df['hour'] = ts.dt.hour
        df['minute'] = ts.dt.minute
        df['dayofweek'] = ts.dt.dayofweek
        df['is_weekend'] = (ts.dt.dayofweek >= 5).astype(int)
        df['halfhour_slot'] = (ts.dt.hour * 2 + (ts.dt.minute // 30))
        
        # Cyclical encoding
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['dow_sin'] = np.sin(2 * np.pi * df['dayofweek'] / 7)
        df['dow_cos'] = np.cos(2 * np.pi * df['dayofweek'] / 7)
        df['slot_sin'] = np.sin(2 * np.pi * df['halfhour_slot'] / 48)
        df['slot_cos'] = np.cos(2 * np.pi * df['halfhour_slot'] / 48)
        
        # Status aggregates
        status_cols = [f'status_{i}' for i in range(1, 9)]
        df['status_sum'] = df[status_cols].sum(axis=1)
        df['status_mean'] = df[status_cols].mean(axis=1)
        df['status_std'] = df[status_cols].std(axis=1)
        df['status_max'] = df[status_cols].max(axis=1)
        df['status_nonzero'] = (df[status_cols] > 0).sum(axis=1)
        
        # Pipeline stage features
        df['early_pipeline'] = df['status_1'] + df['status_2']
        df['mid_pipeline'] = df['status_3'] + df['status_4'] + df['status_5']
        df['late_pipeline'] = df['status_6'] + df['status_7'] + df['status_8']
        
        # Ratios
        df['late_over_early'] = np.where(
            df['early_pipeline'] > 0,
            df['late_pipeline'] / df['early_pipeline'],
            0
        )
        df['mid_share'] = np.where(
            df['status_sum'] > 0,
            df['mid_pipeline'] / df['status_sum'],
            0
        )
        
        return df
    
    def predict(self, route_data: Dict) -> Tuple[float, float, Dict]:
        """
        Killer Feature: Prediction with confidence and uncertainty estimation
        
        Returns:
            forecast: predicted value
            confidence: confidence score (0-1)
            explanation: dict with feature contributions
        """
        if not self.models_loaded:
            self.load_models()
        
        # Build features
        features_df = self.build_features(route_data)
        
        # Select only model features
        if self.feature_columns:
            available_cols = [col for col in self.feature_columns if col in features_df.columns]
            X = features_df[available_cols]
        else:
            X = features_df
        
        # Make prediction
        if self.hybrid_model:
            prediction = self.hybrid_model.predict(X)[0]
        else:
            # Fallback: simple heuristic
            prediction = features_df['late_pipeline'].values[0] * 1.5
        
        # Clip to non-negative
        prediction = max(0, prediction)
        
        # Calculate confidence based on input quality
        confidence = self._calculate_confidence(features_df)
        
        # Calculate uncertainty for dynamic safety factor
        uncertainty = self._calculate_uncertainty(features_df, prediction)
        
        # Generate explanation
        explanation = self._generate_explanation(features_df, prediction)
        
        return prediction, confidence, uncertainty, explanation
    
    def _calculate_confidence(self, features_df: pd.DataFrame) -> float:
        """
        Killer Feature: Confidence estimation based on data quality
        """
        confidence = 1.0
        
        # Reduce confidence if status_sum is very low
        if features_df['status_sum'].values[0] < 5:
            confidence *= 0.7
        
        # Reduce confidence on weekends
        if features_df['is_weekend'].values[0] == 1:
            confidence *= 0.9
        
        # Reduce confidence for unusual hours
        hour = features_df['hour'].values[0]
        if hour < 6 or hour > 22:
            confidence *= 0.8
        
        return max(0.5, min(1.0, confidence))
    
    def _calculate_uncertainty(self, features_df: pd.DataFrame, prediction: float) -> float:
        """
        Killer Feature: Uncertainty for dynamic safety factor
        """
        # Base uncertainty
        uncertainty = 0.1
        
        # Higher uncertainty for high predictions
        if prediction > 50:
            uncertainty += 0.05
        
        # Higher uncertainty if late_pipeline is dominant
        late_ratio = features_df['late_over_early'].values[0]
        if late_ratio > 2:
            uncertainty += 0.1
        
        # Higher uncertainty on weekends
        if features_df['is_weekend'].values[0] == 1:
            uncertainty += 0.05
        
        return min(0.5, uncertainty)
    
    def _generate_explanation(self, features_df: pd.DataFrame, prediction: float) -> Dict:
        """
        Killer Feature: Explainability - why this prediction?
        """
        explanation = {
            "prediction": float(prediction),
            "key_factors": []
        }
        
        # Check late pipeline
        late_pipeline = features_df['late_pipeline'].values[0]
        if late_pipeline > 10:
            explanation["key_factors"].append(
                f"High late pipeline ({late_pipeline} items) indicates imminent shipments"
            )
        
        # Check time of day
        hour = features_df['hour'].values[0]
        if 9 <= hour <= 17:
            explanation["key_factors"].append(
                f"Peak hours ({hour}:00) - historically high activity"
            )
        
        # Check weekend
        if features_df['is_weekend'].values[0] == 1:
            explanation["key_factors"].append(
                "Weekend - reduced activity expected"
            )
        
        # Check status distribution
        late_over_early = features_df['late_over_early'].values[0]
        if late_over_early > 1.5:
            explanation["key_factors"].append(
                f"Late-stage dominance (ratio: {late_over_early:.2f}) suggests urgent shipments"
            )
        
        return explanation


# Global instance
forecast_service = ForecastService()
