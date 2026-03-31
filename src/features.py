from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from src.utils import FREQ_MINUTES, TARGET_COL, get_status_columns, reduce_memory_usage, safe_divide


TARGET_LAGS = (1, 2, 3, 4, 6, 8, 12, 24, 48, 96, 336)
TARGET_ROLL_WINDOWS = (3, 6, 12, 24, 48, 96, 336)
STATUS_ROLL_WINDOWS = (3, 12, 24, 48, 336)
OFFICE_LAGS = (1, 2, 4, 12, 24, 48)
OFFICE_ROLL_WINDOWS = (3, 12, 48, 336)


def get_calendar_feature_names(prefix: str) -> list[str]:
    return [
        f"{prefix}_month",
        f"{prefix}_day",
        f"{prefix}_hour",
        f"{prefix}_minute",
        f"{prefix}_halfhour_slot",
        f"{prefix}_dayofweek",
        f"{prefix}_is_weekend",
        f"{prefix}_weekofyear",
        f"{prefix}_slot_sin",
        f"{prefix}_slot_cos",
        f"{prefix}_dow_sin",
        f"{prefix}_dow_cos",
    ]


def _calendar_feature_dict(ts: pd.Series, prefix: str) -> dict[str, np.ndarray]:
    ts = pd.to_datetime(ts)
    halfhour_slot = (ts.dt.hour * 2 + (ts.dt.minute // 30)).astype(np.int16)
    dayofweek = ts.dt.dayofweek.astype(np.int8)

    return {
        f"{prefix}_month": ts.dt.month.astype(np.int8).to_numpy(),
        f"{prefix}_day": ts.dt.day.astype(np.int8).to_numpy(),
        f"{prefix}_hour": ts.dt.hour.astype(np.int8).to_numpy(),
        f"{prefix}_minute": ts.dt.minute.astype(np.int8).to_numpy(),
        f"{prefix}_halfhour_slot": halfhour_slot.to_numpy(),
        f"{prefix}_dayofweek": dayofweek.to_numpy(),
        f"{prefix}_is_weekend": (dayofweek >= 5).astype(np.int8).to_numpy(),
        f"{prefix}_weekofyear": ts.dt.isocalendar().week.astype(np.int16).to_numpy(),
        f"{prefix}_slot_sin": np.sin(2.0 * np.pi * halfhour_slot.to_numpy(dtype=np.float32) / 48.0).astype(np.float32),
        f"{prefix}_slot_cos": np.cos(2.0 * np.pi * halfhour_slot.to_numpy(dtype=np.float32) / 48.0).astype(np.float32),
        f"{prefix}_dow_sin": np.sin(2.0 * np.pi * dayofweek.to_numpy(dtype=np.float32) / 7.0).astype(np.float32),
        f"{prefix}_dow_cos": np.cos(2.0 * np.pi * dayofweek.to_numpy(dtype=np.float32) / 7.0).astype(np.float32),
    }


def add_calendar_features(df: pd.DataFrame, ts_col: str, prefix: str) -> pd.DataFrame:
    feature_map = _calendar_feature_dict(df[ts_col], prefix=prefix)
    for col, values in feature_map.items():
        df[col] = values
    return df


def _add_status_aggregates(df: pd.DataFrame, status_cols: list[str]) -> pd.DataFrame:
    status_frame = df[status_cols]
    df["status_sum"] = status_frame.sum(axis=1).astype(np.float32)
    df["status_mean"] = status_frame.mean(axis=1).astype(np.float32)
    df["status_max"] = status_frame.max(axis=1).astype(np.float32)
    df["status_min"] = status_frame.min(axis=1).astype(np.float32)
    df["status_nonzero_cnt"] = status_frame.gt(0).sum(axis=1).astype(np.float32)
    df["status_std"] = status_frame.std(axis=1).astype(np.float32)

    for col in status_cols:
        share_col = f"{col}_share"
        df[share_col] = safe_divide(df[col], df["status_sum"])

    return df


def _group_rolling(series: pd.Series, group_keys: pd.Series, window: int, stat: str) -> pd.Series:
    rolled = getattr(
        series.groupby(group_keys, sort=False).rolling(window=window, min_periods=1),
        stat,
    )()
    return rolled.reset_index(level=0, drop=True)


def _add_route_history_features(df: pd.DataFrame, route_col: str, target_col: str) -> pd.DataFrame:
    route_group = df.groupby(route_col, sort=False)

    for lag in TARGET_LAGS:
        df[f"target_lag_{lag}"] = route_group[target_col].shift(lag).astype(np.float32)
        df[f"status_sum_lag_{lag}"] = route_group["status_sum"].shift(lag).astype(np.float32)

    target_shifted = route_group[target_col].shift(1).astype(np.float32)
    status_shifted = route_group["status_sum"].shift(1).astype(np.float32)

    for window in TARGET_ROLL_WINDOWS:
        df[f"target_roll_mean_{window}"] = _group_rolling(target_shifted, df[route_col], window, "mean").astype(np.float32)
        df[f"target_roll_std_{window}"] = _group_rolling(target_shifted, df[route_col], window, "std").astype(np.float32)
        df[f"target_roll_min_{window}"] = _group_rolling(target_shifted, df[route_col], window, "min").astype(np.float32)
        df[f"target_roll_max_{window}"] = _group_rolling(target_shifted, df[route_col], window, "max").astype(np.float32)

    for window in STATUS_ROLL_WINDOWS:
        df[f"status_sum_roll_mean_{window}"] = _group_rolling(status_shifted, df[route_col], window, "mean").astype(np.float32)
        df[f"status_sum_roll_std_{window}"] = _group_rolling(status_shifted, df[route_col], window, "std").astype(np.float32)
        df[f"status_sum_roll_min_{window}"] = _group_rolling(status_shifted, df[route_col], window, "min").astype(np.float32)
        df[f"status_sum_roll_max_{window}"] = _group_rolling(status_shifted, df[route_col], window, "max").astype(np.float32)

    df["target_diff_1"] = (df["target_lag_1"] - df["target_lag_2"]).astype(np.float32)
    df["target_diff_4"] = (df["target_lag_1"] - df["target_lag_4"]).astype(np.float32)
    df["target_vs_roll24"] = (df["target_lag_1"] - df["target_roll_mean_24"]).astype(np.float32)
    df["status_sum_diff_1"] = (df["status_sum_lag_1"] - df["status_sum_lag_2"]).astype(np.float32)
    df["status_sum_diff_4"] = (df["status_sum_lag_1"] - df["status_sum_lag_4"]).astype(np.float32)
    df["status_sum_vs_roll24"] = (df["status_sum_lag_1"] - df["status_sum_roll_mean_24"]).astype(np.float32)
    return df


def _build_office_frame(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    office_frame = (
        df.groupby(["office_from_id", "source_timestamp"], as_index=False)
        .agg(
            office_target_sum=(target_col, "sum"),
            office_status_sum=("status_sum", "sum"),
        )
        .sort_values(["office_from_id", "source_timestamp"])
        .reset_index(drop=True)
    )

    office_group = office_frame.groupby("office_from_id", sort=False)

    for lag in OFFICE_LAGS:
        office_frame[f"office_target_sum_lag_{lag}"] = office_group["office_target_sum"].shift(lag).astype(np.float32)
        office_frame[f"office_status_sum_lag_{lag}"] = office_group["office_status_sum"].shift(lag).astype(np.float32)

    office_target_shifted = office_group["office_target_sum"].shift(1).astype(np.float32)
    office_status_shifted = office_group["office_status_sum"].shift(1).astype(np.float32)

    for window in OFFICE_ROLL_WINDOWS:
        office_frame[f"office_target_roll_mean_{window}"] = _group_rolling(
            office_target_shifted,
            office_frame["office_from_id"],
            window,
            "mean",
        ).astype(np.float32)
        office_frame[f"office_target_roll_std_{window}"] = _group_rolling(
            office_target_shifted,
            office_frame["office_from_id"],
            window,
            "std",
        ).astype(np.float32)
        office_frame[f"office_status_roll_mean_{window}"] = _group_rolling(
            office_status_shifted,
            office_frame["office_from_id"],
            window,
            "mean",
        ).astype(np.float32)
        office_frame[f"office_status_roll_std_{window}"] = _group_rolling(
            office_status_shifted,
            office_frame["office_from_id"],
            window,
            "std",
        ).astype(np.float32)

    return office_frame


def build_features(train_df: pd.DataFrame, target_col: str = TARGET_COL) -> pd.DataFrame:
    df = train_df.sort_values(["route_id", "timestamp"]).reset_index(drop=True).copy()
    df = df.rename(columns={"timestamp": "source_timestamp"})

    status_cols = get_status_columns(df)
    df = _add_status_aggregates(df, status_cols=status_cols)
    df = add_calendar_features(df, ts_col="source_timestamp", prefix="source")
    df = _add_route_history_features(df, route_col="route_id", target_col=target_col)

    office_frame = _build_office_frame(df, target_col=target_col)
    df = df.merge(office_frame, on=["office_from_id", "source_timestamp"], how="left", validate="many_to_one")

    df["route_status_share_current"] = safe_divide(df["status_sum"], df["office_status_sum"])
    for lag in (1, 24):
        df[f"route_target_share_lag_{lag}"] = safe_divide(
            df[f"target_lag_{lag}"],
            df[f"office_target_sum_lag_{lag}"],
        )
        df[f"route_status_share_lag_{lag}"] = safe_divide(
            df[f"status_sum_lag_{lag}"],
            df[f"office_status_sum_lag_{lag}"],
        )

    df = reduce_memory_usage(df, skip_cols=["source_timestamp"])
    return df


def make_targets(
    df: pd.DataFrame,
    target_col: str = TARGET_COL,
    horizons: Iterable[int] = tuple(range(1, 11)),
) -> pd.DataFrame:
    route_group = df.groupby("route_id", sort=False)
    for horizon in horizons:
        df[f"target_h_{horizon}"] = route_group[target_col].shift(-horizon).astype(np.float32)
    return df


def build_model_matrix(
    df: pd.DataFrame,
    base_feature_cols: list[str],
    horizon: int,
    source_ts_col: str = "source_timestamp",
    future_ts_col: str | None = None,
    freq_minutes: int = FREQ_MINUTES,
) -> pd.DataFrame:
    matrix = df[base_feature_cols].copy()
    if future_ts_col is None:
        future_ts = pd.to_datetime(df[source_ts_col]) + pd.to_timedelta(horizon * freq_minutes, unit="m")
    else:
        future_ts = pd.to_datetime(df[future_ts_col])

    feature_map = _calendar_feature_dict(future_ts, prefix="future")
    for col, values in feature_map.items():
        matrix[col] = values

    return reduce_memory_usage(matrix)
