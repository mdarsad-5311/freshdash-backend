# FreshDash REST API Documentation (v1.0.0)

Production-ready Django REST Framework backend designed to support the **FreshDash** React Native + Expo mobile application.

---

## 1. Overview & Architecture

- **Base URL:** `/api/v1/` (with top-level `/api/auth/` aliases for authentication)
- **Authentication:**
  - JWT Bearer Token (`Authorization: Bearer <access_token>`) - Primary for Mobile & SPA
  - DRF Static Token (`Authorization: Token <token>`) - Backward compatibility
  - Session-based Authentication (`sessionid` cookie) - Browser/Admin
- **JWT Lifespan:**
  - Access Token: 15 minutes (short-lived)
  - Refresh Token: 7 days (with automatic rotation and blacklisting on each refresh)
- **Rate Limiting (Throttling):**
  - Login: 5 requests / minute
  - Signup: 5 requests / minute
  - Anonymous: 100 requests / day
  - Authenticated Users: 1000 requests / day
- **Default Content-Type:** `application/json`
- **Interactive Documentation:**
  - **Swagger UI:** `http://127.0.0.1:8000/api/v1/docs/`
  - **ReDoc:** `http://127.0.0.1:8000/api/v1/redoc/`
  - **OpenAPI 3.0 Schema:** `http://127.0.0.1:8000/api/v1/schema/`

---

## 2. Standard Response Format

### Success Responses
- **200 OK / 201 Created:** Returns data payload or standard envelope.
- **204 No Content:** Returned on successful deletion.

### Error Responses
All 4xx and 5xx responses follow a predictable structure:
```json
{
  "success": false,
  "status_code": 400,
  "message": "Human readable summary of the error",
  "errors": {
    "field_name": [
      "Validation error description."
    ]
  }
}
```

---

## 3. Endpoints Reference

### 3.1 System & Health

