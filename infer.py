from __future__ import annotations

import argparse
import os
from pathlib import Path
import warnings

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import joblib
import numpy as np
import pandas as pd

from src.features import (
    build_features,
    build_horizon_feature_frame,
    build_model_matrix,
    build_office_history_frame,
)
from src.utils import clip_and_scale, clip_predictions, load_data, make_submission


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inference for direct LightGBM baseline.")
    parser.add_argument("--train-path", type=str, default="train_team_track.parquet")
    parser.add_argument("--test-path", type=str, default="test_team_track.parquet")
    parser.add_argument("--models-dir", type=str, default="models")
    parser.add_argument("--submission-path", type=str, default="submission.csv")
    parser.add_argument("--max-routes", type=int, default=None, help="Optional deterministic subset for smoke tests.")
    return parser.parse_args()


def predict_test(
    train_feature_df: pd.DataFrame,
    test_df: pd.DataFrame,
    models_dir: str | Path,
    artifact: dict[str, object],
) -> pd.DataFrame:
    models_dir = Path(models_dir)
    base_feature_cols = list(artifact["base_feature_cols"])
    horizon_feature_cols = list(artifact.get("horizon_feature_cols", []))
    categorical_features = list(artifact.get("categorical_features", []))
    horizons = sorted(int(h) for h in artifact["horizons"])
    freq_minutes = int(artifact["freq_minutes"])
    target_col = str(artifact["target_col"])
    experiment_config = dict(artifact.get("experiment_config", {}))
    per_horizon_postprocess = dict(artifact.get("per_horizon_postprocess", {}))

    office_history_frame = build_office_history_frame(train_feature_df, target_col=target_col)

    last_history = (
        train_feature_df.sort_values(["route_id", "source_timestamp"])
        .groupby("route_id", sort=False)
        .tail(1)
        .copy()
    )
    history_base_cols = [
        "route_id",
        "office_from_id",
        "source_timestamp",
        *[col for col in base_feature_cols if col not in {"route_id", "office_from_id"}],
    ]
    base_lookup = last_history[history_base_cols].copy()

    test_frame = test_df.merge(
        base_lookup,
        on=["route_id", "office_from_id"],
        how="left",
        validate="many_to_one",
    )

    if test_frame["source_timestamp"].isna().any():
        raise ValueError("Some test rows do not have corresponding route history.")

    horizon_float = (
        (pd.to_datetime(test_frame["timestamp"]) - pd.to_datetime(test_frame["source_timestamp"]))
        / pd.Timedelta(minutes=freq_minutes)
    ).astype(np.float32)

    rounded_horizon = np.rint(horizon_float).astype(np.int16)
    if not np.allclose(horizon_float.to_numpy(), rounded_horizon.astype(np.float32), atol=1e-6):
        raise ValueError("Test timestamps are not aligned to the expected direct horizons.")

    test_frame["horizon"] = rounded_horizon
    unknown_horizons = sorted(set(test_frame["horizon"].unique()) - set(horizons))
    if unknown_horizons:
        raise ValueError(f"Found unsupported horizons in test: {unknown_horizons}")

    prediction_parts = []
    for horizon in horizons:
        model_path = models_dir / f"model_h{horizon}.joblib"
        model = joblib.load(model_path)

        horizon_slice = test_frame[test_frame["horizon"] == horizon].copy()
        if horizon_slice.empty:
            continue

        if horizon_feature_cols:
            horizon_feature_frame = build_horizon_feature_frame(
                df=train_feature_df,
                office_history_frame=office_history_frame,
                horizon=horizon,
                target_col=target_col,
                use_aligned_lags=bool(experiment_config.get("use_aligned_lags", False)),
                use_route_priors=bool(experiment_config.get("use_route_priors", False)),
                use_office_features=bool(experiment_config.get("use_office_features", False)),
                use_share_features=bool(experiment_config.get("use_share_features", False)),
            )
            extra_lookup = pd.concat(
                [
                    last_history[["route_id", "office_from_id"]].reset_index(drop=True),
                    horizon_feature_frame.loc[last_history.index, horizon_feature_cols].reset_index(drop=True),
                ],
                axis=1,
            )
            horizon_slice = horizon_slice.merge(
                extra_lookup,
                on=["route_id", "office_from_id"],
                how="left",
                validate="many_to_one",
            )

        X_test = build_model_matrix(
            horizon_slice,
            base_feature_cols=base_feature_cols,
            horizon=horizon,
            horizon_feature_cols=horizon_feature_cols,
            categorical_features=categorical_features,
            source_ts_col="source_timestamp",
            future_ts_col="timestamp",
            freq_minutes=freq_minutes,
        )

        raw_pred = np.asarray(
            model.predict(X_test, num_iteration=getattr(model, "best_iteration_", None)),
            dtype=np.float32,
        )

        postprocess = dict(per_horizon_postprocess.get(str(horizon), {}))
        pred_model = clip_and_scale(raw_pred, float(postprocess.get("alpha_model", 1.0)))
        pred_final = pred_model

        if bool(experiment_config.get("use_blend", False)):
            daily_naive = clip_predictions(np.nan_to_num(horizon_slice["target_same_slot_day"], nan=0.0))
            weekly_naive = clip_predictions(np.nan_to_num(horizon_slice["target_same_slot_week"], nan=0.0))
            blend_weights = dict(
                postprocess.get(
                    "blend_weights",
                    {"w_lgbm": 1.0, "w_daily": 0.0, "w_weekly": 0.0},
                )
            )
            blend_raw = (
                pred_model * np.float32(blend_weights.get("w_lgbm", 1.0))
                + daily_naive * np.float32(blend_weights.get("w_daily", 0.0))
                + weekly_naive * np.float32(blend_weights.get("w_weekly", 0.0))
            ).astype(np.float32)
            pred_final = clip_and_scale(blend_raw, float(postprocess.get("blend_alpha", 1.0)))

        horizon_slice["y_pred"] = pred_final
        prediction_parts.append(horizon_slice[["id", "route_id", "timestamp", "y_pred"]])

    prediction_df = pd.concat(prediction_parts, ignore_index=True)
    prediction_df = prediction_df.sort_values("id").reset_index(drop=True)

    if len(prediction_df) != len(test_df):
        raise ValueError("Predictions count does not match test rows.")

    return prediction_df


def main() -> None:
    warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

    args = parse_args()
    models_dir = Path(args.models_dir)
    artifact = joblib.load(models_dir / "artifacts.joblib")

    train_df, test_df = load_data(args.train_path, args.test_path, max_routes=args.max_routes)
    train_feature_df = build_features(train_df, target_col=str(artifact["target_col"]))
    prediction_df = predict_test(train_feature_df, test_df, models_dir=models_dir, artifact=artifact)
    submission = make_submission(prediction_df, args.submission_path)

    print(f"Loaded artifacts from: {models_dir / 'artifacts.joblib'}")
    print(f"Saved submission to:   {args.submission_path}")
    print(f"Submission rows:       {len(submission)}")


if __name__ == "__main__":
    main()
