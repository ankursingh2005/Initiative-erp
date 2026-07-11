# Initiative ERP: Web + Android Play Store Setup

## 1) Make web app production-ready

1. Deploy backend with HTTPS (Render/Railway/AWS/VPS).
2. Use PostgreSQL in production (recommended instead of SQLite).
3. Set your domain, for example: https://erp.initiative.in
4. Verify these URLs work:
   - /login
   - /signup
   - /forgot-password
   - /dashboard
   - /manifest.webmanifest
   - /sw.js

## 2) PWA support already added in this codebase

This project now includes:
1. Manifest: static/manifest.webmanifest
2. Service worker: static/sw.js
3. PWA registration in login/signup/forgot_password/dashboard pages
4. FastAPI routes for:
   - /manifest.webmanifest
   - /sw.js

## 3) Build Android app (fastest route)

Use Android Studio WebView wrapper:

1. Create new Android project (Empty Activity).
2. In your WebView screen, load your HTTPS URL.
3. Enable:
   - JavaScript
   - DOM storage
   - file access if needed
4. Handle back press: if WebView can go back, navigate back.
5. Add internet permission in AndroidManifest.xml.
6. Build signed AAB from Android Studio.

## 4) Play Store requirements

1. Privacy Policy URL (public web page).
2. Data safety form in Play Console.
3. App icon (512x512), feature graphic, screenshots.
4. Target SDK must meet current Play requirements.

## 5) Recommended testing before upload

1. Login/signup/forgot password flow on Android device.
2. Dashboard tables, exports, role-based views.
3. Logout modal and session persistence.
4. Slow network behavior and offline fallback.

## 6) Notes

1. If you keep this as WebView app, updates happen mostly on the server.
2. For best long-term UX/performance, migrate to Flutter later.
