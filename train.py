from __future__ import annotations

import argparse
import os
from pathlib import Path
import warnings

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from src.features import build_features, build_model_matrix, get_calendar_feature_names, make_targets
from src.metrics import competition_score, relative_bias, wape
from src.utils import (
    FORECAST_HORIZONS,
    TARGET_COL,
    clip_and_scale,
    ensure_dir,
    load_data,
    make_submission,
    save_json,
    time_split,
    tune_global_alpha,
)


DEFAULT_MODEL_PARAMS = {
    "objective": "l1",
    "n_estimators": 1500,
    "learning_rate": 0.03,
    "num_leaves": 127,
    "min_child_samples": 100,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": -1,
    "verbosity": -1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train direct LightGBM baseline for target_2h.")
    parser.add_argument("--train-path", type=str, default="train_team_track.parquet")
    parser.add_argument("--test-path", type=str, default="test_team_track.parquet")
    parser.add_argument("--models-dir", type=str, default="models")
    parser.add_argument("--outputs-dir", type=str, default="outputs")
    parser.add_argument("--submission-path", type=str, default="outputs/submission_from_train.csv")
    parser.add_argument("--valid-days", type=int, default=7)
    parser.add_argument("--freq-minutes", type=int, default=30)
    parser.add_argument("--early-stopping-rounds", type=int, default=100)
    parser.add_argument("--alpha-min", type=float, default=0.90)
    parser.add_argument("--alpha-max", type=float, default=1.10)
    parser.add_argument("--alpha-step", type=float, default=0.001)
    parser.add_argument("--n-estimators", type=int, default=DEFAULT_MODEL_PARAMS["n_estimators"])
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_MODEL_PARAMS["learning_rate"])
    parser.add_argument("--num-leaves", type=int, default=DEFAULT_MODEL_PARAMS["num_leaves"])
    parser.add_argument("--min-child-samples", type=int, default=DEFAULT_MODEL_PARAMS["min_child_samples"])
    parser.add_argument("--subsample", type=float, default=DEFAULT_MODEL_PARAMS["subsample"])
    parser.add_argument("--colsample-bytree", type=float, default=DEFAULT_MODEL_PARAMS["colsample_bytree"])
    parser.add_argument("--reg-alpha", type=float, default=DEFAULT_MODEL_PARAMS["reg_alpha"])
    parser.add_argument("--reg-lambda", type=float, default=DEFAULT_MODEL_PARAMS["reg_lambda"])
    parser.add_argument("--n-jobs", type=int, default=DEFAULT_MODEL_PARAMS["n_jobs"])
    parser.add_argument("--max-routes", type=int, default=None, help="Optional deterministic subset for smoke tests.")
    parser.add_argument("--horizons", type=int, nargs="+", default=list(FORECAST_HORIZONS))
    return parser.parse_args()


def build_model_params(args: argparse.Namespace) -> dict[str, float | int | str]:
    params = DEFAULT_MODEL_PARAMS.copy()
    params.update(
        {
            "n_estimators": args.n_estimators,
            "learning_rate": args.learning_rate,
            "num_leaves": args.num_leaves,
            "min_child_samples": args.min_child_samples,
            "subsample": args.subsample,
            "colsample_bytree": args.colsample_bytree,
            "reg_alpha": args.reg_alpha,
            "reg_lambda": args.reg_lambda,
            "n_jobs": args.n_jobs,
        }
    )
    return params


