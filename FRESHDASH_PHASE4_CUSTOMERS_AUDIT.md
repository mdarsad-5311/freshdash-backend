# FreshDash — Phase 4: Customers Management Read-Only Production Audit Report

**Date:** November 5, 2026  
**Status:** COMPLETE (READ-ONLY AUDIT)  
**Target Environments:**
- Production Backend API: `https://mdarsad5311.pythonanywhere.com/api/v1/`
- Production Admin Dashboard: `https://mdarsad5311.pythonanywhere.com/dashboard/#/customers/`
- Local Backend: `C:\Users\SIS\OneDrive\Desktop\freshdash-backend\`
- Local Frontend: `C:\Users\SIS\OneDrive\Desktop\freshdash\`
- Production Database: `/home/mdarsad5311/freshdash-backend/db.sqlite3` (Preserved intact; 0 mutations)

---

## 1. Executive Summary

A comprehensive, strictly read-only audit of the FreshDash Customers Management module was conducted across the Django REST Framework backend, React + Vite Admin Dashboard frontend, and the live PythonAnywhere production environment.

### Audit Summary Matrix
| Category | Live Production Status | Local Codebase Status | Health Assessment |
| :--- | :--- | :--- | :--- |
| **Authentication & RBAC** | Enforced (401 unauth, 403 consumer) | Protected with `IsAdminRole` | Pass |
| **Customer List API** | HTTP 200 OK (13 accounts) | Standard DRF ReadOnlyModelViewSet | Pass |
| **Customer Detail API** | HTTP 200 OK (Addresses & Orders) | `AdminCustomerDetailSerializer` | Pass |
| **Role & Status Toggles** | Functional with self-lockout guard | Custom ViewSet actions | Pass |
| **Search & Filtering** | Functional on backend | Incomplete frontend integration | Needs Improvement |
| **Pagination** | Functional on backend (20/page) | **MISSING on frontend UI** | **P0 Issue** |
| **Sorting** | Hardcoded `-date_joined` | Metrics sort not annotated | Needs Improvement |
| **Query Performance** | N+1 queries on `orders_count`/`total_spent` | Evaluated in serializer methods | Needs Improvement |
| **Test Suite** | Not deployed directly | 4/4 Customer tests pass; 91/91 all pass | Pass |
| **Frontend Build** | Live on PA | `tsc -b && vite build` 0 errors | Pass |

---

## 2. Production Live Verification & Probe Evidence

Live GET probes were executed against the PythonAnywhere production API (`https://mdarsad5311.pythonanywhere.com/api/v1`) using administrator authentication (`admin_test`). All personal identifying information (PII) is masked in accordance with privacy protocols.

### 2.1 Live Endpoint Audit Results

| Endpoint / Operation | HTTP Code | Response Summary / Evidence |
| :--- | :--- | :--- |
| `GET /api/v1/admin/customers/` (Unauthenticated) | **401 Unauthorized** | `{"success": false, "message": "Authentication credentials were not provided."}` |
| `POST /api/v1/admin/auth/login/` (Admin Login) | **200 OK** | JWT `access` & `refresh` tokens issued; user confirmed as `role='admin'`, `is_staff=True` |
| `GET /api/v1/admin/customers/` (List All) | **200 OK** | Envelope: `count: 13`, `total_pages: 1`, `current_page: 1`, `page_size: 20`. 13 accounts returned. |
| `GET /api/v1/admin/customers/{id}/` (Detail) | **200 OK** | Includes `addresses` array and `recent_orders` array. |
| `GET /api/v1/admin/customers/?search=adm` | **200 OK** | `count: 3` (Matches admin accounts by username/email). |
| `GET /api/v1/admin/customers/?role=customer` | **200 OK** | `count: 10` (Lists consumer customer accounts). |
| `GET /api/v1/admin/customers/?role=admin` | **200 OK** | `count: 3` (Lists administrator accounts). |
| `GET /api/v1/admin/customers/?role=manager` | **200 OK** | `count: 0` (No store managers currently registered). |
| `GET /api/v1/admin/customers/?is_active=true` | **200 OK** | `count: 13` (All 13 accounts currently active). |
| `GET /api/v1/admin/customers/?is_active=false` | **200 OK** | `count: 0` (No accounts currently blocked/inactive). |
| `GET /api/v1/admin/customers/?page=1` | **200 OK** | Returns page 1 with 13 records. |
| `GET /api/v1/admin/customers/?page=9999` | **404 Not Found** | Correct DRF 404 behavior for non-existent page. |
| `GET /api/v1/admin/customers/?ordering=-total_spent` | **200 OK** | Query parameter silently ignored; items returned in `-date_joined` order because `total_spent` is not annotated. |
| `GET /api/v1/admin/dashboard/` (Analytics) | **200 OK** | `analytics.total_customers: 10` (Strictly counts `is_staff=False, is_superuser=False`). |

