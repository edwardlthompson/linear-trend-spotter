# Linear Trend Spotter — Android companion (Q25 scaffold)

FOSS Android app using **UnifiedPush** with an ntfy-compatible distributor. No Google Play Services or Firebase.

## Status

Scaffold only — implement Kotlin module under `app/` when Sprint 8 is approved.

## Target architecture

1. User selects UnifiedPush distributor (ntfy, UP-FCM-free, etc.).
2. Worker Tier-C (`NTFY_*`) publishes list-change messages to the user's topic.
3. App receives push via UP and shows a system notification with deep link to the dashboard.

## Alternative

Foreground `Service` polling `qualified_public_snapshot.json` hourly — higher battery cost; document in app UI.

## Distribution

- F-Droid ([submission checklist](https://f-droid.org/docs/Submitting_an_App/)) — metadata in `fdroid/metadata/en-US/`
- Reproducible builds with `SOURCE_DATE_EPOCH` per project FOSS rules

### F-Droid automation (scaffold)

```bash
bash scripts/android_fdroid_prepare.sh
```

Generates `release.keystore` if missing (gitignored) and validates metadata. Full F-Droid tracker submission requires a built signed APK ([ADB] after Kotlin module exists).

## Module activation

Starting native Android work activates **Module A** rules in `AGENTS.md` and `.cursor/rules/foss-compliance.mdc`.

## Related docs

- [`docs/WEB_DASHBOARD.md`](../../docs/WEB_DASHBOARD.md) — Tier-C ntfy
- [`scanner/ntfy_notify.py`](../../scanner/ntfy_notify.py) — worker publisher
