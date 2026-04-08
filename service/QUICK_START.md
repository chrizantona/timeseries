# 🚀 Quick Start Guide

## 5-Minute Setup

### Prerequisites
- Docker & Docker Compose installed
- 8GB RAM available
- Ports 8000 and 8501 free

### Step 1: Clone & Start (2 minutes)

```bash
cd transport-dispatch-service
chmod +x quickstart.sh
./quickstart.sh
```

That's it! Services are now running.

### Step 2: Verify (30 seconds)

```bash
# Check health
curl http://localhost:8000/health

# Expected response:
# {"status":"ok","timestamp":"...","models_loaded":true,"database_connected":true}
```

### Step 3: First API Call (1 minute)

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

### Step 4: Open Dashboard (30 seconds)

```bash
# Open in browser
http://localhost:8501
```

### Step 5: Run Demo (1 minute)

```bash
# Install demo dependencies
pip install rich

# Run demo
python demo.py
```

---

## Common Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# API only
docker-compose logs -f api

# Dashboard only
docker-compose logs -f dashboard
```

### Restart Services
```bash
docker-compose restart
```

### Rebuild After Code Changes
```bash
docker-compose up --build
```

---

## API Endpoints Quick Reference

### Health Check
```bash
GET http://localhost:8000/health
```

### Forecast
```bash
POST http://localhost:8000/forecast/predict
Content-Type: application/json

{
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
}
```

### Decision
```bash
POST http://localhost:8000/decision/calculate
Content-Type: application/json

{
  "route_id": 105,
  "office_from_id": 42,
  "forecast_2h": 18.7,
  "vehicle_capacity": 5,
  "already_ordered": 1
}
```

### Complete Pipeline (Recommended)
```bash
POST http://localhost:8000/plan/dispatch
Content-Type: application/json

{
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
}
```

### Create Order
```bash
POST http://localhost:8000/orders/create
Content-Type: application/json

{
  "office_from_id": 42,
  "route_id": 105,
  "vehicles": 4,
  "priority": "high",
  "planned_dispatch_time": "2026-04-10T11:30:00"
}
```

### List Orders
```bash
GET http://localhost:8000/orders?limit=100
```

---

## Configuration Quick Reference

Edit `.env` file:

```bash
# Enable/disable features
ENABLE_DYNAMIC_SAFETY_FACTOR=true
ENABLE_SMART_PRIORITIZATION=true
SHADOW_MODE=true

# Adjust business parameters
VEHICLE_CAPACITY_DEFAULT=5
SAFETY_FACTOR_BASE=1.1
SAFETY_FACTOR_BETA=0.05

# Model paths (if using custom models)
MODEL_DIR=../timeseries/models_recursive
HYBRID_MODEL_PATH=../timeseries/out/recursive/recursive_model.joblib
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in .env
API_PORT=8001
```

### Models Not Loading
```bash
# Check model files exist
ls -la ../timeseries/models_recursive/
ls -la ../timeseries/out/recursive/

# Check logs
docker-compose logs api | grep -i "model"
```

### Dashboard Not Connecting to API
```bash
# Check API is running
curl http://localhost:8000/health

# Check dashboard logs
docker-compose logs dashboard

# Restart dashboard
docker-compose restart dashboard
```

### Database Issues
```bash
# Remove database and restart
rm transport_orders.db
docker-compose restart api
```

---

## Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test
```bash
pytest tests/test_forecast_api.py::test_health_check -v
```

### Run with Coverage
```bash
pytest --cov=src tests/
```

---

## Development Mode

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment
cp .env.example .env

# Terminal 1: Start API
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Dashboard
streamlit run dashboard/streamlit_app.py
```

### Hot Reload

Both API and Dashboard support hot reload:
- Edit Python files
- Changes are automatically detected
- No need to restart

---

## Next Steps

1. ✅ **Read README.md** - Full documentation
2. ✅ **Check KILLER_FEATURES.md** - Understand what makes us special
3. ✅ **Review PITCH.md** - Business case and vision
4. ✅ **Explore API Docs** - http://localhost:8000/docs
5. ✅ **Try Dashboard** - http://localhost:8501
6. ✅ **Run Tests** - `pytest tests/`
7. ✅ **Customize** - Edit `.env` and experiment

---

## Support

### Documentation
- README.md - Complete guide
- KILLER_FEATURES.md - Feature details
- PITCH.md - Business case
- API Docs - http://localhost:8000/docs

### Logs
```bash
docker-compose logs -f
```

### Issues
- Check logs first
- Verify prerequisites
- Restart services
- Rebuild if needed

---

## Quick Demo Script

```bash
# 1. Start services
./quickstart.sh

# 2. Wait 10 seconds
sleep 10

# 3. Run demo
python demo.py

# 4. Open dashboard
open http://localhost:8501  # macOS
# or
xdg-open http://localhost:8501  # Linux
# or
start http://localhost:8501  # Windows

# 5. Explore!
```

---

**You're all set! 🚀**

Happy dispatching! 🚛
