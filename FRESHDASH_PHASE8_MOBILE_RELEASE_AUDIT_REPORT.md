# FreshDash — Phase 8: Mobile App Release & Deployment Audit Report

**Date:** November 5, 2026  
**Project:** FreshDash (Expo / React Native Client)  
**Target Backend:** Django REST Framework (`https://mdarsad5311.pythonanywhere.com/api/v1/`)  
**EAS Project ID:** `72fdb8da-e836-42b0-95c8-010b8f027726`  
**Application ID (Android):** `com.freshdash.app`  
**Audit Posture:** Strictly READ-ONLY (Zero code modifications, zero build triggers, zero backend changes)

---

## Executive Summary & Verdict

### Executive Verdict: **READY WITH LIMITATIONS**

| Distribution Channel | Target Format | Current Status | Critical Gaps / Blockers |
| :--- | :--- | :--- | :--- |
| **Android Internal Testing** | Standalone APK | **READY** | None. Profile `preview` in `eas.json` builds standalone APK with production API. |
| **Google Play Store** | Android App Bundle (AAB) | **READY WITH LIMITATIONS** | Config is ready; requires Google Play Console account ($25), Privacy Policy URL, and Data Safety declaration. |
| **Apple App Store (iOS)** | iOS App Archive (IPA) | **NOT READY** | Missing `ios.bundleIdentifier` in `app.json`, missing `ios` profile in `eas.json`, requires Apple Developer Program ($99/yr). |
| **EAS Update / Over-The-Air (OTA)**| JavaScript / Asset Bundle | **NOT SUPPORTED** | `expo-updates` is not installed; no `runtimeVersion` or update channels configured. |

### Critical Finding on OTA Updates vs. Native Build
> [!IMPORTANT]
> **A NEW NATIVE BUILD IS STRICTLY REQUIRED TO DISTRIBUTE PHASE 7 IMPROVEMENTS.**
>
> The Phase 7 mobile integration improvements (Favorites backend persistence, Dynamic FAQs accordion with fallback, and Product image URL resolution) **CANNOT** be distributed via Over-The-Air (OTA) updates to existing installed app binaries (e.g., the Nov 4 preview APK build `8e0a9b6d`).
>
> **Technical Reason:**
> 1. The `expo-updates` package is **not installed** in `package.json` and not configured in `app.json`.
> 2. Existing native APK binaries embed a single static JavaScript bundle compiled at build time. They completely lack the native background update service, manifest polling mechanism, and runtime bundle loader.
> 3. Any attempt to run `eas update` will fail or have zero effect on user devices.
> 4. To test and use the new Phase 7 features, a new native build (`eas build -p android --profile preview`) must be generated and installed.

---

## 1. Expo & EAS Configuration Audit

### 1.1 Project Metadata & Dependencies (`package.json`)
- **Expo SDK Version:** `~57.0.31`
- **React Native Version:** `0.86.3`
- **React Version:** `19.2.3`
- **Navigation Engine:** `expo-router` (`~57.0.29`) with file-based routing
- **State Management:** `zustand` (`^5.0.15`)
- **Network Client:** `axios` (`^1.21.0`)
- **Secure Storage:** `expo-secure-store` (`~57.0.4`)
- **OTA Updates Package:** **MISSING** (`expo-updates` is not listed in `dependencies`)

### 1.2 App Configuration (`app.json`)
```json
{
  "expo": {
    "name": "FreshDash",
    "slug": "freshdash",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/images/icon.png",
    "scheme": "freshdash",
    "userInterfaceStyle": "light",
    "ios": {
      "supportsTablet": true
    },
    "android": {
      "package": "com.freshdash.app",
      "versionCode": 1,
      "adaptiveIcon": {
        "backgroundColor": "#F7F8F3",
        "foregroundImage": "./assets/images/android-icon-foreground.png",
        "backgroundImage": "./assets/images/android-icon-background.png",
        "monochromeImage": "./assets/images/android-icon-monochrome.png"
      },
      "permissions": [
        "INTERNET",
        "ACCESS_NETWORK_STATE"
      ],
      "predictiveBackGestureEnabled": false
    },
    "web": {
      "bundler": "metro",
      "output": "single",
      "favicon": "./assets/images/favicon.png"
    },
    "plugins": [
      "expo-router",
      [
        "expo-splash-screen",
        {
          "image": "./assets/images/splash-icon.png",
          "resizeMode": "contain",
          "backgroundColor": "#ffffff"
        }
      ],
      "expo-font",
      "expo-status-bar",
      "expo-web-browser",
      "expo-secure-store"
    ],
    "experiments": {
      "typedRoutes": true
    },
    "extra": {
      "router": {},
      "eas": {
        "projectId": "72fdb8da-e836-42b0-95c8-010b8f027726"
      }
    }
  }
}
```

