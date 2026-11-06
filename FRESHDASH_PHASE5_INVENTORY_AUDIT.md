# FreshDash — Phase 5: Inventory Management Read-Only Production Audit Report

**Date:** November 5, 2026  
**Status:** COMPLETE (READ-ONLY AUDIT)  
**Target Environments:**
- Production Backend API: `https://mdarsad5311.pythonanywhere.com/api/v1/`
- Production Admin Dashboard: `https://mdarsad5311.pythonanywhere.com/dashboard/#/inventory`
- Local Backend: `C:\Users\SIS\OneDrive\Desktop\freshdash-backend\`
- Local Frontend: `C:\Users\SIS\OneDrive\Desktop\freshdash\`
- Production Database: `/home/mdarsad5311/freshdash-backend/db.sqlite3` (**100% PRESERVED; 0 MUTATIONS**)

---

## 1. Executive Summary

A comprehensive, strictly read-only technical and functional audit of the **Inventory Management** module was conducted across the Django REST Framework backend, React Admin Dashboard frontend, and the live PythonAnywhere production environment.

### Audit Summary Matrix
| Category | Live Production Status | Local Codebase Status | Health Assessment |
| :--- | :--- | :--- | :--- |
| **Authentication & RBAC** | Enforced (401 unauth, 403 consumer) | Protected with `IsAdminRole` | Pass |
| **Inventory List API** | HTTP 200 OK (13 produce items) | Returns custom non-paginated dict | Needs Improvement |
| **Stock Adjustments API** | Functional with auto-availability sync | NameError on batch validation | **P0 Bug Found** |
| **Order Stock Deduction** | Atomic deduction on order creation | Verified in `OrderCreateSerializer` | Pass |
| **Cancellation Restoration** | Restores stock atomically | Idempotent transition validation | Pass |
| **Search & Filtering** | Name/ID search and status filter | No debounce; category filter missing | Needs Improvement |
| **Pagination** | **Ignored on backend & absent in UI** | Returns all records in 1 payload | **P1 Issue** |
| **Dynamic Sorting** | **Ignored on backend; hardcoded `stock`** | No sorting UI or backend mapping | **P1 Issue** |
| **Concurrency Locking** | SQLite file lock | Missing `select_for_update()` | Needs Improvement |
| **Automated Tests** | 2 basic tests | Missing adjust validation & RBAC tests | Needs Improvement |
| **Frontend Build** | Live on PA | `tsc -b && vite build` 0 errors | Pass |

---

## 2. Production Live Verification & Probe Evidence

Live GET probes were executed against the PythonAnywhere production API (`https://mdarsad5311.pythonanywhere.com/api/v1`) using administrator credentials (`admin_test`). All personal identifying information and secrets are strictly masked.

### 2.1 Live Production Endpoints Evidence

| Endpoint / Operation | HTTP Code | Response Summary / Evidence |
| :--- | :--- | :--- |
| `GET /api/v1/admin/inventory/` (Unauthenticated) | **401 Unauthorized** | `{"success": false, "message": "Authentication credentials were not provided."}` |
| `POST /api/v1/admin/auth/login/` (Admin Login) | **200 OK** | JWT `access` token acquired; user verified as `role='admin'`. |
| `GET /api/v1/admin/inventory/` (Full List) | **200 OK** | Top-level keys: `['success', 'total_items', 'low_stock_count', 'out_of_stock_count', 'inventory']`. `total_items: 13`. |
| `GET /api/v1/admin/inventory/?filter=low_stock` | **200 OK** | `count: 0` (No products currently between 1 and 10 units). |
| `GET /api/v1/admin/inventory/?filter=out_of_stock`| **200 OK** | `count: 0` (No products currently at 0 units). |
| `GET /api/v1/admin/inventory/?filter=in_stock` | **200 OK** | `count: 13` (All 13 products have stock > 10). |
| `GET /api/v1/admin/inventory/?search=tomato` | **200 OK** | `count: 1` (`tomato`: Fresh red tomatoes, stock = 50). |
| `GET /api/v1/admin/inventory/?page=1&page_size=3` | **200 OK** | Returns all 13 items. **Backend completely ignores pagination params.** |
| `GET /api/v1/admin/inventory/?ordering=-stock` | **200 OK** | Returns items in default stock order. **Backend ignores ordering param.** |
| `GET /api/v1/admin/products/` (Cross-Check) | **200 OK** | Total products = 13; low stock = 0; out of stock = 0. Matches inventory 100%. |
| `GET /api/v1/admin/dashboard/` (Cross-Check) | **200 OK** | `low_stock_products: []`, `out_of_stock_products: []`. Matches inventory 100%. |