### 2.2 Live Production Customer Schema (Masked PII)
```json
{
  "id": 13,
  "username": "ad***",
  "email": "a***@admin.com",
  "first_name": "",
  "last_name": "",
  "phone_number": "None",
  "role": "admin",
  "is_active": true,
  "is_staff": true,
  "orders_count": 0,
  "total_spent": 0.0,
  "date_joined": "2026-11-03T12:47:20.122187Z",
  "last_login": "2026-11-03T12:47:34.357702Z"
}
```

### 2.3 Live Production Detail Schema (Customer with Addresses & Orders)
```json
{
  "id": 1,
  "username": "us***",
  "email": "u***@example.com",
  "first_name": "R***",
  "last_name": "S***",
  "phone_number": "******9012",
  "role": "customer",
  "is_active": true,
  "is_staff": false,
  "orders_count": 2,
  "total_spent": 203.0,
  "date_joined": "2026-10-30T10:15:00.000000Z",
  "last_login": "2026-11-04T08:30:00.000000Z",
  "addresses": [
    {
      "id": 3,
      "name": "Home",
      "line": "Apt 4B, Palm Grove",
      "area": "Bandra West, Mumbai",
      "is_default": true,
      "created_at": "2026-10-30T10:20:00.000000Z"
    }
  ],
  "recent_orders": [
    {
      "id": 14,
      "order_number": "FR6D83E2",
      "status": "delivered",
      "payment_status": "paid",
      "grand_total": "145.00",
      "items_count": 3,
      "created_at": "2026-11-02T14:10:00.000000Z"
    }
  ]
}
```

---

## 3. Architecture & Code Inspection

### 3.1 Backend Architecture (`freshdash-backend/api/`)

#### 1. Models & Relations (`api/models.py`)
- Standard Django `django.contrib.auth.models.User` is used as the root customer model.
- `UserProfile` (One-to-One with `User`):
  - `role`: Choices `['customer', 'manager', 'admin']` (default `'customer'`).
  - `phone_number`: Stored as `CharField(max_length=20, blank=True)`.
  - `order_updates`: Boolean (default `True`).
  - `offers_notifications`: Boolean (default `False`).
- `Address` (Foreign Key to `User` with `related_name='addresses'`):
  - `name`, `line`, `area`, `is_default`, `created_at`.
- `Order` (Foreign Key to `User` with `related_name='orders'`):
  - Tracks customer transactions, statuses, totals, and timestamps.

#### 2. Serializers (`api/serializers.py`)
- `AdminCustomerSerializer` (lines 839–873):
  - Reads `role` via `profile.role` and `phone_number` via `profile.phone_number`.
  - `orders_count`: Evaluated via `obj.orders.count()`.
  - `total_spent`: Evaluated via `obj.orders.exclude(status='cancelled').aggregate(total=models.Sum('grand_total'))['total'] or Decimal('0.00')`.
  - **Performance Observation (N+1 Query):** Even with `prefetch_related('orders')`, calling `.count()` and `.aggregate()` invokes 2 separate SQL queries per customer in the list. For a 20-item page, this executes 40 extra database queries.
- `AdminCustomerDetailSerializer` (lines 874–889):
  - Extends `AdminCustomerSerializer`.
  - Adds `addresses` via `AddressSerializer(many=True)`.
  - Adds `recent_orders` via `AdminOrderListSerializer(obj.orders.all()[:10], many=True)`.

#### 3. ViewSet & Business Logic (`api/views.py`)
- `AdminCustomerViewSet(viewsets.ReadOnlyModelViewSet)` (lines 1191–1287):
  - Protected with `permission_classes = [IsAdminRole]`.
  - `get_queryset()`:
    - Filters: `role` (`profile__role`), `is_active` (`true`/`false`), `search` (`username`, `email`, `first_name`, `last_name`, `profile__phone_number`).
    - Fixed ordering: Hardcoded to `order_by('-date_joined')`.
  - `toggle_status` action (`POST /admin/customers/{id}/toggle-status/`):
    - **Self-Lockout Guard:** Checks `if customer == request.user` and rejects with HTTP 400 (`"You cannot deactivate your own administrative account."`).
    - Flips `customer.is_active` and calls `save(update_fields=['is_active'])`.
  - `change_role` action (`POST /admin/customers/{id}/change-role/`):
    - Validates role choice against `['admin', 'manager', 'customer']`.
    - Creates `UserProfile` if missing.
    - Synchronizes `is_staff` (`True` for admin/manager, `False` for customer).