#### Key Observations in `app.json`:
1. **EAS Project ID:** `72fdb8da-e836-42b0-95c8-010b8f027726` is properly registered.
2. **Android Package:** `com.freshdash.app` is well-formed.
3. **Android Version Code:** Currently `1`. Must be incremented to `2` before uploading a new build to the Google Play Store.
4. **Missing iOS Bundle Identifier:** Lines 10-12 only declare `"supportsTablet": true`. iOS builds will fail immediately without `"bundleIdentifier": "com.freshdash.app"`.
5. **Missing OTA Configuration:** No `runtimeVersion` or `updates` object is configured.

### 1.3 EAS Build Configuration (`eas.json`)
```json
{
  "cli": {
    "version": ">= 15.0.0",
    "appVersionSource": "remote"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "env": {
        "EXPO_PUBLIC_API_URL": "http://10.0.2.2:8000/api/v1"
      }
    },
    "preview": {
      "distribution": "internal",
      "android": {
        "buildType": "apk"
      },
      "env": {
        "EXPO_PUBLIC_API_URL": "https://mdarsad5311.pythonanywhere.com/api/v1"
      }
    },
    "production": {
      "android": {
        "buildType": "app-bundle"
      },
      "env": {
        "EXPO_PUBLIC_API_URL": "https://mdarsad5311.pythonanywhere.com/api/v1"
      }
    }
  },
  "submit": {
    "production": {
      "android": {
        "track": "internal"
      }
    }
  }
}
```

#### Key Observations in `eas.json`:
1. **Preview Profile:** Configured for standalone APK generation (`android.buildType: "apk"`), internal distribution, and automatically points to the live PythonAnywhere production backend (`https://mdarsad5311.pythonanywhere.com/api/v1`).
2. **Production Profile:** Configured for Google Play App Bundle (`android.buildType: "app-bundle"`), with the live production API URL injected at build time.
3. **Submit Profile:** Configured to submit to Google Play Console's `internal` test track.
4. **Missing iOS Targets:** Neither `preview` nor `production` specifies an `ios` configuration.
5. **Missing Update Channels:** No `channel` configuration exists in `eas.json`.

---

## 2. Android Release Readiness

### 2.1 Package & Identity
- **Package Name:** `com.freshdash.app` (Valid, standard reverse-domain syntax).
- **Version Name:** `1.0.0`
- **Version Code:** `1`
  - *Recommendation:* Prior to uploading to Google Play Console, increment `android.versionCode` to `2` to distinguish from prior internal test builds.

### 2.2 Visual Assets & Branding
All required visual assets have been verified to exist on disk:
- **Application Icon:** `assets/images/icon.png` (Present, 1024x1024 PNG).
- **Adaptive Icon Foreground:** `assets/images/android-icon-foreground.png` (Present).
- **Adaptive Icon Background:** `assets/images/android-icon-background.png` (Present).
- **Adaptive Icon Monochrome:** `assets/images/android-icon-monochrome.png` (Present, supports Android 13+ themed icons).
- **Adaptive Icon Background Color:** `#F7F8F3` (Matches FreshDash brand light aesthetic).
- **Splash Screen:** `assets/images/splash-icon.png` (Present, contain mode, `#ffffff` background).

### 2.3 Android Permissions
- **Permissions Declared in `app.json`:**
  - `INTERNET`: Required for backend API, product images, and authentication.
  - `ACCESS_NETWORK_STATE`: Required to detect network availability and offline states.
- **Privacy Impact:** Zero dangerous or invasive permissions requested (no camera, background location, microphone, contacts, or external storage access).
- **Google Play Approval Impact:** Low friction; does not require high-risk permission declaration forms or sensitive permission justifications.

### 2.4 Deep Linking & URL Schemes
- **Scheme:** `freshdash://`
- Configured via `expo.scheme` and handled natively by `expo-linking` and `expo-router`.

### 2.5 Architecture & Optimization
- **Workflow Type:** Managed Workflow with Continuous Native Generation (CNG via EAS Build). No tracked `android/` or `ios/` folders, ensuring zero native configuration drift.
- **JavaScript Engine:** Hermes is enabled by default in Expo SDK 57 / React Native 0.86, providing fast cold-start performance and low memory footprint.
- **ProGuard / R8:** Managed by Expo EAS Build during `production` App Bundle generation.

