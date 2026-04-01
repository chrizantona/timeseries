from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from src.metrics import competition_score, relative_bias, wape


TARGET_COL = "target_2h"
FREQ_MINUTES = 30
FORECAST_HORIZONS = tuple(range(1, 11))
EPSILON = 1e-6


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(data: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fp:
        return json.load(fp)


def safe_divide(
    numerator: pd.Series | np.ndarray,
    denominator: pd.Series | np.ndarray,
    fill_value: float = 0.0,
) -> np.ndarray:
    numerator_arr = np.asarray(numerator, dtype=np.float32)
    denominator_arr = np.asarray(denominator, dtype=np.float32)
    result = np.divide(
        numerator_arr,
        denominator_arr,
        out=np.full_like(numerator_arr, fill_value, dtype=np.float32),
        where=np.abs(denominator_arr) > 1e-12,
    )
    return result.astype(np.float32)


def clip_predictions(predictions: Iterable[float]) -> np.ndarray:
    return np.clip(np.asarray(predictions, dtype=np.float32), 0.0, None).astype(np.float32)


def clip_and_scale(predictions: Iterable[float], alpha: float) -> np.ndarray:
    scaled = np.asarray(predictions, dtype=np.float32) * np.float32(alpha)
    return clip_predictions(scaled)


def get_status_columns(df: pd.DataFrame) -> list[str]:
    return sorted(col for col in df.columns if col.startswith("status_"))


def reduce_memory_usage(df: pd.DataFrame, skip_cols: Iterable[str] | None = None) -> pd.DataFrame:
    skip_cols = set(skip_cols or [])

    for col in df.columns:
        if col in skip_cols:
            continue

        col_data = df[col]
        if pd.api.types.is_datetime64_any_dtype(col_data) or pd.api.types.is_categorical_dtype(col_data):
            continue

        if pd.api.types.is_integer_dtype(col_data):
            df[col] = pd.to_numeric(col_data, downcast="integer")
        elif pd.api.types.is_float_dtype(col_data):
            df[col] = pd.to_numeric(col_data, downcast="float")
        elif pd.api.types.is_bool_dtype(col_data):
            df[col] = col_data.astype(np.int8)

    return df


def load_data(
    train_path: str | Path,
    test_path: str | Path,
    max_routes: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_df = pd.read_parquet(train_path)
    test_df = pd.read_parquet(test_path)

    train_df["timestamp"] = pd.to_datetime(train_df["timestamp"])
    test_df["timestamp"] = pd.to_datetime(test_df["timestamp"])

    train_df = train_df.sort_values(["route_id", "timestamp"]).reset_index(drop=True)
    test_df = test_df.sort_values(["route_id", "timestamp"]).reset_index(drop=True)

    route_office = train_df[["route_id", "office_from_id"]].drop_duplicates()
    if route_office["route_id"].duplicated().any():
        raise ValueError("route_id must map to exactly one office_from_id.")

    if "office_from_id" not in test_df.columns:
        test_df = test_df.merge(route_office, on="route_id", how="left", validate="many_to_one")

    if test_df["office_from_id"].isna().any():
        missing_routes = test_df.loc[test_df["office_from_id"].isna(), "route_id"].unique()[:10]
        raise ValueError(f"Failed to recover office_from_id for some test routes: {missing_routes}")

    if max_routes is not None:
        keep_routes = sorted(train_df["route_id"].unique())[:max_routes]
        train_df = train_df[train_df["route_id"].isin(keep_routes)].reset_index(drop=True)
        test_df = test_df[test_df["route_id"].isin(keep_routes)].reset_index(drop=True)

    train_df = reduce_memory_usage(train_df, skip_cols=["timestamp"])
    test_df = reduce_memory_usage(test_df, skip_cols=["timestamp"])
    return train_df, test_df


def time_split(
    df: pd.DataFrame,
    horizon: int,
    valid_days: int = 7,
    freq_minutes: int = FREQ_MINUTES,
    source_ts_col: str = "source_timestamp",
) -> dict[str, pd.Series | pd.Timestamp]:
    max_timestamp = pd.to_datetime(df[source_ts_col]).max()
    step = pd.Timedelta(minutes=freq_minutes)
    valid_start = max_timestamp - pd.Timedelta(days=valid_days) + step
    fit_cutoff = valid_start - (step * horizon)

    fit_mask = df[source_ts_col] < fit_cutoff
    valid_mask = df[source_ts_col] >= valid_start

    return {
        "fit_mask": fit_mask,
        "valid_mask": valid_mask,
        "fit_cutoff": fit_cutoff,
        "valid_start": valid_start,
    }


def summarize_metrics(y_true: Iterable[float], y_pred: Iterable[float]) -> dict[str, float]:
    return {
        "wape": float(wape(y_true, y_pred)),
        "relative_bias": float(relative_bias(y_true, y_pred)),
        "score": float(competition_score(y_true, y_pred)),
    }


def tune_alpha(
    y_true: Iterable[float],
    y_pred_raw: Iterable[float],
    alpha_min: float = 0.90,
    alpha_max: float = 1.10,
    alpha_step: float = 0.001,
) -> tuple[float, list[dict[str, float]]]:
    y_true_arr = np.asarray(y_true, dtype=np.float32)
    y_pred_arr = np.asarray(y_pred_raw, dtype=np.float32)

    tried_scores: list[dict[str, float]] = []
    best_alpha = 1.0
    best_score = np.inf

    for alpha in np.arange(alpha_min, alpha_max + alpha_step / 2.0, alpha_step, dtype=np.float32):
        calibrated = clip_and_scale(y_pred_arr, float(alpha))
        score = competition_score(y_true_arr, calibrated)
        tried_scores.append({"alpha": float(alpha), "score": float(score)})
        if score < best_score:
            best_score = score
            best_alpha = float(alpha)

    return best_alpha, tried_scores


def tune_global_alpha(
    y_true: Iterable[float],
    y_pred_raw: Iterable[float],
    alpha_min: float = 0.90,
    alpha_max: float = 1.10,
    alpha_step: float = 0.001,
) -> tuple[float, list[dict[str, float]]]:
    return tune_alpha(
        y_true=y_true,
        y_pred_raw=y_pred_raw,
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        alpha_step=alpha_step,
    )


def search_blend_weights(
    y_true: Iterable[float],
    pred_lgbm: Iterable[float],
    pred_daily: Iterable[float],
    pred_weekly: Iterable[float],
    weight_step: float = 0.05,
) -> tuple[dict[str, float], dict[str, float]]:
    if weight_step <= 0 or weight_step > 1:
        raise ValueError("weight_step must be in the interval (0, 1].")

    grid_size = int(round(1.0 / weight_step))
    if not np.isclose(grid_size * weight_step, 1.0, atol=1e-8):
        raise ValueError("weight_step must divide 1.0 exactly, e.g. 0.5, 0.25, 0.2, 0.1, 0.05.")

    y_true_arr = np.asarray(y_true, dtype=np.float32)
    pred_lgbm_arr = clip_predictions(pred_lgbm)
    pred_daily_arr = clip_predictions(pred_daily)
    pred_weekly_arr = clip_predictions(pred_weekly)

    best_weights = {"w_lgbm": 1.0, "w_daily": 0.0, "w_weekly": 0.0}
    best_metrics = summarize_metrics(y_true_arr, pred_lgbm_arr)

    for lgbm_units in range(grid_size + 1):
        for daily_units in range(grid_size - lgbm_units + 1):
            weekly_units = grid_size - lgbm_units - daily_units

            w_lgbm = lgbm_units / grid_size
            w_daily = daily_units / grid_size
            w_weekly = weekly_units / grid_size

            blended = (
                pred_lgbm_arr * np.float32(w_lgbm)
                + pred_daily_arr * np.float32(w_daily)
                + pred_weekly_arr * np.float32(w_weekly)
            ).astype(np.float32)
            metrics = summarize_metrics(y_true_arr, blended)
            if metrics["score"] < best_metrics["score"]:
                best_metrics = metrics
                best_weights = {
                    "w_lgbm": float(w_lgbm),
                    "w_daily": float(w_daily),
                    "w_weekly": float(w_weekly),
                }

    return best_weights, best_metrics


def make_submission(prediction_df: pd.DataFrame, submission_path: str | Path) -> pd.DataFrame:
    submission = prediction_df[["id", "y_pred"]].copy()
    submission = submission.sort_values("id").reset_index(drop=True)

    if submission["id"].duplicated().any():
        raise ValueError("Submission contains duplicate ids.")
    if submission["y_pred"].isna().any():
        raise ValueError("Submission contains missing predictions.")

    submission["y_pred"] = np.clip(submission["y_pred"].astype(np.float32), 0.0, None)
    submission.to_csv(submission_path, index=False)
    return submission