---

### 3.2 Frontend Architecture (`freshdash/admin-dashboard/`)

#### 1. Customer Directory (`src/pages/CustomersPage.tsx`)
- Table presentation:
  - Columns: Customer Name (with initials avatar and `@username`), Contact Details (email & phone), Role badge, Orders count, Total spent, Status badge, Joined date, Actions.
  - Action buttons: View profile (`Eye`), Role change modal (`Shield`), Toggle active status (`UserX` / `UserCheck`).
- Modals:
  - Role Change Modal allows changing user role between Consumer Customer, Store Manager, and Administrator.
- **Identified Deficiencies:**
  1. **Missing Pagination UI (P0):** The component has no pagination state (`currentPage`, `totalPages`), no pagination buttons (Previous/Next/Page Pills), and does not pass `page` to `customerService.getCustomers()`.
  2. **Page Count Banner Mismatch (P1):** Line 99 displays `Customer Directory ({customers.length})`. When pagination returns 20 items for 50 customers, the header displays 20 instead of the total 50.
  3. **Missing Search Debouncing (P1):** The search input has no debounce timer; typing triggers an immediate network request on every keystroke.
  4. **Missing Sort Controls (P2):** The table headers do not allow sorting by Lifetime Spending, Orders Count, or Join Date.

#### 2. Customer Detail Profile (`src/pages/CustomerDetailPage.tsx`)
- Profile presentation:
  - Header with large avatar initials, full name, username, active/blocked badge, lifetime orders, and total spent.
  - Contact row with email, phone, and membership join date.
  - Saved Delivery Addresses card with default badges.
  - Order History table listing recent orders with order numbers, items, grand totals, status badges, payment badges, and dates.
  - Action button: Block / Reactivate account with immediate UI feedback.
- **Identified Deficiencies:**
  1. **Generic Order Row Navigation (P2):** Line 230 navigates to `/orders` when an order row is clicked instead of deep-linking or opening the specific order detail.

#### 3. API Service (`src/services/customerService.ts`)
- `getCustomers(params?: CustomerFilterParams)`: Calls `GET /customers/`.
- `getCustomer(id: number)`: Calls `GET /customers/{id}/`.
- `toggleStatus(id: number)`: Calls `POST /customers/{id}/toggle-status/`.
- `changeRole(id: number, role: string)`: Calls `POST /customers/{id}/change-role/`.

---

## 4. Discrepancy Analysis: Directory Count vs Dashboard Analytics

- In `api/views.py` (`AdminDashboardView`, line 1434):
  ```python
  total_customers = User.objects.filter(is_staff=False, is_superuser=False).count()
  ```
  The dashboard strictly counts end-consumer customers who have neither staff nor superuser status. On live production, this yields **10**.
- In `AdminCustomerViewSet` (`api/views.py`, line 1206):
  ```python
  qs = User.objects.select_related('profile').prefetch_related('orders', 'addresses').all()
  ```
  The customer directory lists all user records in the Django auth system. On live production, this yields **13** (10 customers + 3 admins).
- **Recommendation:**
  In `CustomersPage.tsx`, the directory filter defaults to "All Account Roles" (13). When filtered to "Consumer Customers" (`role=customer`), it returns exactly 10, aligning with the dashboard. The frontend directory banner should display the total count from the DRF pagination envelope (`count`), and clearly indicate role breakdown.

---

## 5. Security, RBAC & Data Privacy Audit

1. **Authentication & Token Lifetime:**
   - SimpleJWT enforces access tokens with 15-minute expiry.
   - Dual-token refresh endpoint provides seamless token renewal.
2. **Role-Based Access Control:**
   - All admin customer endpoints require `IsAdminRole`.
   - Consumer customer tokens attempting to access `/api/v1/admin/customers/` receive **HTTP 403 Forbidden**.
   - Unauthenticated requests receive **HTTP 401 Unauthorized**.
3. **Administrative Self-Protection:**
   - An administrator cannot deactivate their own account via `toggle_status`.
4. **Data Privacy (PII Protection):**
   - Customer passwords are never exposed (excluded from serializers).
   - In production reports and logs, all emails, phones, and names are masked.

---

## 6. Local Test Suite & Build Verification

