# `target_2h` LightGBM Baseline

Полностью рабочий baseline для соревнования по прогнозу `target_2h`.

## Что это за решение

Решение использует direct forecasting для panel time series по `route_id`:

- обучаются `10` отдельных `LightGBMRegressor` для горизонтов `h=1..10`
- target для каждого горизонта строится как `shift(-h)` внутри `route_id`
- validation делается строго по времени: последние `7` дней
- после валидации подбирается глобальный `alpha` под метрику `WAPE + |Relative Bias|`
- предсказания всегда обрезаются в `0+`

Решение не использует:

- future leakage
- random split
- recursive forecast

## Какие фичи используются

- сырые `status_1..status_8`
- агрегаты по статусам:
  `status_sum`, `status_mean`, `status_max`, `status_min`, `status_nonzero_cnt`, `status_std`
- доли каждого `status_i` внутри `status_sum`
- calendar features для текущего `timestamp`
- future calendar features для `target timestamp = timestamp + 30min * h`
- лаги `target_2h` по `route_id`
- rolling mean/std/min/max по `target_2h` только из прошлого через `shift(1)`
- лаги и rolling по `status_sum`
- diff features по `target_2h` и `status_sum`
- office-level aggregates по `office_from_id`
- route share features относительно офиса

## Структура репозитория

```text
.
├── train.py
├── infer.py
├── requirements.txt
├── README.md
└── src
    ├── features.py
    ├── metrics.py
    └── utils.py
```

## Файлы

- `train.py` обучает модели, сохраняет артефакты и считает validation
- `infer.py` загружает обученные модели и собирает `submission.csv`
- `src/features.py` строит все признаки
- `src/metrics.py` реализует `WAPE + |Relative Bias|`
- `src/utils.py` содержит загрузку parquet, split, калибровку и сбор сабмита

## Важная деталь про test

В фактическом `test_team_track.parquet` нет `office_from_id`.
В коде этот столбец восстанавливается по стабильной связи `route_id -> office_from_id` из train.

## Как получить submission

1. Положить рядом с кодом файлы:

- `train_team_track.parquet`
- `test_team_track.parquet`

2. Установить зависимости:

```bash
python -m pip install -r requirements.txt
```

3. Обучить baseline:

```bash
python train.py
```

4. Собрать финальный сабмит:

```bash
python infer.py --submission-path submission.csv
```

5. Загружать файл:

```text
submission.csv
```

## Что появится после обучения

- `models/model_h1.joblib` ... `models/model_h10.joblib`
- `models/artifacts.joblib`
- `outputs/feature_importance_h*.csv`
- `outputs/validation_predictions.parquet`
- `outputs/validation_scores.json`
- `outputs/submission_from_train.csv`

После отдельного инференса появится финальный:

- `submission.csv`