#### Health Check
- **URL:** `GET /api/v1/health/`
- **Auth:** None (`AllowAny`)
- **Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "FreshDash Backend API",
  "version": "1.0.0"
}
```

---

### 3.2 Authentication & User Profile

#### User Signup
- **URL:** `POST /api/v1/auth/signup/` (or `POST /api/auth/signup/` / `POST /api/v1/auth/register/`)
- **Auth:** None (`AllowAny`)
- **Rate Limit:** 5 requests / minute
- **Password Rules:** Enforces Django password validation (minimum 8 characters, non-numeric, not common, dissimilarity to user details).
- **Email Rules:** Required, validated, and unique across all accounts.
- **Request Body:**
```json
{
  "username": "fresh_shopper",
  "email": "shopper@freshdash.local",
  "password": "StrongPassword123!",
  "first_name": "Rohan",
  "last_name": "Sharma",
  "phone_number": "+919876543210"
}
```
- **Response (201 Created):**
```json
{
  "success": true,
  "message": "User registered successfully.",
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  },
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": {
    "id": 2,
    "username": "fresh_shopper",
    "email": "shopper@freshdash.local",
    "first_name": "Rohan",
    "last_name": "Sharma",
    "profile": {
      "phone_number": "+919876543210",
      "order_updates": true,
      "offers_notifications": false
    }
  }
}
```

#### User Login
- **URL:** `POST /api/v1/auth/login/` (or `POST /api/auth/login/`)
- **Auth:** None (`AllowAny`)
- **Rate Limit:** 5 requests / minute
- **Identifier Support:** Accepts either **Username** OR **Email** in the `username` field.
- **Request Body:**
```json
{
  "username": "fresh_foodie",
  "password": "FreshFoodie123!"
}
```
*Or using email:*
```json
{
  "username": "foodie@freshdash.local",
  "password": "FreshFoodie123!"
}
```
- **Response (200 OK):**
```json
{
  "success": true,
  "message": "Login successful.",
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  },
  "token": "bb35aad4fd40d32f63b086bdb003f039e2142807",
  "user": {
    "id": 1,
    "username": "fresh_foodie",
    "email": "foodie@freshdash.local",
    "first_name": "Fresh",
    "last_name": "Foodie",
    "profile": {
      "phone_number": "",
      "order_updates": true,
      "offers_notifications": false
    }
  }
}
```

#### Token Refresh (Rotation)
- **URL:** `POST /api/v1/auth/token/refresh/` (or `POST /api/auth/token/refresh/`)
- **Auth:** None (`AllowAny`)
- **Security:** Issues a newly rotated refresh token and immediately blacklists the old refresh token.
- **Request Body:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
- **Response (200 OK):**
```json
{
  "success": true,
  "message": "Token refreshed successfully.",
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

#### User Logout (Token Blacklisting)
- **URL:** `POST /api/v1/auth/logout/` (or `POST /api/auth/logout/`)
- **Auth:** Required (`IsAuthenticated`, send `Authorization: Bearer <access_token>`)
- **Security:** Blacklists the refresh token permanently in the database so it can never be used to obtain new access tokens.
- **Request Body:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
- **Response (200 OK):**
```json
{
  "success": true,
  "message": "Successfully logged out and refresh token blacklisted."
}
```

#### Get Current User Details
- **URL:** `GET /api/v1/auth/me/` (or `GET /api/auth/me/` / `GET /api/v1/profile/`)
- **Auth:** Required (`IsAuthenticated`, send `Authorization: Bearer <access_token>`)
- **Response (200 OK):**
```json
{
  "id": 1,
  "username": "fresh_foodie",
  "email": "foodie@freshdash.local",
  "first_name": "Fresh",
  "last_name": "Foodie",
  "profile": {
    "phone_number": "",
    "order_updates": true,
    "offers_notifications": false
  }
}
```
    "order_updates": true,
    "offers_notifications": false
  }
}
```

#### Update Profile Settings
- **URL:** `PATCH /api/v1/profile/`
- **Auth:** Required (`IsAuthenticated`)
- **Request Body:**
```json
{
  "order_updates": true,
  "offers_notifications": true
}
```

---

### 3.3 Categories

#### List Categories
- **URL:** `GET /api/v1/categories/`
- **Auth:** None (`AllowAny`)
- **Response (200 OK):**
```json
{
  "count": 9,
  "total_pages": 1,
  "current_page": 1,
  "page_size": 20,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "vegetables",
      "name": "Fresh vegetables",
      "photo": 0,
      "tint": "#EEF4E8",
      "is_active": true,
      "products_count": 5
    },
    {
      "id": "fruits",
      "name": "Fresh fruits",
      "photo": 5,
      "tint": "#FFF0E8",
      "is_active": true,
      "products_count": 2
    }
  ]
}
```

#### Retrieve Category
- **URL:** `GET /api/v1/categories/{id}/`
- **Auth:** None (`AllowAny`)

#### Retrieve Products in Category
- **URL:** `GET /api/v1/categories/{id}/products/`
- **Auth:** None (`AllowAny`)

---

### 3.4 Products

#### List Products (with Search, Filter & Pagination)
- **URL:** `GET /api/v1/products/`
- **Auth:** None (`AllowAny`)
- **Query Parameters:**
  - `page`: Page number (default: 1)
  - `page_size`: Results per page (default: 20, max: 100)
  - `search`: Filter by produce name or description (e.g. `?search=tomato`)
  - `category`: Category identifier or tab:
    - `all`: All items
    - `vegetables`: Excludes fruits and seasonal items
    - `fruits`: Includes fruits, seasonal, and exotic fruits
    - `organic`: Filter organic produce
    - Specific category id (`roots`, `leafy`, `exotic-vegetables`, `seasonal`, `herbs`, `exotic-fruits`)
  - `popular`: `true` / `false` (Bestsellers)
  - `organic`: `true` / `false`
  - `offers`: `true` (Items with 20%+ discount)
  - `featured`: `vegetables` or `fruits` (Home screen shelf collections)
  - `ordering`: Sort by field (e.g. `price`, `-price`, `name`)
- **Response (200 OK):**
```json
{
  "count": 12,
  "total_pages": 1,
  "current_page": 1,
  "page_size": 20,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "tomato",
      "name": "Fresh red tomatoes",
      "weight": "500 g",
      "price": "28.00",
      "original": "36.00",
      "discount_percentage": 22,
      "photo": 0,
      "category": "vegetables",
      "category_name": "Fresh vegetables",
      "popular": true,
      "organic": false,
      "description": "Firm, juicy tomatoes with a bright, naturally tangy flavour.",
      "is_available": true
    }
  ]
}
```

#### Retrieve Single Product
- **URL:** `GET /api/v1/products/{id}/`
- **Auth:** None (`AllowAny`)

#### Complementary Produce ("Pairs well with")
- **URL:** `GET /api/v1/products/{id}/pairs-well-with/`
- **Auth:** None (`AllowAny`)

#### Bestsellers Collection
- **URL:** `GET /api/v1/products/bestsellers/`
- **Auth:** None (`AllowAny`)

#### Seasonal Produce
- **URL:** `GET /api/v1/products/seasonal/`
- **Auth:** None (`AllowAny`)

---

### 3.5 Shopping Basket / Cart

#### Get Basket and Bill Summary
- **URL:** `GET /api/v1/cart/`
- **Auth:** Required (`IsAuthenticated`)
- **Response (200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "key": "tomato:regular",
      "product": {
        "id": "tomato",
        "name": "Fresh red tomatoes",
        "weight": "500 g",
        "price": "28.00",
        "original": "36.00",
        "photo": 0
      },
      "quantity": 1,
      "large": false,
      "unit_price": "28.00",
      "unit_original": "36.00",
      "total_price": "28.00",
      "total_savings": "8.00"
    }
  ],
  "total_items": 1,
  "item_total": "28.00",
  "savings_total": "8.00",
  "free_delivery_threshold": "199.00",
  "delivery_fee": "20.00",
  "grand_total": "48.00"
}
```