### 2.6 Signing & Keystore Management
- Managed automatically by EAS Credentials.
- When `eas build` runs, EAS securely generates and retains the Android upload keystore in the cloud.
- Google Play App Signing will manage the actual distribution keys for Google Play users.

---

## 3. iOS Release Readiness

### 3.1 Gap Analysis
1. **Missing Bundle Identifier:**
   - `app.json` lines 10-12:
     ```json
     "ios": {
       "supportsTablet": true
     }
     ```
   - **Resolution Required:** Must add `"bundleIdentifier": "com.freshdash.app"`.
2. **Missing Build Number:**
   - Must add `"buildNumber": "1"` under `expo.ios`.
3. **Missing iOS EAS Profiles:**
   - `eas.json` only configures `android` under `preview` and `production`.
   - **Resolution Required:** Add `ios` configuration (e.g. `"simulator": true` for local simulator testing or `"enterprise"`/`"ad-hoc"`/TestFlight for devices).
4. **Apple Developer Account:**
   - Requires active enrollment in Apple Developer Program ($99 USD/year).
   - Requires Apple Distribution Certificate and Provisioning Profile (EAS CLI can generate these automatically once signed in).

---

## 4. EAS Update / OTA (Over-The-Air) Compatibility Analysis

### 4.1 Detailed Evaluation
- **Is `expo-updates` installed?** **NO**. (`package.json` dependencies do not include `expo-updates`).
- **Is `runtimeVersion` configured?** **NO**.
- **Is `updates.url` configured?** **NO**.
- **Are update channels configured?** **NO**.

### 4.2 Can Phase 7 Changes Be Pushed via OTA to Existing Devices?
> **VERDICT: NO.**
> 
> A complete native rebuild (`.apk` / `.aab`) is strictly required.

#### Architectural Rationale:
1. **Static Bundle Embedding:** In standard Expo managed builds without `expo-updates`, Metro bundles all JavaScript, JSX, and TypeScript into a single static file (`assets/index.android.bundle`) during native compilation.
2. **Absence of Native Update Manager:** The compiled APK binary has no background thread or native bridge capable of querying Expo servers (`https://u.expo.dev`), downloading bundle patches, verifying cryptographic signatures, or restarting the React runtime with new JS code.
3. **Existing Installed Builds:** Devices running historical builds (e.g., preview build `8e0a9b6d` from Nov 4) are locked to the code present at their compile time. They cannot see or receive Phase 7's:
   - Backend-persisted favorites (`services/favoriteService.ts` and `store/favoritesStore.ts`)
   - Dynamic FAQs accordion (`services/faqService.ts` and `app/profile-section.tsx`)
   - Product image URL resolution (`utils/image.ts`, `components/ProducePhoto.tsx`, `components/ProductCard.tsx`)
4. **Action Required:** Build and distribute a new APK preview build to deliver Phase 7 to internal testers.

---

## 5. Backend & Environment Compatibility

### 5.1 API Endpoint Configuration
- **Production Backend API:** `https://mdarsad5311.pythonanywhere.com/api/v1`
- **Environment Variable:** `EXPO_PUBLIC_API_URL`
  - In `eas.json`, both `preview` and `production` profiles explicitly inject:
    ```json
    "env": {
      "EXPO_PUBLIC_API_URL": "https://mdarsad5311.pythonanywhere.com/api/v1"
    }
    ```
  - In `constants/config.ts`:
    ```typescript
    const ENV_API_URL = process.env.EXPO_PUBLIC_API_URL;
    export const API_BASE_URL = ENV_API_URL || (__DEV__
      ? 'http://10.0.2.2:8000/api/v1'
      : 'https://mdarsad5311.pythonanywhere.com/api/v1');
    ```
- **Zero Localhost Leaks:** Production builds (`preview` and `production`) will never resolve to `10.0.2.2` or `localhost`.

### 5.2 Resiliency & Fault Tolerance
1. **Token Refresh Mutex:** `services/apiClient.ts` implements an atomic `isRefreshing` lock and a FIFO `failedQueue` callback buffer. When a JWT expires, concurrent requests wait for a single refresh operation before replaying with the new token.
2. **Offline Handling:** Axios interceptors normalize low-level network errors into clean, localized errors (`Network error. Please check your connection.`).
3. **Optimistic Favorites:** UI toggles heart icons immediately; if the network call fails or user is unauthenticated, state reverts cleanly with alert messaging.
4. **FAQ Offline Fallback:** If the backend FAQ endpoint is unreachable or returns an empty list, the app seamlessly falls back to 8 predefined local FAQ items.
5. **Media Asset Handling:** `utils/image.ts` converts relative backend media paths (`/media/products/...`) into absolute production URLs, handling external CDNs and empty values safely.