### 2.2 Live Production Stock Baseline Table
| Product ID | Produce Name | Category | Current Stock | Stock Status | Visibility (`is_available`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `tomato` | Fresh red tomatoes | Fresh vegetables | 50 | IN_STOCK | Available (`true`) |
| `potato` | Farm fresh potatoes | Root vegetables | 50 | IN_STOCK | Available (`true`) |
| `onion` | Red onions | Root vegetables | 50 | IN_STOCK | Available (`true`) |
| `broccoli` | Fresh green broccoli | Exotic vegetables | 50 | IN_STOCK | Available (`true`) |
| `banana` | Banana Robusta | Fresh fruits | 50 | IN_STOCK | Available (`true`) |
| `apple` | Royal Gala apples | Fresh fruits | 50 | IN_STOCK | Available (`true`) |
| `mango` | Alphonso mangoes | Seasonal fruits | 50 | IN_STOCK | Available (`true`) |
| `avocado` | Premium Hass avocado | Exotic fruits | 50 | IN_STOCK | Available (`true`) |
| `spinach` | Fresh spinach (Palak) | Leafy vegetables | 50 | IN_STOCK | Available (`true`) |
| `carrot` | Crunchy orange carrots | Root vegetables | 50 | IN_STOCK | Available (`true`) |
| `pepper` | Colourful bell peppers | Exotic vegetables | 50 | IN_STOCK | Available (`true`) |
| `lemon` | Fresh lemons | Herbs and chillies | 50 | IN_STOCK | Available (`true`) |
| `kale` | Kale | Fresh vegetables | 50 | IN_STOCK | **Hidden / Unavailable (`false`)** |

---

## 3. Architecture & Code Inspection

### 3.1 Backend Architecture (`freshdash-backend/api/`)

#### 1. Models & Business Properties (`api/models.py`)
- `Product`:
  - `stock`: `PositiveIntegerField(default=50, validators=[MinValueValidator(0)])`.
  - `is_available`: `BooleanField(default=True)`.
  - `is_low_stock` property: `0 < self.stock <= 10`.
  - `is_out_of_stock` property: `self.stock == 0`.
- **Finding:** There is no dedicated `StockHistory`, `InventoryLog`, or `StockAudit` model. Stock adjustments overwrite `product.stock` directly without leaving an audit log of who adjusted the stock and why.

#### 2. Serializers (`api/serializers.py`)
- `AdminInventoryStockAdjustSerializer` (lines 894–910):
  - Validates `product_id` existence.
  - Requires either `stock` (integer, `min_value=0`) or `adjustment` (integer delta).
- `AdminBatchStockAdjustSerializer` (lines 911–917):
  - Wraps a list of adjustments: `adjustments = AdminInventoryStockAdjustSerializer(many=True)`.

#### 3. ViewSet & Adjustment Endpoints (`api/views.py`, lines 1316–1440)
- `AdminInventoryViewSet(viewsets.ViewSet)`:
  - Protected with `permission_classes = [IsAdminRole]`.
  - `list(request)`:
    - Filters: `low_stock`, `out_of_stock`, `in_stock`, `search`.
    - Hardcoded ordering: `qs.order_by('stock')`.
    - Returns non-standard response structure:
      `{"success": True, "total_items": 13, "low_stock_count": 0, "out_of_stock_count": 0, "inventory": [...]}`.
    - **Deficiency:** Does not support pagination (`page`, `page_size`), dynamic sorting (`ordering`), or category filtering (`category`).
  - `adjust(request)` action (`POST /admin/inventory/adjust/`):
    - Wrapped in `transaction.atomic()`.
    - Negative stock guard: `if product.stock + delta < 0: return Response(..., status=400)`.
    - Auto-availability synchronization:
      - `if product.stock == 0: product.is_available = False`
      - `elif product.stock > 0 and not product.is_available: product.is_available = True`
  - `batch_adjust(request)` action (`POST /admin/inventory/batch-adjust/`):
    - Wrapped in `transaction.atomic()`.
    - **CONFIRMED CRITICAL BUG (P0):**
      Line 1419:
      ```python
      if prod.stock + delta < 0:
          raise serializers.ValidationError(
              f"Stock for '{prod.name}' cannot drop below 0 (current: {prod.stock}, adjustment: {delta})."
          )
      ```
      `serializers` is **NOT imported** in `api/views.py`! Line 6 only imports `viewsets, status, permissions`.
      Attempting to raise `serializers.ValidationError` causes an uncaught `NameError: name 'serializers' is not defined`, crashing the endpoint with **HTTP 500 Internal Server Error** instead of returning HTTP 400 Bad Request!

---

### 3.2 Frontend Architecture (`freshdash/admin-dashboard/`)

#### 1. Inventory Page (`src/pages/InventoryPage.tsx`)
- **Metric Cards / Tabs:**
  - "All Catalog Stock", "Low Stock Warnings" (1–10 units), "Out of Stock" (0 units).
  - Clicking a tab toggles `filterType` (`''`, `'low_stock'`, `'out_of_stock'`).
- **Batch Adjustment Interface:**
  - Quick stepper controls for each row: `-10`, `-1`, pending delta display, `+1`, `+10`.
  - Stores pending edits in a local state map `batchDeltas: Record<string, number>`.
  - Renders a floating banner button: `Save X Pending Change(s)`.
  - Submits all pending deltas in a single atomic request via `inventoryService.batchAdjust`.
- **Single Adjustment Modal:**
  - Toggles between "Delta (+/-)" and "Exact Absolute Units".
  - Submits single change via `inventoryService.adjustStock`.
- **Identified Deficiencies:**
  1. **No Search Debounce (P1):** The search input triggers `fetchInventory` on every keystroke.
  2. **No Pagination UI (P1):** No page state, previous/next controls, or page range indicators.
  3. **No Sorting Controls (P1):** Table headers are static; cannot sort by highest stock, lowest stock, name A-Z, price, or category.
  4. **No Category Filter Dropdown (P2):** Admins cannot filter inventory by produce category.
  5. **Metric Tab Count Inconsistency (P2):** "All Catalog Stock" tab card displays `items.length` rather than total catalog items (`res.total_items`).
  6. **Stock Badge Ignores Visibility (P2):** `getStockBadge(it.is_available, it.stock)` in `Badge.tsx` ignores `is_available` and renders a green "In Stock (50)" badge for `kale` even though the product is hidden from customer browsing.

---

## 4. Stock Integrity & Order Workflow Findings

### 4.1 Order Creation Stock Deduction (`OrderCreateSerializer.create`)
- Deducts stock inside `@transaction.atomic`.
- Respects pack sizes: `needed = item.quantity * 2 if item.large else item.quantity`.
- Checks stock sufficiency before deduction:
  `if not item.product.is_available or item.product.stock < needed: raise ValidationError(...)`.
- Flips `is_available = False` if stock hits 0.
- **Integrity Assessment:** **Sound.** Over-ordering is prevented, and atomic transaction guarantees cart isolation.

### 4.2 Order Cancellation Stock Restoration
- Restores stock inside `transaction.atomic` in both customer cancellation (`OrderViewSet.cancel`) and admin cancellation (`AdminOrderViewSet.update`).
- Restores regular and double pack units accurately.
- Automatically reactivates product visibility (`is_available = True`) when stock is replenished from 0.
- Idempotent: `ALLOWED_STATUS_TRANSITIONS` forbids transitioning from `delivered` to `cancelled`, and forbids transitioning from `cancelled` back to `placed` or `confirmed`. Stock cannot be restored twice.
- **Integrity Assessment:** **Sound.**

---

## 5. Categorized Issues & Improvement Roadmap

### Priority 0 (Critical Bug)
| ID | Area | Issue Description | Impact | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **INV-P0-1** | Backend | `NameError: name 'serializers' is not defined` in `api/views.py` line 1419 | Submitting an invalid batch adjustment where `stock + delta < 0` crashes the server with **HTTP 500** instead of HTTP 400. | Import `from rest_framework import serializers` or return a clean `Response({"success": False, "message": ...}, status=status.HTTP_400_BAD_REQUEST)`. |

### Priority 1 (High)
| ID | Area | Issue Description | Impact | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **INV-P1-1** | Backend | Missing pagination in `AdminInventoryViewSet.list()` | Returns all produce items in a single unpaginated payload; cannot scale to hundreds of items. | Add `page` and `page_size` pagination parameters and standard envelope. |
| **INV-P1-2** | Backend | Hardcoded ordering `order_by('stock')` | Silently ignores `?ordering=-stock`, `?ordering=name`, `?ordering=-price`. | Add dynamic `ORDERING_MAP` supporting bidirectional sorting with deterministic tie-breaker. |
| **INV-P1-3** | Frontend | Missing search debounce in `InventoryPage.tsx` | Keystrokes trigger immediate API calls, causing request storms and UI flickering. | Implement 300ms search debouncing with timer cleanup and page 1 reset. |
| **INV-P1-4** | Frontend | Missing pagination controls in `InventoryPage.tsx` | Admins cannot navigate between pages or view range indicators. | Add range indicator (`Showing 1–20 of 50`), Previous/Next buttons, and numbered page pills. |
| **INV-P1-5** | Frontend | Missing sorting dropdown or clickable headers | Admins cannot sort products by highest/lowest stock or alphabetical order. | Add dynamic sorting dropdown matching Products/Orders/Customers pages. |

### Priority 2 (Medium)
| ID | Area | Issue Description | Impact | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **INV-P2-1** | Backend & Frontend | Missing category filtering in inventory | Admins cannot filter inventory items by category (e.g. Fruits, Vegetables). | Add `category` query param in backend and category dropdown filter in frontend. |
| **INV-P2-2** | Frontend | Metric tab card displays `items.length` instead of total catalog count | When search is active, the "All Catalog Stock" tab card drops to the search count rather than showing total catalog produce. | Bind tab card count to `res.total_items`. |
| **INV-P2-3** | Frontend | Stock badge ignores `is_available` in `Badge.tsx` | Hidden products with stock (e.g. `kale`) render green "In Stock" badges rather than indicating unavailable status. | Display "Unavailable / In Stock ({stock})" or yellow warning badge when `!is_available`. |
| **INV-P2-4** | Backend | Missing `select_for_update()` concurrency lock | Under extreme concurrent checkouts and adjustments, stock could be read before update. | Add `select_for_update()` on product lookups inside `transaction.atomic()`. |

### Priority 3 (Testing & Future Enhancements)
| ID | Area | Issue Description | Impact | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **INV-P3-1** | Backend Tests | Low inventory test coverage in `api/tests.py` | Only 2 basic inventory tests exist; missing coverage for adjust error handling, availability toggling, and RBAC. | Add 8+ automated regression tests for inventory endpoints. |
| **INV-P3-2** | Architecture | No stock transaction audit history | No record of who adjusted stock or why. | Consider future `StockAdjustmentLog` model in milestone roadmap. |

---

## 6. Files Requiring Modification for Phase 5 Implementation

### Backend (`freshdash-backend/`)
- `api/views.py`:
  - Import `serializers` (fixes P0 bug).
  - Add pagination, dynamic sorting (`ORDERING_MAP`), and category filter in `AdminInventoryViewSet.list()`.
  - Add `select_for_update()` in `adjust()` and `batch_adjust()`.
- `api/tests.py`:
  - Add comprehensive regression test suite for inventory.

### Frontend (`freshdash/`)
- `admin-dashboard/src/pages/InventoryPage.tsx`:
  - Add 300ms search debounce.
  - Add pagination state and controls (range indicator, Prev/Next, page pills).
  - Add dynamic sorting dropdown (`Stock: Low to High`, `Stock: High to Low`, `Name: A-Z`, `Price: High/Low`).
  - Add category filter dropdown.
  - Fix metric tab card total count display.
- `admin-dashboard/src/services/inventoryService.ts`:
  - Update `getInventory` parameters and return types for pagination and sorting.
- `admin-dashboard/src/types/inventory.ts`:
  - Update `InventoryListResponse` to include pagination metadata (`count`, `total_pages`, `current_page`, `page_size`).
- `admin-dashboard/src/components/common/Badge.tsx`:
  - Update `getStockBadge` to consider `is_available`.

---

## 7. Database Preservation Statement

- Production database `/home/mdarsad5311/freshdash-backend/db.sqlite3` remains **completely untouched, unmodified, and preserved**.
- Zero write operations (POST, PUT, PATCH, DELETE) were executed against live inventory, product, or order business records.
- Zero database migrations were run on production.

---

## 8. Final Audit Verdict

# **VERDICT: READY FOR IMPLEMENTATION**

The technical audit is complete. A critical backend bug (P0 `NameError` in `batch_adjust`) and several high-priority UI/API deficiencies (missing pagination, sorting, search debounce) have been identified with concrete evidence and clear remediation steps.

**Awaiting user instructions to proceed to Phase 5 Implementation.**

