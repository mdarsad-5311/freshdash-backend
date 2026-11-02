# FreshDash Backend API

A complete, production-ready REST API built with **Django 6** and **Django REST Framework (DRF)** to power the **FreshDash** React Native + Expo quick-commerce mobile app.

---

## Features

- **Architecture:** Clean layered structure with decoupled models, serializers, views, permissions, filters, and exception handling.
- **RESTful Endpoints:** Full CRUD support with versioned `/api/v1/` routes.
- **Mobile Optimized & Secure:**
  - JWT Authentication (`Authorization: Bearer <access_token>`) with 15-minute access token lifespan.
  - Refresh token rotation with immediate blacklisting on refresh.
  - Dual-auth support: JWT Bearer tokens + DRF Token (`Token <token>`) + Session authentication.
  - Email or Username login support.
  - Strict password strength validation via Django password validators.
  - Rate limiting (throttling): 5 requests/min for login & signup to prevent brute-force attacks.
  - Page-number pagination with `count`, `total_pages`, `current_page`, and navigation links.
  - Search filter (`?search=`), category filter (`?category=`), shelf collections (`?featured=`), and price sorting (`?ordering=price`).
  - Strict ownership-based access control (`IsOwner`) preventing unauthorized data access & IDOR.
  - Normalized error response handling across all 4xx/5xx status codes.
- **Produce & Quick-Commerce Logic:**
  - Live shopping basket calculations (subtotal, savings, free delivery threshold above ₹199).
  - Promo coupon validation and discount computation (`FRESH20`).
  - Multi-pack support (regular vs. double pack).
  - Delivery address management with default selection.
  - Order checkout with snapshotting and automatic basket clearing.
- **API Documentation:**
  - Auto-generated OpenAPI 3.0 specification (`drf-spectacular`).
  - Interactive Swagger UI (`/api/v1/docs/`) and ReDoc (`/api/v1/redoc/`).

---

## Tech Stack

- **Language:** Python 3.13+
- **Framework:** Django 6.1.2 & Django REST Framework 3.18.3
- **Database:** SQLite3 (development) with immediate PostgreSQL migration readiness
- **Documentation:** drf-spectacular (OpenAPI 3.0)
- **CORS:** django-cors-headers configured for Expo and React Native

---

## Local Setup Instructions

### 1. Prerequisites
- Python 3.10+ installed
- Virtual environment tool (`venv`)

### 2. Activate Virtual Environment
On Windows (PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```
On macOS / Linux:
```bash
source .venv/bin/activate
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```
Default `.env` configuration:
```ini
SECRET_KEY=django-insecure-freshdash-secret-key-phase3-dev-token-2026-b816
JWT_SECRET_KEY=freshdash-jwt-secret-key-unique-phase4-super-secure-token-2026
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost,10.0.2.2,*
CORS_ALLOW_ALL_ORIGINS=True
PAGE_SIZE=20
```

### 5. Apply Migrations
```powershell
python manage.py migrate
```

### 6. Seed Initial Data (Categories, Products, Demo User, Coupons)
Run the custom management command to seed the database with all categories and products matching the FreshDash frontend:
```powershell
python manage.py seed_data
```
This sets up:
- 9 Produce Categories
- 12 Produce Products
- Promo coupon `FRESH20`
- FAQs for Help & Support
- Demo user `fresh_foodie` (Password: `FreshFoodie123!`, Token: `bb35aad4fd40d32f63b086bdb003f039e2142807`)
- Saved Home & Work delivery addresses

### 7. Run Automated Test Suite
```powershell
python manage.py test api
```
Runs 31 automated tests covering JWT authentication, token rotation, blacklisting, rate limiting, password validation, product filtering, pagination, cart math, coupons, orders, permissions, IDOR prevention, and error handling.

### 8. Start the Development Server
```powershell
python manage.py runserver 0.0.0.0:8000
```
- API Base: `http://127.0.0.1:8000/api/v1/`
- Swagger Docs: `http://127.0.0.1:8000/api/v1/docs/`
- ReDoc: `http://127.0.0.1:8000/api/v1/redoc/`
- Admin Panel: `http://127.0.0.1:8000/admin/`

---

## API Documentation
For detailed endpoint schemas, request parameters, and response payloads, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md).
