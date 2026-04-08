# 📦 Инструкция по Установке и Запуску

## Системные Требования

- **OS**: Windows 10/11, Linux, macOS
- **Python**: 3.11 или выше
- **RAM**: 8GB минимум
- **Порты**: 8000 (API), 8501 (Dashboard)
- **Docker** (опционально): для контейнерного запуска

---

## 🚀 Способ 1: Быстрый Запуск (Windows)

### Шаг 1: Клонировать репозиторий

```bash
git clone https://github.com/YOUR_USERNAME/transport-dispatch-service.git
cd transport-dispatch-service
```

### Шаг 2: Запустить сервисы

**Откройте 2 терминала:**

**Терминал 1 - API:**
```bash
start_api.bat
```

**Терминал 2 - Dashboard:**
```bash
start_dashboard.bat
```

### Шаг 3: Открыть в браузере

- Dashboard: http://localhost:8501
- API Docs: http://localhost:8000/docs

**Готово! 🎉**

---

## 🐳 Способ 2: Docker (Рекомендуется)

### Преимущества:
- ✅ Не нужно устанавливать зависимости
- ✅ Изолированная среда
- ✅ Одна команда для запуска
- ✅ Легко масштабировать

### Шаг 1: Установить Docker

**Windows:**
- Скачать [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Установить и запустить

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**macOS:**
- Скачать [Docker Desktop](https://www.docker.com/products/docker-desktop)

### Шаг 2: Запустить

```bash
cd transport-dispatch-service
docker-compose up --build
```

### Шаг 3: Открыть

- Dashboard: http://localhost:8501
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Остановить:

```bash
docker-compose down
```

---

## 💻 Способ 3: Ручная Установка

### Шаг 1: Клонировать репозиторий

```bash
git clone https://github.com/YOUR_USERNAME/transport-dispatch-service.git
cd transport-dispatch-service
```

### Шаг 2: Создать виртуальное окружение

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Шаг 3: Установить зависимости

```bash
pip install -r requirements.txt
```

### Шаг 4: Настроить окружение

```bash
# Скопировать пример конфигурации
copy .env.example .env  # Windows
# или
cp .env.example .env    # Linux/macOS

# Отредактировать .env при необходимости
```

### Шаг 5: Запустить API

**Терминал 1:**
```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

Вы увидите:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Шаг 6: Запустить Dashboard

**Терминал 2 (новый):**
```bash
streamlit run dashboard/streamlit_app.py
```

Вы увидите:
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

### Шаг 7: Открыть в браузере

- Dashboard: http://localhost:8501
- API Docs: http://localhost:8000/docs

---

## ⚙️ Конфигурация

### Файл .env

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Business Parameters
VEHICLE_CAPACITY_DEFAULT=5
SAFETY_FACTOR_BASE=1.1
SAFETY_FACTOR_BETA=0.05

# Feature Flags
ENABLE_DYNAMIC_SAFETY_FACTOR=true
ENABLE_SMART_PRIORITIZATION=true
SHADOW_MODE=true  # true = тестовый режим, false = боевой

# Database
DATABASE_URL=sqlite:///./transport_orders.db

# Logging
LOG_LEVEL=INFO
```

### Основные параметры:

- **VEHICLE_CAPACITY_DEFAULT** - вместимость одной машины
- **SAFETY_FACTOR_BASE** - базовый коэффициент безопасности
- **SHADOW_MODE** - режим работы (true = не создает реальные заказы)

---

## 🧪 Проверка Установки

### 1. Проверить API

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:
```json
{
  "status": "ok",
  "timestamp": "2026-04-08T...",
  "models_loaded": true,
  "database_connected": true
}
```

### 2. Проверить Dashboard

Открыть http://localhost:8501 - должна загрузиться страница с градиентным фоном

### 3. Запустить тесты

```bash
pytest tests/ -v
```

Все тесты должны пройти ✅

---

## 🔧 Troubleshooting

### Проблема: Порт уже занят

**Ошибка:**
```
Error: Address already in use
```

**Решение:**

**Windows:**
```bash
# Найти процесс на порту 8000
netstat -ano | findstr :8000

# Убить процесс (замените PID)
taskkill /PID <PID> /F
```

**Linux/macOS:**
```bash
# Найти процесс
lsof -i :8000

# Убить процесс
kill -9 <PID>
```

**Или изменить порт в .env:**
```bash
API_PORT=8001
```

---

### Проблема: Модели не загружаются

**Ошибка:**
```
models_loaded: false
```

**Решение:**

1. Проверить пути к моделям в .env:
```bash
MODEL_DIR=../timeseries/models_recursive
HYBRID_MODEL_PATH=../timeseries/out/recursive/recursive_model.joblib
```

2. Убедиться что файлы существуют:
```bash
ls -la ../timeseries/models_recursive/
ls -la ../timeseries/out/recursive/
```

3. Если моделей нет - система работает с fallback (простая эвристика)

---

### Проблема: Dashboard не подключается к API

**Ошибка в Dashboard:**
```
🔴 API недоступен
```

**Решение:**

1. Проверить что API запущен:
```bash
curl http://localhost:8000/health
```

2. Проверить URL в dashboard/streamlit_app.py:
```python
API_URL = "http://localhost:8000"
```

3. Перезапустить Dashboard:
```bash
# Ctrl+C в терминале Dashboard
streamlit run dashboard/streamlit_app.py
```

---

### Проблема: Ошибки импорта

**Ошибка:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Решение:**

1. Активировать виртуальное окружение:
```bash
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
```

2. Переустановить зависимости:
```bash
pip install -r requirements.txt --force-reinstall
```

---

### Проблема: База данных

**Ошибка:**
```
Database connection failed
```

**Решение:**

1. Удалить старую базу:
```bash
rm transport_orders.db  # Linux/macOS
del transport_orders.db  # Windows
```

2. Перезапустить API - база создастся автоматически

---

## 📊 Проверка Работоспособности

### Тест 1: Health Check

```bash
curl http://localhost:8000/health
```

Должен вернуть `status: "ok"`

### Тест 2: Прогноз

```bash
curl -X POST http://localhost:8000/forecast/predict \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": 105,
    "office_from_id": 42,
    "timestamp": "2026-04-10T11:00:00",
    "status_1": 18,
    "status_2": 11,
    "status_3": 9,
    "status_4": 6,
    "status_5": 5,
    "status_6": 4,
    "status_7": 3,
    "status_8": 2
  }'
```

Должен вернуть прогноз с confidence

### Тест 3: Полный Pipeline

```bash
curl -X POST http://localhost:8000/plan/dispatch \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": 105,
    "office_from_id": 42,
    "timestamp": "2026-04-10T11:00:00",
    "status_1": 18,
    "status_2": 11,
    "status_3": 9,
    "status_4": 6,
    "status_5": 5,
    "status_6": 4,
    "status_7": 3,
    "status_8": 2,
    "vehicle_capacity": 5,
    "already_ordered": 1
  }'
```

Должен вернуть полный план с объяснениями

---

## 🎯 Следующие Шаги

После успешной установки:

1. ✅ Изучить [README.md](README.md) - описание системы
2. ✅ Прочитать [KILLER_FEATURES.md](KILLER_FEATURES.md) - детали фич
3. ✅ Открыть Dashboard и поэкспериментировать
4. ✅ Изучить API Docs: http://localhost:8000/docs
5. ✅ Запустить demo: `python demo.py`

---

## 💡 Полезные Команды

### Просмотр логов (Docker)

```bash
# Все сервисы
docker-compose logs -f

# Только API
docker-compose logs -f api

# Только Dashboard
docker-compose logs -f dashboard
```

### Перезапуск сервисов (Docker)

```bash
docker-compose restart
```

### Пересборка после изменений (Docker)

```bash
docker-compose up --build
```

### Запуск тестов

```bash
# Все тесты
pytest tests/ -v

# С покрытием
pytest --cov=src tests/

# Конкретный файл
pytest tests/test_forecast_api.py -v
```

---

## 📞 Поддержка

Если возникли проблемы:

1. Проверьте [Troubleshooting](#-troubleshooting)
2. Посмотрите логи
3. Проверьте что все порты свободны
4. Убедитесь что Python 3.11+

---

**Готово! Теперь у вас работает Transport Dispatch Service 🚛**
