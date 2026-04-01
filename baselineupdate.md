Нужно улучшить текущий direct LightGBM baseline для panel time series forecasting.

Постановка:

* отдельная модель на каждый горизонт `h=1..10`
* таргет для горизонта `h`: `target_h = target_2h.shift(-h)` внутри `route_id`
* все признаки должны использовать только информацию, доступную в момент времени `t`
* запрещён leakage из будущего

Что нужно реализовать в первом пакете:

1. Убедиться, что `route_id` и `office_from_id` используются как categorical features в LightGBM.
2. Для каждой модели горизонта `h` добавить horizon-aligned seasonal lag features по `target_2h` внутри `route_id`:

* `target_same_slot_day_h = shift(48 - h)`
* `target_same_slot_2day_h = shift(96 - h)`
* `target_same_slot_week_h = shift(336 - h)`
* `target_same_slot_2week_h = shift(672 - h)`

3. Добавить derived features на их основе:

* `same_slot_day_vs_week_diff_h`
* `same_slot_day_vs_week_ratio_h`
* `same_slot_week_vs_2week_diff_h`

4. Добавить route-level weekly same-slot priors:

* `route_weekslot_mean_2_h` = mean of `shift(336-h)` and `shift(672-h)`
* `route_weekslot_mean_4_h` = mean of `shift(336-h)`, `shift(672-h)`, `shift(1008-h)`, `shift(1344-h)`
* `route_weekslot_median_4_h`
* `route_weekslot_std_4_h`

5. Построить office-level aggregated target series:

* `office_target_sum` = sum of `target_2h` by `office_from_id` and `timestamp`

И для каждой модели горизонта `h` добавить:

* `office_same_slot_day_h = office_target_sum.shift(48 - h)`
* `office_same_slot_week_h = office_target_sum.shift(336 - h)`
* `office_weekslot_mean_2_h`
* `office_weekslot_mean_4_h`

6. Добавить route-share features:

* `route_share_day_h = target_same_slot_day_h / (office_same_slot_day_h + 1e-6)`
* `route_share_week_h = target_same_slot_week_h / (office_same_slot_week_h + 1e-6)`
* `route_share_weekslot_mean_h = route_weekslot_mean_4_h / (office_weekslot_mean_4_h + 1e-6)`

7. После обучения сделать per-horizon calibration:

* для каждого горизонта `h` подобрать `alpha_h`
* `pred_calibrated_h = clip(pred_raw_h * alpha_h, lower=0)`
* alpha подбирать на validation grid search по метрике `WAPE + abs(sum(pred)/sum(y)-1)`

8. Построить два naive baseline:

* `daily_naive_h = shift(48 - h)`
* `weekly_naive_h = shift(336 - h)`

9. Сделать blend:

* `pred_blend_h = w1_h * pred_lgbm_h + w2_h * pred_daily_naive_h + w3_h * pred_weekly_naive_h`
* веса искать по validation
* после blend можно ещё раз подобрать `alpha_h`

10. После каждого эксперимента логировать:

* overall validation score
* WAPE
* Relative Bias
* per-horizon metrics
* feature importances
* runtime

11. Делать эксперименты поэтапно, не всё сразу:

* сначала categorical ids
* потом aligned lags
* потом route priors
* потом office features
* потом share features
* потом per-horizon alpha
* потом blend
