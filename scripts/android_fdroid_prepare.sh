#!/usr/bin/env bash
# Prepare F-Droid submission artifacts for the Android companion (Q25 scaffold).
# Generates a release keystore if missing; validates metadata files.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ANDROID="$ROOT/clients/android"
FDROID="$ANDROID/fdroid"
KEYSTORE="${LTS_ANDROID_KEYSTORE:-$ANDROID/release.keystore}"
KEYSTORE_PASS="${LTS_ANDROID_KEYSTORE_PASS:-change-me-before-release}"

echo "=== F-Droid prep: Linear Trend Spotter Android companion ==="

for f in "$FDROID/metadata/en-US/short_description.txt" "$FDROID/metadata/en-US/full_description.txt"; do
  if [ ! -f "$f" ]; then
    echo "FAIL: missing metadata file: $f"
    exit 1
  fi
done
echo "Metadata files: OK"

if [ ! -f "$KEYSTORE" ]; then
  if ! command -v keytool >/dev/null 2>&1; then
    echo "FAIL: keytool not found (install JDK)"
    exit 1
  fi
  echo "Generating release keystore at $KEYSTORE (store in secrets — never commit)"
  keytool -genkeypair -v \
    -keystore "$KEYSTORE" \
    -alias lts-release \
    -keyalg RSA -keysize 4096 -validity 10000 \
    -storepass "$KEYSTORE_PASS" \
    -keypass "$KEYSTORE_PASS" \
    -dname "CN=Linear Trend Spotter, OU=FOSS, O=Linear Trend Spotter, L=Local, ST=NA, C=US"
  echo "Created keystore. Set LTS_ANDROID_KEYSTORE and LTS_ANDROID_KEYSTORE_PASS in CI secrets."
else
  echo "Keystore exists: $KEYSTORE"
fi

echo ""
echo "Next steps (manual after APK exists):"
echo "  1. Implement Kotlin module per clients/android/README.md"
echo "  2. Build signed release APK with SOURCE_DATE_EPOCH set"
echo "  3. Submit to F-Droid: https://f-droid.org/docs/Submitting_an_App/"
echo "  4. Until then, users should install ntfy from F-Droid for Tier-C alerts"
