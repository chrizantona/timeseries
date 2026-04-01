# `target_2h` LightGBM Baseline

Обновленный direct LightGBM baseline для panel time series forecasting по `target_2h`.

## Что изменено

Теперь в пайплайне есть:

- отдельная модель на каждый горизонт `h=1..10`
- categorical handling для `route_id` и `office_from_id`
- horizon-aligned seasonal lag features без future leakage
- route-level weekly same-slot priors
- office-level same-slot aggregates и share features
- per-horizon calibration по validation
- blend из `LightGBM + daily naive + weekly naive`
- логирование `overall / per-horizon` метрик, feature importance и runtime

## Какие признаки используются

Базовые признаки:

- `status_1..status_8`
- агрегаты по статусам
- calendar features по `source_timestamp`
- future calendar features по `target timestamp = source_timestamp + h * 30min`
- route history lags / rolling stats по `target_2h`
- route history lags / rolling stats по `status_sum`
- office-level агрегаты по `office_from_id`

Новые horizon-aligned признаки:

- `target_same_slot_day`, `target_same_slot_2day`, `target_same_slot_week`, `target_same_slot_2week`
- `same_slot_day_vs_week_diff`, `same_slot_day_vs_week_ratio`, `same_slot_week_vs_2week_diff`
- `route_weekslot_mean_2`, `route_weekslot_mean_4`, `route_weekslot_median_4`, `route_weekslot_std_4`
- `office_same_slot_day`, `office_same_slot_week`, `office_weekslot_mean_2`, `office_weekslot_mean_4`
- `route_share_day`, `route_share_week`, `route_share_weekslot_mean`

Naive baseline для blend берется из:

- `daily_naive = target_same_slot_day`
- `weekly_naive = target_same_slot_week`

## Структура репозитория

```text
.
├── train.py
├── infer.py
├── bassboost.ipynb
├── baselineupdate.md
├── requirements.txt
└── src
    ├── features.py
    ├── metrics.py
    └── utils.py
```

## Как запускать

Установить зависимости:

```bash
python -m pip install -r requirements.txt
```

Финальная конфигурация со всеми улучшениями:

```bash
python train.py \
  --models-dir models/final \
  --outputs-dir outputs/final \
  --submission-path outputs/final/submission_from_train.csv
```

Отдельный инференс по сохраненным моделям:

```bash
python infer.py \
  --models-dir models/final \
  --submission-path submission.csv
```

## Поэтапные эксперименты

`train.py` поддерживает staged ablation через флаги:

- `--disable-aligned-lags`
- `--disable-route-priors`
- `--disable-office-features`
- `--disable-share-features`
- `--disable-per-horizon-alpha`
- `--disable-blend`
- `--disable-categorical-features`

Пример первого шага только с categorical ids:

```bash
python train.py \
  --models-dir models/01_categorical \
  --outputs-dir outputs/01_categorical \
  --submission-path outputs/01_categorical/submission_from_train.csv \
  --disable-aligned-lags \
  --disable-route-priors \
  --disable-office-features \
  --disable-share-features \
  --disable-per-horizon-alpha \
  --disable-blend
```

Готовый Kaggle-ноутбук `[bassboost.ipynb](/Users/chrizantona/timeseries/bassboost.ipynb)` уже содержит эту лестницу стадий и по умолчанию запускает только финальный stage. Если хочешь пройти все этапы, в ноутбуке достаточно заменить `EXPERIMENTS_TO_RUN = STAGE_SEQUENCE[-1:]` на `EXPERIMENTS_TO_RUN = STAGE_SEQUENCE`.

## Что сохраняется после обучения

- `models/.../model_h1.joblib` ... `model_h10.joblib`
- `models/.../artifacts.joblib`
- `outputs/.../feature_importance_h*.csv`
- `outputs/.../validation_predictions.parquet`
- `outputs/.../per_horizon_metrics.csv`
- `outputs/.../validation_scores.json`
- `outputs/.../submission_from_train.csv`

## Важная деталь про test

В фактическом `test_team_track.parquet` нет `office_from_id`.
Он восстанавливается из стабильной связи `route_id -> office_from_id`, найденной в train.