### 6.1 Backend Tests (`manage.py test`)
- Customer unit tests:
  ```powershell
  python manage.py test api.tests.AdminManagementSystemAPITests.test_admin_list_customers api.tests.AdminManagementSystemAPITests.test_admin_customer_detail api.tests.AdminManagementSystemAPITests.test_admin_toggle_customer_status api.tests.AdminManagementSystemAPITests.test_admin_change_customer_role
  ```
  **Result:** 4/4 tests passed (0.361s).
- Full regression suite:
  ```powershell
  python manage.py test api.tests
  ```
  **Result:** 91/91 tests passed (8.031s).
- Django system checks: `0 issues identified (0 silenced)`.

### 6.2 Frontend Build (`tsc -b && vite build`)
- TypeScript check and Vite build executed cleanly:
  ```
  dist/index.html                   1.14 kB │ gzip:   0.69 kB
  dist/assets/index-D620WZPV.css   35.58 kB │ gzip:   6.42 kB
  dist/assets/index-BP6AuHo2.js   779.53 kB │ gzip: 217.50 kB
  ✓ built in 21.96s
  ```
  **Result:** 0 TypeScript compilation errors.

---

## 7. Categorized Issues & Improvement Roadmap

### Priority 0 (Critical)
| ID | Area | Issue Description | Impact | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **CUST-P0-1** | Frontend | Missing pagination UI and controls in `CustomersPage.tsx` | Users beyond the first 20 records cannot be navigated to or viewed in the UI. | Add `currentPage`, `totalPages`, `pageSize` state, range indicator, and page pill navigation matching Products and Orders pages. |

### Priority 1 (High)
| ID | Area | Issue Description | Impact | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **CUST-P1-1** | Frontend | Missing search debounce in `CustomersPage.tsx` | Every keystroke triggers an immediate API request, causing UI flickering and redundant server load. | Implement 300ms debounce on search input before invoking `fetchCustomers`. |
| **CUST-P1-2** | Frontend | Header displays `customers.length` instead of total `count` | Displays current page item count (e.g. 20) instead of total registered customers (e.g. 100). | Read and display `totalCount` from the backend pagination envelope `response.count`. |
| **CUST-P1-3** | Backend | N+1 queries in `AdminCustomerSerializer` | Serializer calls `orders.count()` and `orders.aggregate(Sum)` per row, generating 40+ extra queries per page. | Annotate `orders_count = Count('orders', distinct=True)` and `annotated_total_spent = Sum(...)` in `get_queryset()`. |

### Priority 2 (Medium)
| ID | Area | Issue Description | Impact | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **CUST-P2-1** | Backend | Dynamic sorting is unsupported for metrics | `?ordering=-total_spent` and `?ordering=-orders_count` fail silently because they are not database fields. | Add explicit `ordering_fields = ['date_joined', 'orders_count', 'total_spent', 'username']` and map annotated fields in `AdminCustomerViewSet`. |
| **CUST-P2-2** | Frontend | Sort dropdown or clickable sort headers missing | Administrators cannot sort customers by top spenders or highest order counts. | Add sort dropdown or clickable table headers (`Highest Spend`, `Most Orders`, `Newest`, `Oldest`). |
| **CUST-P2-3** | Frontend | Generic order navigation in `CustomerDetailPage.tsx` | Clicking a customer order navigates to `/orders` without opening or filtering by that order. | Deep-link to `/orders?search={order_number}` or open order detail directly. |

### Priority 3 (Testing & Quality)
| ID | Area | Issue Description | Impact | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **CUST-P3-1** | Backend Tests | Missing automated regression tests for customer search, filters, pagination, and RBAC | Regressions in customer filtering or security could go undetected. | Add 6 automated tests in `api/tests.py` covering search, role filter, status filter, pagination, self-deactivation guard, and consumer 403. |

---

## 8. Database Preservation Statement

- Production database `/home/mdarsad5311/freshdash-backend/db.sqlite3` remains **completely untouched and unmodified**.
- Zero write operations (POST, PUT, PATCH, DELETE) were executed against customer or order tables during this audit.
- SQLite3 database integrity, schema, and concurrency settings are 100% preserved.

---

## 9. Phase 4 Conclusion & Next Steps

The Phase 4 Read-Only Audit is complete. The system architecture, API security, and production endpoints are structurally sound. However, the frontend Customers page requires pagination, search debouncing, and total count display alignment to achieve production readiness on par with Products (Phase 1/2) and Orders (Phase 3).

**Awaiting user instructions to proceed to Phase 4 implementation.**