def train_one_horizon(
    df: pd.DataFrame,
    horizon: int,
    base_feature_cols: list[str],
    categorical_features: list[str],
    model_params: dict[str, float | int | str],
    valid_days: int,
    freq_minutes: int,
    early_stopping_rounds: int,
) -> dict[str, object]:
    target_name = f"target_h_{horizon}"
    split = time_split(df, horizon=horizon, valid_days=valid_days, freq_minutes=freq_minutes)

    fit_mask = split["fit_mask"] & df[target_name].notna()
    valid_mask = split["valid_mask"] & df[target_name].notna()

    fit_df = df.loc[fit_mask].copy()
    valid_df = df.loc[valid_mask].copy()

    X_fit = build_model_matrix(fit_df, base_feature_cols=base_feature_cols, horizon=horizon, freq_minutes=freq_minutes)
    X_valid = build_model_matrix(valid_df, base_feature_cols=base_feature_cols, horizon=horizon, freq_minutes=freq_minutes)
    y_fit = fit_df[target_name].astype(np.float32).to_numpy()
    y_valid = valid_df[target_name].astype(np.float32).to_numpy()

    model = lgb.LGBMRegressor(**model_params)
    model.fit(
        X_fit,
        y_fit,
        eval_set=[(X_valid, y_valid)],
        eval_metric="l1",
        categorical_feature=categorical_features,
        callbacks=[
            lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=False),
            lgb.log_evaluation(period=100),
        ],
    )

    valid_pred_raw = model.predict(X_valid, num_iteration=model.best_iteration_)
    valid_pred_clip = np.clip(valid_pred_raw, 0.0, None).astype(np.float32)

    feature_importance = pd.DataFrame(
        {
            "feature": X_fit.columns,
            "importance_gain": model.booster_.feature_importance(importance_type="gain"),
            "importance_split": model.booster_.feature_importance(importance_type="split"),
        }
    ).sort_values(["importance_gain", "importance_split"], ascending=False)

    valid_predictions = valid_df[["route_id", "office_from_id", "source_timestamp"]].copy()
    valid_predictions["horizon"] = horizon
    valid_predictions["target_timestamp"] = valid_predictions["source_timestamp"] + pd.to_timedelta(horizon * freq_minutes, unit="m")
    valid_predictions["y_true"] = y_valid
    valid_predictions["y_pred_raw"] = np.asarray(valid_pred_raw, dtype=np.float32)
    valid_predictions["y_pred_clip"] = valid_pred_clip

    metrics = {
        "horizon": horizon,
        "fit_rows": int(fit_mask.sum()),
        "valid_rows": int(valid_mask.sum()),
        "fit_cutoff": str(split["fit_cutoff"]),
        "valid_start": str(split["valid_start"]),
        "best_iteration": int(model.best_iteration_ or model.n_estimators),
        "wape_clip": float(wape(y_valid, valid_pred_clip)),
        "relative_bias_clip": float(relative_bias(y_valid, valid_pred_clip)),
        "score_clip": float(competition_score(y_valid, valid_pred_clip)),
    }

    return {
        "model": model,
        "feature_importance": feature_importance,
        "valid_predictions": valid_predictions,
        "metrics": metrics,
    }


def _build_artifact(
    args: argparse.Namespace,
    base_feature_cols: list[str],
    categorical_features: list[str],
    alpha: float,
    horizons: list[int],
    validation_metrics: dict[str, object],
) -> dict[str, object]:
    feature_columns = base_feature_cols + get_calendar_feature_names(prefix="future")
    return {
        "target_col": TARGET_COL,
        "horizons": horizons,
        "freq_minutes": args.freq_minutes,
        "valid_days": args.valid_days,
        "alpha": float(alpha),
        "base_feature_cols": base_feature_cols,
        "feature_columns": feature_columns,
        "categorical_features": categorical_features,
        "validation_metrics": validation_metrics,
    }


