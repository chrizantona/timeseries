from __future__ import annotations

import argparse
import os
from pathlib import Path
import time
import warnings

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from src.features import (
    build_features,
    build_horizon_feature_frame,
    build_model_matrix,
    build_office_history_frame,
    get_calendar_feature_names,
    get_horizon_feature_names,
    make_targets,
)
from src.utils import (
    FORECAST_HORIZONS,
    TARGET_COL,
    clip_and_scale,
    clip_predictions,
    ensure_dir,
    load_data,
    make_submission,
    save_json,
    search_blend_weights,
    summarize_metrics,
    time_split,
    tune_alpha,
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
    parser.add_argument("--blend-weight-step", type=float, default=0.05)
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
    parser.add_argument("--feature-importance-topk", type=int, default=10)
    parser.add_argument("--disable-categorical-features", action="store_true")
    parser.add_argument("--disable-aligned-lags", action="store_true")
    parser.add_argument("--disable-route-priors", action="store_true")
    parser.add_argument("--disable-office-features", action="store_true")
    parser.add_argument("--disable-share-features", action="store_true")
    parser.add_argument("--disable-per-horizon-alpha", action="store_true")
    parser.add_argument("--disable-blend", action="store_true")
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


def normalize_experiment_config(args: argparse.Namespace) -> dict[str, bool]:
    config = {
        "use_categorical_features": not args.disable_categorical_features,
        "use_aligned_lags": not args.disable_aligned_lags,
        "use_route_priors": not args.disable_route_priors,
        "use_office_features": not args.disable_office_features,
        "use_share_features": not args.disable_share_features,
        "use_per_horizon_alpha": not args.disable_per_horizon_alpha,
        "use_blend": not args.disable_blend,
    }

    if config["use_share_features"]:
        config["use_aligned_lags"] = True
        config["use_route_priors"] = True
        config["use_office_features"] = True

    if config["use_blend"]:
        config["use_aligned_lags"] = True

    return config


def _resolve_submission_path(args: argparse.Namespace) -> Path:
    submission_path = Path(args.submission_path)
    default_submission_path = Path("outputs/submission_from_train.csv")
    if submission_path == default_submission_path and Path(args.outputs_dir) != Path("outputs"):
        submission_path = Path(args.outputs_dir) / "submission_from_train.csv"
    ensure_dir(submission_path.parent)
    return submission_path


def _build_artifact(
    args: argparse.Namespace,
    base_feature_cols: list[str],
    categorical_features: list[str],
    horizon_feature_cols: list[str],
    horizons: list[int],
    validation_metrics: dict[str, object],
    experiment_config: dict[str, bool],
    per_horizon_postprocess: dict[str, dict[str, object]],
) -> dict[str, object]:
    feature_columns = base_feature_cols + horizon_feature_cols + get_calendar_feature_names(prefix="future")
    return {
        "target_col": TARGET_COL,
        "horizons": horizons,
        "freq_minutes": args.freq_minutes,
        "valid_days": args.valid_days,
        "base_feature_cols": base_feature_cols,
        "horizon_feature_cols": horizon_feature_cols,
        "feature_columns": feature_columns,
        "categorical_features": categorical_features,
        "experiment_config": experiment_config,
        "per_horizon_postprocess": per_horizon_postprocess,
        "validation_metrics": validation_metrics,
    }


def train_one_horizon(
    df: pd.DataFrame,
    office_history_frame: pd.DataFrame,
    horizon: int,
    base_feature_cols: list[str],
    categorical_features: list[str],
    model_params: dict[str, float | int | str],
    valid_days: int,
    freq_minutes: int,
    early_stopping_rounds: int,
    alpha_min: float,
    alpha_max: float,
    alpha_step: float,
    blend_weight_step: float,
    experiment_config: dict[str, bool],
) -> dict[str, object]:
    start_time = time.perf_counter()

    target_name = f"target_h_{horizon}"
    split = time_split(df, horizon=horizon, valid_days=valid_days, freq_minutes=freq_minutes)

    fit_mask = split["fit_mask"] & df[target_name].notna()
    valid_mask = split["valid_mask"] & df[target_name].notna()

    horizon_feature_frame = build_horizon_feature_frame(
        df=df,
        office_history_frame=office_history_frame,
        horizon=horizon,
        target_col=TARGET_COL,
        use_aligned_lags=experiment_config["use_aligned_lags"],
        use_route_priors=experiment_config["use_route_priors"],
        use_office_features=experiment_config["use_office_features"],
        use_share_features=experiment_config["use_share_features"],
    )
    horizon_feature_cols = list(horizon_feature_frame.columns)

    fit_df = df.loc[fit_mask].copy()
    valid_df = df.loc[valid_mask].copy()

    X_fit = build_model_matrix(
        fit_df,
        base_feature_cols=base_feature_cols,
        horizon=horizon,
        horizon_feature_cols=horizon_feature_cols,
        horizon_feature_frame=horizon_feature_frame,
        categorical_features=categorical_features,
        freq_minutes=freq_minutes,
    )
    X_valid = build_model_matrix(
        valid_df,
        base_feature_cols=base_feature_cols,
        horizon=horizon,
        horizon_feature_cols=horizon_feature_cols,
        horizon_feature_frame=horizon_feature_frame,
        categorical_features=categorical_features,
        freq_minutes=freq_minutes,
    )

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

    valid_pred_raw = np.asarray(
        model.predict(X_valid, num_iteration=model.best_iteration_),
        dtype=np.float32,
    )
    valid_pred_clip = clip_predictions(valid_pred_raw)

    alpha_model = 1.0
    alpha_trials_model: list[dict[str, float]] = []
    if experiment_config["use_per_horizon_alpha"]:
        alpha_model, alpha_trials_model = tune_alpha(
            y_true=y_valid,
            y_pred_raw=valid_pred_raw,
            alpha_min=alpha_min,
            alpha_max=alpha_max,
            alpha_step=alpha_step,
        )
    valid_pred_model = clip_and_scale(valid_pred_raw, alpha_model)

    daily_naive = None
    weekly_naive = None
    if "target_same_slot_day" in horizon_feature_frame.columns:
        daily_naive = clip_predictions(np.nan_to_num(horizon_feature_frame.loc[valid_df.index, "target_same_slot_day"], nan=0.0))
    if "target_same_slot_week" in horizon_feature_frame.columns:
        weekly_naive = clip_predictions(np.nan_to_num(horizon_feature_frame.loc[valid_df.index, "target_same_slot_week"], nan=0.0))

    blend_weights = {
        "w_lgbm": 1.0,
        "w_daily": 0.0,
        "w_weekly": 0.0,
    }
    blend_search_metrics = summarize_metrics(y_valid, valid_pred_model)
    blend_alpha = 1.0
    blend_alpha_trials: list[dict[str, float]] = []
    valid_pred_blend = valid_pred_model.copy()

    if experiment_config["use_blend"]:
        if daily_naive is None or weekly_naive is None:
            raise ValueError("Blend requires aligned daily and weekly naive features.")

        blend_weights, blend_search_metrics = search_blend_weights(
            y_true=y_valid,
            pred_lgbm=valid_pred_model,
            pred_daily=daily_naive,
            pred_weekly=weekly_naive,
            weight_step=blend_weight_step,
        )

        blend_raw = (
            valid_pred_model * np.float32(blend_weights["w_lgbm"])
            + daily_naive * np.float32(blend_weights["w_daily"])
            + weekly_naive * np.float32(blend_weights["w_weekly"])
        ).astype(np.float32)

        blend_alpha, blend_alpha_trials = tune_alpha(
            y_true=y_valid,
            y_pred_raw=blend_raw,
            alpha_min=alpha_min,
            alpha_max=alpha_max,
            alpha_step=alpha_step,
        )
        valid_pred_blend = clip_and_scale(blend_raw, blend_alpha)

    valid_pred_final = valid_pred_blend if experiment_config["use_blend"] else valid_pred_model

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
    valid_predictions["y_pred_raw"] = valid_pred_raw
    valid_predictions["y_pred_clip"] = valid_pred_clip
    valid_predictions["y_pred_model"] = valid_pred_model
    valid_predictions["y_pred_final"] = valid_pred_final

    if daily_naive is not None:
        valid_predictions["y_pred_daily_naive"] = daily_naive
    if weekly_naive is not None:
        valid_predictions["y_pred_weekly_naive"] = weekly_naive
    if experiment_config["use_blend"]:
        valid_predictions["y_pred_blend"] = valid_pred_blend

    metrics = {
        "horizon": horizon,
        "fit_rows": int(fit_mask.sum()),
        "valid_rows": int(valid_mask.sum()),
        "fit_cutoff": str(split["fit_cutoff"]),
        "valid_start": str(split["valid_start"]),
        "best_iteration": int(model.best_iteration_ or model.n_estimators),
        "runtime_seconds": float(time.perf_counter() - start_time),
        "raw_clip": summarize_metrics(y_valid, valid_pred_clip),
        "model_calibrated": summarize_metrics(y_valid, valid_pred_model),
        "final": summarize_metrics(y_valid, valid_pred_final),
        "alpha_model": float(alpha_model),
        "blend_weights": blend_weights,
        "blend_alpha": float(blend_alpha),
        "blend_search_metrics": blend_search_metrics,
        "alpha_trials_model": alpha_trials_model,
        "alpha_trials_blend": blend_alpha_trials,
    }

    if daily_naive is not None:
        metrics["daily_naive"] = summarize_metrics(y_valid, daily_naive)
    if weekly_naive is not None:
        metrics["weekly_naive"] = summarize_metrics(y_valid, weekly_naive)
    if experiment_config["use_blend"]:
        metrics["blend"] = summarize_metrics(y_valid, valid_pred_blend)

    return {
        "model": model,
        "feature_importance": feature_importance,
        "valid_predictions": valid_predictions,
        "metrics": metrics,
        "horizon_feature_cols": horizon_feature_cols,
        "postprocess": {
            "alpha_model": float(alpha_model),
            "blend_weights": blend_weights,
            "blend_alpha": float(blend_alpha),
        },
    }


def main() -> None:
    warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

    total_start = time.perf_counter()

    args = parse_args()
    horizons = sorted(set(int(h) for h in args.horizons))
    experiment_config = normalize_experiment_config(args)

    models_dir = ensure_dir(args.models_dir)
    outputs_dir = ensure_dir(args.outputs_dir)
    submission_path = _resolve_submission_path(args)

    print("Loading train/test parquet...")
    train_df, test_df = load_data(args.train_path, args.test_path, max_routes=args.max_routes)
    print(f"train shape: {train_df.shape}")
    print(f"test shape:  {test_df.shape}")
    print(f"horizons:    {horizons}")
    print(f"config:      {experiment_config}")

    print("Building base features...")
    feature_df = build_features(train_df, target_col=TARGET_COL)
    feature_df = make_targets(feature_df, target_col=TARGET_COL, horizons=horizons)
    office_history_frame = build_office_history_frame(feature_df, target_col=TARGET_COL)

    target_cols = {f"target_h_{h}" for h in horizons}
    excluded_cols = {"source_timestamp", TARGET_COL, *target_cols}
    base_feature_cols = [col for col in feature_df.columns if col not in excluded_cols]
    categorical_features = []
    if experiment_config["use_categorical_features"]:
        categorical_features = [col for col in ("route_id", "office_from_id") if col in base_feature_cols]

    model_params = build_model_params(args)
    horizon_results: list[dict[str, object]] = []
    validation_parts: list[pd.DataFrame] = []
    horizon_feature_cols: list[str] = get_horizon_feature_names(
        use_aligned_lags=experiment_config["use_aligned_lags"],
        use_route_priors=experiment_config["use_route_priors"],
        use_office_features=experiment_config["use_office_features"],
        use_share_features=experiment_config["use_share_features"],
    )
    per_horizon_postprocess: dict[str, dict[str, object]] = {}

    for horizon in tqdm(horizons, desc="Training horizons"):
        result = train_one_horizon(
            df=feature_df,
            office_history_frame=office_history_frame,
            horizon=horizon,
            base_feature_cols=base_feature_cols,
            categorical_features=categorical_features,
            model_params=model_params,
            valid_days=args.valid_days,
            freq_minutes=args.freq_minutes,
            early_stopping_rounds=args.early_stopping_rounds,
            alpha_min=args.alpha_min,
            alpha_max=args.alpha_max,
            alpha_step=args.alpha_step,
            blend_weight_step=args.blend_weight_step,
            experiment_config=experiment_config,
        )

        if result["horizon_feature_cols"] != horizon_feature_cols:
            raise ValueError("Horizon feature columns are inconsistent across horizons.")

        horizon_results.append(result)
        validation_parts.append(result["valid_predictions"])
        per_horizon_postprocess[str(horizon)] = result["postprocess"]

        model_path = models_dir / f"model_h{horizon}.joblib"
        joblib.dump(result["model"], model_path)

        importance_path = outputs_dir / f"feature_importance_h{horizon}.csv"
        result["feature_importance"].to_csv(importance_path, index=False)

        final_score = result["metrics"]["final"]["score"]
        print(f"\nTop features for horizon {horizon}:")
        print(result["feature_importance"].head(args.feature_importance_topk).to_string(index=False))
        print(f"validation final score: {final_score:.6f}")
        print(
            "validation final WAPE / Relative Bias: "
            f"{result['metrics']['final']['wape']:.6f} / {result['metrics']['final']['relative_bias']:.6f}"
        )

    validation_df = pd.concat(validation_parts, ignore_index=True)

    overall_metrics = {
        "raw_clip": summarize_metrics(validation_df["y_true"], validation_df["y_pred_clip"]),
        "model_calibrated": summarize_metrics(validation_df["y_true"], validation_df["y_pred_model"]),
        "final": summarize_metrics(validation_df["y_true"], validation_df["y_pred_final"]),
    }
    if "y_pred_daily_naive" in validation_df.columns:
        overall_metrics["daily_naive"] = summarize_metrics(validation_df["y_true"], validation_df["y_pred_daily_naive"])
    if "y_pred_weekly_naive" in validation_df.columns:
        overall_metrics["weekly_naive"] = summarize_metrics(validation_df["y_true"], validation_df["y_pred_weekly_naive"])
    if "y_pred_blend" in validation_df.columns:
        overall_metrics["blend"] = summarize_metrics(validation_df["y_true"], validation_df["y_pred_blend"])

    per_horizon_summary_rows = []
    for horizon in horizons:
        horizon_slice = validation_df[validation_df["horizon"] == horizon]
        row = {
            "horizon": horizon,
            "raw_clip_score": float(summarize_metrics(horizon_slice["y_true"], horizon_slice["y_pred_clip"])["score"]),
            "model_score": float(summarize_metrics(horizon_slice["y_true"], horizon_slice["y_pred_model"])["score"]),
            "final_score": float(summarize_metrics(horizon_slice["y_true"], horizon_slice["y_pred_final"])["score"]),
        }
        if "y_pred_daily_naive" in horizon_slice.columns:
            row["daily_naive_score"] = float(
                summarize_metrics(horizon_slice["y_true"], horizon_slice["y_pred_daily_naive"])["score"]
            )
        if "y_pred_weekly_naive" in horizon_slice.columns:
            row["weekly_naive_score"] = float(
                summarize_metrics(horizon_slice["y_true"], horizon_slice["y_pred_weekly_naive"])["score"]
            )
        per_horizon_summary_rows.append(row)

    per_horizon_summary = pd.DataFrame(per_horizon_summary_rows)
    validation_metrics = {
        "config": experiment_config,
        "runtime_seconds_total": float(time.perf_counter() - total_start),
        "overall": overall_metrics,
        "per_horizon": [result["metrics"] for result in horizon_results],
    }

    validation_df.to_parquet(outputs_dir / "validation_predictions.parquet", index=False)
    per_horizon_summary.to_csv(outputs_dir / "per_horizon_metrics.csv", index=False)
    save_json(validation_metrics, outputs_dir / "validation_scores.json")

    artifact = _build_artifact(
        args=args,
        base_feature_cols=base_feature_cols,
        categorical_features=categorical_features,
        horizon_feature_cols=horizon_feature_cols,
        horizons=horizons,
        validation_metrics=validation_metrics,
        experiment_config=experiment_config,
        per_horizon_postprocess=per_horizon_postprocess,
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

    print("\nPer-horizon validation summary:")
    print(per_horizon_summary.to_string(index=False))
    print("\nValidation overall final score:", f"{overall_metrics['final']['score']:.6f}")
    print("Validation overall final WAPE:", f"{overall_metrics['final']['wape']:.6f}")
    print("Validation overall final Relative Bias:", f"{overall_metrics['final']['relative_bias']:.6f}")
    print(f"Saved validation predictions to: {outputs_dir / 'validation_predictions.parquet'}")
    print(f"Saved per-horizon metrics to:    {outputs_dir / 'per_horizon_metrics.csv'}")
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
        submission = make_submission(prediction_df, submission_path)
        print(f"Saved submission to:             {submission_path}")
        print(f"Submission rows:                 {len(submission)}")
    else:
        print(
            "Skipping test inference because trained horizons do not cover the full test horizon set: "
            f"{sorted(expected_test_horizons)}"
        )


if __name__ == "__main__":
    main()