#### Add Item to Basket
- **URL:** `POST /api/v1/cart/`
- **Auth:** Required (`IsAuthenticated`)
- **Request Body:**
```json
{
  "product_id": "banana",
  "quantity": 1,
  "large": false
}
```
- **Response (201 Created):**
```json
{
  "success": true,
  "message": "Added Banana Robusta to basket.",
  "item": { ... },
  "summary": { ... }
}
```

#### Update Item Quantity
- **URL:** `PATCH /api/v1/cart/{pk_or_key}/` (supports ID e.g. `1` or key e.g. `tomato:regular`)
- **Auth:** Required (`IsAuthenticated`)
- **Request Body (Delta or Absolute Quantity):**
```json
{
  "delta": 1
}
```
*(Passing `delta: -1` when quantity is 1 automatically removes the item from the basket).*

#### Remove Item
- **URL:** `DELETE /api/v1/cart/{pk_or_key}/`
- **Auth:** Required (`IsAuthenticated`)

#### Clear Entire Basket
- **URL:** `POST /api/v1/cart/clear/`
- **Auth:** Required (`IsAuthenticated`)

---

### 3.6 Delivery Addresses

#### List Saved Addresses
- **URL:** `GET /api/v1/addresses/`
- **Auth:** Required (`IsAuthenticated` & `IsOwner`)

#### Add New Address
- **URL:** `POST /api/v1/addresses/`
- **Auth:** Required (`IsAuthenticated`)
- **Request Body:**
```json
{
  "name": "Work",
  "line": "8, 100 Feet Road",
  "area": "Indiranagar, Bengaluru · 560038",
  "is_default": false
}
```

#### Update Address
- **URL:** `PUT /api/v1/addresses/{id}/` or `PATCH /api/v1/addresses/{id}/`
- **Auth:** Required (`IsAuthenticated` & `IsOwner`)

#### Set Default Address
- **URL:** `POST /api/v1/addresses/{id}/set-default/`
- **Auth:** Required (`IsAuthenticated` & `IsOwner`)