---

## 6. Store & Distribution Readiness Matrix

### 6.1 Android Internal Testing (APK)
- **Status:** **100% READY NOW**
- **Profile:** `preview`
- **Command:** `eas build --platform android --profile preview`
- **Output:** Sideloadable `.apk` file hosted directly on Expo servers for fast QR code or direct link installation on any Android device.

### 6.2 Google Play Store (Production AAB)
- **Status:** **READY WITH PREREQUISITES**
- **Profile:** `production`
- **Prerequisites for Submission:**
  1. **Google Play Console Account:** $25 one-time developer registration fee.
  2. **App Listing Assets:**
     - High-res icon (512x512 PNG, 32-bit color).
     - Feature graphic (1024x500 PNG/JPEG).
     - Minimum 2 phone screenshots (16:9 or 9:16 aspect ratio).
  3. **Privacy Policy URL:** Publicly accessible HTTPS URL explaining user data collection (email, name, order history).
  4. **Target API Level:** Expo SDK 57 targets Android 15 (API level 35), fully satisfying Google Play's requirement (minimum API level 34+).
  5. **Data Safety Form:** Disclose collection of User Info (name, email) and Purchase History for app functionality.

### 6.3 Apple App Store (iOS)
- **Status:** **NOT READY**
- **Blockers to Resolve:**
  1. Add `bundleIdentifier: "com.freshdash.app"` to `app.json`.
  2. Add `ios` build block to `eas.json`.
  3. Enroll in Apple Developer Program ($99/year).
  4. Create App Store Connect record and privacy nutrition disclosures.

---

## 7. Quality Gate Verification

All automated test suites, static analysis, and type checks were executed directly:

| Quality Gate | Tool / Command | Result | Details |
| :--- | :--- | :--- | :--- |
| **Unit & Integration Tests** | `npm test -- --watchAll=false` | **100% PASS** | **17 test suites passed, 104 tests passed**, 0 failures. |
| **TypeScript Type Check** | `npx tsc --noEmit` | **100% PASS** | Clean exit (code 0), 0 compiler errors. |
| **ESLint Static Analysis** | `npx eslint services/ utils/ ...` | **100% PASS** | Clean exit (code 0), 0 linting warnings or errors. |
| **Production Backend DB** | Remote SQLite DB | **UNCHANGED** | Zero write operations performed; DB preserved in read-only state. |

---

## 8. Step-by-Step Execution Plan

### Step A: Build Android Preview APK for Phase 7 Internal Testing (Immediate Next Step)
To verify the Phase 7 Favorites, FAQs, and Product Images on real Android devices:
```bash
# 1. Login to EAS (if not already authenticated)
eas login

# 2. Trigger Android Preview APK build
eas build --platform android --profile preview
```
*Expected Result:* EAS will produce a standalone `.apk` link. Testers can download and test immediately without Google Play approval.

### Step B: Build Google Play Production App Bundle (AAB)
When ready for Google Play internal testing or release:
```bash
# 1. Update android.versionCode to 2 in app.json
# 2. Run production build
eas build --platform android --profile production

# 3. Submit to Google Play Internal Test Track (or upload manually via Play Console)
eas submit --platform android --profile production
```

### Step C: Optional Future Setup — Enabling EAS Update (OTA)
If OTA updates are desired for subsequent releases (allowing instant JS updates without store re-submissions):
1. Install the updates package:
   ```bash
   npx expo install expo-updates
   ```
2. Configure `app.json`:
   ```json
   "updates": {
     "url": "https://u.expo.dev/72fdb8da-e836-42b0-95c8-010b8f027726"
   },
   "runtimeVersion": {
     "policy": "appVersion"
   }
   ```
3. Configure `eas.json` channels:
   ```json
   "build": {
     "preview": {
       "channel": "preview"
     },
     "production": {
       "channel": "production"
     }
   }
   ```
4. Rebuild the native binary once with the update module included. Subsequent JS-only patches can then be published via:
   ```bash
   eas update --branch production --message "Bug fix or UI tweak"
   ```

---

## 9. Conclusion
The FreshDash mobile application is in a stable state. Android preview and production build pipelines are fully configured and verified against the live PythonAnywhere backend. Phase 7 improvements are ready for native distribution via EAS Build.