def main() -> None:
    warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

    args = parse_args()
    horizons = sorted(set(int(h) for h in args.horizons))

    models_dir = ensure_dir(args.models_dir)
    outputs_dir = ensure_dir(args.outputs_dir)

    print("Loading train/test parquet...")
    train_df, test_df = load_data(args.train_path, args.test_path, max_routes=args.max_routes)
    print(f"train shape: {train_df.shape}")
    print(f"test shape:  {test_df.shape}")
    print(f"horizons:    {horizons}")

    print("Building base features...")
    feature_df = build_features(train_df, target_col=TARGET_COL)
    feature_df = make_targets(feature_df, target_col=TARGET_COL, horizons=horizons)

    target_cols = {f"target_h_{h}" for h in horizons}
    excluded_cols = {"source_timestamp", TARGET_COL, *target_cols}
    base_feature_cols = [col for col in feature_df.columns if col not in excluded_cols]
    categorical_features = [col for col in ("route_id", "office_from_id") if col in base_feature_cols]

    model_params = build_model_params(args)
    horizon_results: list[dict[str, object]] = []
    validation_parts: list[pd.DataFrame] = []

    for horizon in tqdm(horizons, desc="Training horizons"):
        result = train_one_horizon(
            df=feature_df,
            horizon=horizon,
            base_feature_cols=base_feature_cols,
            categorical_features=categorical_features,
            model_params=model_params,
            valid_days=args.valid_days,
            freq_minutes=args.freq_minutes,
            early_stopping_rounds=args.early_stopping_rounds,
        )
        horizon_results.append(result)
        validation_parts.append(result["valid_predictions"])

        model_path = models_dir / f"model_h{horizon}.joblib"
        joblib.dump(result["model"], model_path)

        importance_path = outputs_dir / f"feature_importance_h{horizon}.csv"
        result["feature_importance"].to_csv(importance_path, index=False)

        print(f"\nTop features for horizon {horizon}:")
        print(result["feature_importance"].head(10).to_string(index=False))
        print(f"validation score (clipped): {result['metrics']['score_clip']:.6f}")

    validation_df = pd.concat(validation_parts, ignore_index=True)
    best_alpha, alpha_trials = tune_global_alpha(
        validation_df["y_true"].to_numpy(),
        validation_df["y_pred_raw"].to_numpy(),
        alpha_min=args.alpha_min,
        alpha_max=args.alpha_max,
        alpha_step=args.alpha_step,
    )
    validation_df["y_pred"] = clip_and_scale(validation_df["y_pred_raw"].to_numpy(), best_alpha)

    horizon_metrics_after_alpha = []
    for horizon in horizons:
        horizon_slice = validation_df[validation_df["horizon"] == horizon]
        horizon_metrics_after_alpha.append(
            {
                "horizon": horizon,
                "wape": float(wape(horizon_slice["y_true"], horizon_slice["y_pred"])),
                "relative_bias": float(relative_bias(horizon_slice["y_true"], horizon_slice["y_pred"])),
                "score": float(competition_score(horizon_slice["y_true"], horizon_slice["y_pred"])),
            }
        )

    overall_metrics = {
        "alpha": float(best_alpha),
        "wape": float(wape(validation_df["y_true"], validation_df["y_pred"])),
        "relative_bias": float(relative_bias(validation_df["y_true"], validation_df["y_pred"])),
        "score": float(competition_score(validation_df["y_true"], validation_df["y_pred"])),
    }
    validation_metrics = {
        "per_horizon_before_alpha": [result["metrics"] for result in horizon_results],
        "per_horizon_after_alpha": horizon_metrics_after_alpha,
        "overall_after_alpha": overall_metrics,
        "alpha_trials": alpha_trials,
    }

    validation_df.to_parquet(outputs_dir / "validation_predictions.parquet", index=False)
    save_json(validation_metrics, outputs_dir / "validation_scores.json")

    artifact = _build_artifact(
        args=args,
        base_feature_cols=base_feature_cols,
        categorical_features=categorical_features,
        alpha=best_alpha,
        horizons=horizons,
        validation_metrics=validation_metrics,
    )
    joblib.dump(artifact, models_dir / "artifacts.joblib")

    expected_test_horizons = set(
        (
            test_df.sort_values(["route_id", "timestamp"])
            .groupby("route_id", sort=False)
            .cumcount()
            + 1
        ).astype(int)
    )

    print("\nValidation overall score after alpha:", f"{overall_metrics['score']:.6f}")
    print("Best alpha:", f"{best_alpha:.6f}")
    print(f"Saved validation predictions to: {outputs_dir / 'validation_predictions.parquet'}")
    print(f"Saved validation metrics to:     {outputs_dir / 'validation_scores.json'}")

    if expected_test_horizons.issubset(set(horizons)):
        from infer import predict_test

        print("Running inference with saved models...")
        prediction_df = predict_test(
            train_feature_df=feature_df,
            test_df=test_df,
            models_dir=models_dir,
            artifact=artifact,
        )
        submission = make_submission(prediction_df, args.submission_path)
        print(f"Saved submission to:             {args.submission_path}")
        print(f"Submission rows:                 {len(submission)}")
    else:
        print(
            "Skipping test inference because trained horizons do not cover the full test horizon set: "
            f"{sorted(expected_test_horizons)}"
        )


if __name__ == "__main__":
    main()
