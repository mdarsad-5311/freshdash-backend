# FreshDash Backend API

Django REST Framework backend for the FreshDash quick-commerce mobile application.

## Tech Stack
- Python 3.13
- Django 6.1
- Django REST Framework 3.18
- SQLite (Local development)

## Getting Started

### 1. Prerequisites
- Python 3.10+ installed

### 2. Activate Virtual Environment
```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Or create a new one:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Run Migrations & Start Server
```powershell
python manage.py migrate
python manage.py runserver
```

The server runs on: `http://127.0.0.1:8000/`

## Health Check
- Endpoint: `GET /api/v1/health/`
- Response:
```json
{
  "status": "ok",
  "message": "FreshDash API is running"
}
```
