"""
Скрипт для создания лучшего бленда
Результат на LB: 0.2609
"""

import pandas as pd
import numpy as np

print("="*80)
print("Создание лучшего бленда (LB: 0.2609)")
print("="*80)

# Загружаем модели
print("\nЗагрузка моделей...")
best_lb = pd.read_csv('f1da85dd-777a-44a7-b568-f63b008f0204.csv')  # 0.262
smooth = pd.read_csv('submission_advanced_01_smooth_transition.csv')  # 0.263
hybrid = pd.read_csv('out/submission_hybrid.csv')  # 0.282
catboost = pd.read_csv('out/submission_catboost.csv')

print(f"✓ Best LB (0.262): {best_lb.shape}")
print(f"✓ Smooth (0.263): {smooth.shape}")
print(f"✓ Hybrid (0.282): {hybrid.shape}")
print(f"✓ CatBoost: {catboost.shape}")

# Стратегия: Staged v2 with CatBoost
# Stage 1: Blend direct models (best + smooth)
print("\nStage 1: Блендим direct модели...")
stage1 = best_lb.copy()
stage1['y_pred'] = 0.5 * best_lb['y_pred'] + 0.3 * smooth['y_pred'] + 0.2 * hybrid['y_pred']
print(f"Stage 1: mean={stage1['y_pred'].mean():.2f}")

# Stage 2: Add CatBoost
print("Stage 2: Добавляем CatBoost...")
stage2 = best_lb.copy()
stage2['y_pred'] = 0.8 * stage1['y_pred'] + 0.2 * catboost['y_pred']
print(f"Stage 2: mean={stage2['y_pred'].mean():.2f}")

# Stage 3: Alpha calibration
print("Stage 3: Калибровка alpha...")
target_mean = 72.98  # Mean от best LB
alpha = target_mean / stage2['y_pred'].mean()
final = best_lb.copy()
final['y_pred'] = np.clip(stage2['y_pred'] * alpha, 0, None)
print(f"Alpha: {alpha:.4f}")
print(f"Final: mean={final['y_pred'].mean():.2f}")

# Сохраняем
output_path = 'submission_best_0_2609.csv'
final.to_csv(output_path, index=False)

print("\n" + "="*80)
print(f"✅ Создан: {output_path}")
print("="*80)
print("\nСтатистика:")
print(f"Mean: {final['y_pred'].mean():.2f}")
print(f"Std: {final['y_pred'].std():.2f}")
print(f"Min: {final['y_pred'].min():.2f}")
print(f"Max: {final['y_pred'].max():.2f}")
print(f"Median: {final['y_pred'].median():.2f}")

print("\n🎯 Этот бленд дал 0.2609 на LB!")
print("\nФормула:")
print("1. stage1 = 0.5*best + 0.3*smooth + 0.2*hybrid")
print("2. stage2 = 0.8*stage1 + 0.2*catboost")
print("3. final = stage2 * alpha (где alpha калибрует mean к 72.98)")