#### Delete Address
- **URL:** `DELETE /api/v1/addresses/{id}/`
- **Auth:** Required (`IsAuthenticated` & `IsOwner`)

---

### 3.7 Coupons & Promo Discounts

#### List Active Coupons
- **URL:** `GET /api/v1/coupons/`
- **Auth:** None (`AllowAny`)
- **Response (200 OK):**
```json
{
  "results": [
    {
      "code": "FRESH20",
      "description": "Get 20% off your basket, up to ₹50.",
      "discount_rate": "0.20",
      "discount_percentage": 20,
      "max_discount": "50.00",
      "min_order_value": "0.00",
      "is_active": true
    }
  ]
}
```

#### Apply Coupon to Basket Total
- **URL:** `POST /api/v1/coupons/apply/`
- **Auth:** None (`AllowAny`)
- **Request Body:**
```json
{
  "code": "FRESH20",
  "item_total": "200.00"
}
```
- **Response (200 OK):**
```json
{
  "valid": true,
  "code": "FRESH20",
  "description": "Get 20% off your basket, up to ₹50.",
  "discount_percentage": 20,
  "discount_amount": "40.00",
  "item_total": "200.00",
  "delivery_fee": "0.00",
  "grand_total": "160.00",
  "message": "20% off applied, up to ₹50."
}
```

---

### 3.8 Orders

#### Place Order from Basket
- **URL:** `POST /api/v1/orders/`
- **Auth:** Required (`IsAuthenticated`)
- **Request Body:**
```json
{
  "delivery_address_id": 1,
  "coupon_code": "FRESH20"
}
```
- **Response (201 Created):**
```json
{
  "success": true,
  "message": "Order placed successfully.",
  "order": {
    "id": 1,
    "order_number": "FR9B4A1F",
    "status": "placed",
    "delivery_address_snapshot": {
      "name": "Home",
      "line": "24, 18th Main Road, Sector 2",
      "area": "HSR Layout, Bengaluru · 560102"
    },
    "item_total": "111.00",
    "delivery_fee": "20.00",
    "discount_amount": "22.20",
    "grand_total": "108.80",
    "coupon_code": "FRESH20",
    "items": [
      {
        "id": 1,
        "product": "tomato",
        "product_name": "Fresh red tomatoes",
        "weight": "500 g",
        "quantity": 1,
        "large": false,
        "unit_price": "28.00",
        "total_price": "28.00"
      }
    ],
    "created_at": "2026-10-30T07:15:00Z"
  }
}
```

#### List Customer Orders
- **URL:** `GET /api/v1/orders/`
- **Auth:** Required (`IsAuthenticated` & `IsOwner`)

#### Retrieve Order by Order Number
- **URL:** `GET /api/v1/orders/{order_number}/` (e.g. `/api/v1/orders/FR1024/`)
- **Auth:** Required (`IsAuthenticated` & `IsOwner`)

---

### 3.9 Favourite Products

#### List Favourites
- **URL:** `GET /api/v1/favorites/`
- **Auth:** Required (`IsAuthenticated` & `IsOwner`)

#### Toggle Favourite
- **URL:** `POST /api/v1/favorites/toggle/`
- **Auth:** Required (`IsAuthenticated`)
- **Request Body:**
```json
{
  "product_id": "tomato"
}
```
- **Response (200 OK):**
```json
{
  "success": true,
  "product_id": "tomato",
  "is_favourite": true,
  "message": "Saved Fresh red tomatoes to favourites."
}
```

---

### 3.10 FAQs (Help & Support)

#### List FAQs
- **URL:** `GET /api/v1/faqs/`
- **Auth:** None (`AllowAny`)
- **Response (200 OK):**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "question": "How does FreshDash work?",
      "answer": "Browse farm-fresh fruits, vegetables and greens. Add items to your basket and experience instant delivery in 10–15 minutes.",
      "order": 1
    }
  ]
}
```

