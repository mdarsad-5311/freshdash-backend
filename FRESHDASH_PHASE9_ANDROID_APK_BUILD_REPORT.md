# FreshDash — Phase 9: Android Preview APK Build & Testing Report

**Date:** November 5, 2026  
**Build Target:** Standalone Android Preview APK  
**Build Status:** **FINISHED (SUCCESS)**  
**EAS Build ID:** `d49270e0-f806-48f3-9a18-86827e52406f`  
**EAS Project:** `@mdarsad/freshdash` (`72fdb8da-e836-42b0-95c8-010b8f027726`)  
**Package Identifier:** `com.freshdash.app`  
**App Version:** `1.0.0` (versionCode: `1`)  
**Expo SDK:** `57.0.0` (React Native `0.86.3`, React `19.2.3`)  
**Target Backend API:** `https://mdarsad5311.pythonanywhere.com/api/v1`  
**Official APK Artifact URL:** [application-d49270e0-f806-48f3-9a18-86827e52406f.apk](https://expo.dev/artifacts/eas/oIVTctPEFABY2cFmvOK3YbpX-VpDtngN8WN15RPgd2k.apk)  
**EAS Build Logs:** [View Build on Expo Dashboard](https://expo.dev/accounts/mdarsad/projects/freshdash/builds/d49270e0-f806-48f3-9a18-86827e52406f)

---

## 1. Executive Summary

Phase 9 successfully generated a new native Android Preview APK incorporating all Phase 7 mobile integration improvements:
1. **Backend-Persisted Favorites (P1):** Full bidirectional synchronization with the Django `/api/v1/favorites/` endpoint, optimistic UI with rollback, and session-scoped persistence.
2. **Dynamic FAQs Accordion (P2):** Dynamic FAQ fetching from `/api/v1/faqs/` with loading skeleton, smooth collapsible accordion, and seamless fallback to 8 local FAQs on network failure.
3. **Product Image URL Resolution (P2):** Absolute image resolution via `resolveMediaUrl()` for both relative Django media paths (`/media/products/...`) and external CDNs, with produce-themed placeholder fallbacks.

The build was compiled, signed with the managed EAS Keystore (`Build Credentials 1peq6A31AD`), and verified on the EAS CDN. Zero changes were made to production data or PythonAnywhere backend configurations.

---

## 2. Pre-Build Verification Results

| Check | Expected | Actual Result | Status |
| :--- | :--- | :--- | :--- |
| **EAS CLI** | Installed & operational | `eas-cli/27.4.1 win32-x64 node-v24.14.0` | **PASS** |
| **Authenticated Account**| `mdarsad` | `mdarsad` (`alumaimatechforge@gmail.com`) | **PASS** |
| **EAS Project ID** | `72fdb8da-e836-42b0-95c8-010b8f027726` | `@mdarsad/freshdash` (`72fdb8da-e836-42b0-95c8-010b8f027726`) | **PASS** |
| **Build Profile** | `preview` | Profile `preview` (distribution: internal) | **PASS** |
| **Artifact Output Type** | Standalone `.apk` | `android.buildType: "apk"` | **PASS** |
| **Target API Injected** | Production PythonAnywhere URL | `EXPO_PUBLIC_API_URL: https://mdarsad5311.pythonanywhere.com/api/v1` | **PASS** |
| **Dev URL Leakage** | Zero localhost / emulator IPs | No `10.0.2.2` or `localhost` in preview build | **PASS** |
| **Automated Test Suite** | All tests passing | 17/17 test suites, 104/104 tests passed | **PASS** |
| **TypeScript Compilation**| Zero errors | `tsc --noEmit` exited clean (code 0) | **PASS** |
| **ESLint Analysis** | Zero errors | `eslint` on target files exited clean (code 0) | **PASS** |

---

## 3. Build Execution Details

```text
Build ID:                 d49270e0-f806-48f3-9a18-86827e52406f
Platform:                 Android
Build Profile:            preview
Distribution:             internal
Target Build Type:        apk
Package Name:             com.freshdash.app
App Version:              1.0.0
Version Code:             1
SDK Version:              57.0.0
React Native:             0.86.3
Build Fingerprint:        77c7acdb415e6ace6e2d06fbee35b5f424d33fce
Started At:               November 5, 2026, 6:14:28 PM IST
Finished At:              November 5, 2026, 6:35:56 PM IST
Total Build Time:         ~21 minutes 28 seconds
Triggered By:             mdarsad
Status:                   finished (SUCCESS)
```

---

## 4. Artifact Verification

Direct HTTP header inspection of the generated artifact verified its integrity:
- **HTTP Status:** `200 OK`
- **MIME Content-Type:** `application/octet-stream`
- **Content-Disposition:** `attachment; filename="application-d49270e0-f806-48f3-9a18-86827e52406f.apk"`
- **Exact File Size:** `112,727,614 bytes` (~107.5 MB)
- **ETag:** `"fc0e0a16e200ca3d2cb625b259a61fa9"`
- **CDN Host:** `wf-artifacts.eascdn.net` via Cloudflare
- **Direct Download Link:** `https://expo.dev/artifacts/eas/oIVTctPEFABY2cFmvOK3YbpX-VpDtngN8WN15RPgd2k.apk`

---

## 5. Real-Device Manual Testing Checklist

Testers should install the APK directly on an Android 10+ handset and execute the following 14-point test sequence:

> [!CAUTION]
> **Production Safety Notice:**
> The APK communicates directly with the live production backend. Do not place dummy or unauthorized orders without explicit approval. Use identified test accounts for end-to-end checkout validation.

| # | Test Area | Test Scenario & Verification Steps | Expected Result | Pass / Fail |
|---|---|---|---|---|
| **1** | **Install & Launch** | Download APK via mobile browser, allow "Install from unknown sources", and tap the FreshDash icon. | App launches smoothly, white splash screen with FreshDash logo dismisses, and Home tab renders. | [ ] |
| **2** | **Customer Login** | Navigate to Profile tab -> Tap Login -> Sign in with existing credentials (`fresh_foodie` / `FreshFoodie123!`). | Bearer token saved to SecureStore, user profile displays name, phone, and email immediately. | [ ] |
| **3** | **Customer Signup** | Log out, tap "Create Account", submit valid details (or verify inline validation prevents invalid inputs). | Form validates phone/email, sends request to `/api/v1/auth/signup/`, logs in automatically upon success. | [ ] |
| **4** | **Logout & Session Clear** | From Profile tab, tap "Logout" button. | SecureStore tokens deleted, cart and favorites local state reset, app returns to unauthenticated state. | [ ] |
| **5** | **Browse Catalog** | Browse Home tab and Categories tab. Tap various categories (Vegetables, Fruits, Herbs). | 9 categories load, products grid shows prices, weights, and stock badges accurately. | [ ] |
| **6** | **Product Details & Images** *(Phase 7)* | Tap a product card (e.g., Alphonso Mango, Organic Spinach) to open Product Details screen. | Full product image loads via `resolveMediaUrl()` from PythonAnywhere media; placeholder displays if no image. | [ ] |
| **7** | **Favorites Persistence** *(Phase 7)* | Log in, tap heart icon on 2 products. Force-close and restart the app. Re-open app. | Heart icons remain highlighted red. Favorites tab lists the saved products from `/api/v1/favorites/`. | [ ] |
| **8** | **Favorites Optimistic Rollback** *(Phase 7)* | Disconnect Wi-Fi/cellular. Tap heart icon on an un-favorited item. | Heart highlights optimistically, then reverts back with a friendly network error alert. | [ ] |
| **9** | **Dynamic FAQs Accordion** *(Phase 7)* | Navigate to Profile -> Help & Support / FAQs section. | FAQs load dynamically from `/api/v1/faqs/`. Tapping a question smoothly expands/collapses the answer. | [ ] |
| **10** | **FAQ Offline Fallback** *(Phase 7)* | Turn on Airplane mode, re-enter FAQs section. | App falls back to the 8 hardcoded local FAQ items; user never sees a broken or blank screen. | [ ] |
| **11** | **Cart Operations** | Add products from Home/Details. Navigate to Cart tab. Increase quantity with `+`, decrease with `-`. | Quantities update instantly, order subtotal recalculates dynamically, out-of-stock items block addition. | [ ] |
| **12** | **Address Management** | From Cart/Checkout, view saved delivery addresses. Select an address or add a new delivery address. | Saved addresses from `/api/v1/addresses/` populate cleanly with complete address fields. | [ ] |
| **13** | **Token Refresh Mutex** | Leave the app idle in background until access token expires (~15-60 min). Reopen and perform an action. | Silent background token refresh via `/auth/token/refresh/` succeeds without logging the user out. | [ ] |
| **14** | **Offline Network Handling** | Disable network while browsing. Perform an action that requires network. | Clean, user-friendly alert appears ("Network error. Please check your connection.") without crashing. | [ ] |

---

## 6. Known Limitations & Next Steps

### Limitations:
1. **Google Play Store:** This build is a standalone preview APK (`preview` profile), not an Android App Bundle (`.aab`). It cannot be uploaded directly to Google Play production tracks without running `eas build -p android --profile production`.
2. **Version Code:** Built with `versionCode: 1`. When preparing for Google Play submission, `versionCode` must be incremented to `2` in `app.json`.
3. **EAS Update (OTA):** Not enabled. Future JavaScript changes will require another native EAS build until `expo-updates` is configured.
4. **iOS Build:** Pending iOS configuration (`bundleIdentifier`) and Apple Developer Program credentials.

### Recommended Next Actions:
1. Distribute the APK link to QA testers and stakeholders:
   `https://expo.dev/artifacts/eas/oIVTctPEFABY2cFmvOK3YbpX-VpDtngN8WN15RPgd2k.apk`
2. Perform physical handset verification using the 14-point checklist above.
3. Upon QA sign-off, configure Google Play Console prerequisites (Developer Account, Store Listing graphics, Privacy Policy URL) for Phase 10 production release.

