#!/bin/bash
# Runs the screenshot tour on the emulator and copies the pictures to ./out.
# Called by .github/workflows/screenshots.yml once the emulator has booted.
set -u
PKG=ai.pickup.app
APK=android/app/build/outputs/apk/debug/app-debug.apk
TEST_APK=android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
RUNNER=$PKG.test/androidx.test.runner.AndroidJUnitRunner
mkdir -p out/screens

prepare() {
  adb install -r -g "$APK" >/dev/null
  adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS 2>/dev/null
  adb shell cmd role add-role-holder android.app.role.CALL_SCREENING $PKG 0 || adb shell cmd role add-role-holder android.app.role.CALL_SCREENING $PKG
  adb shell cmd role get-role-holders android.app.role.CALL_SCREENING
}

collect() {
  for f in $(adb shell run-as $PKG ls files/screens 2>/dev/null | tr -d '\r'); do
    adb exec-out run-as $PKG cat "files/screens/$f" > "out/screens/$f"
  done
}

adb install -r "$TEST_APK" >/dev/null
adb logcat -c

prepare
adb shell am instrument -w -e class "$PKG.ScreenshotTour#onboarding" $RUNNER | tee out/tour-onboarding.txt
collect

adb shell pm clear $PKG >/dev/null
prepare
adb shell am instrument -w -e class "$PKG.ScreenshotTour#mainApp" $RUNNER | tee out/tour-main.txt
collect

adb logcat -d -v time '*:E' | grep -v -E 'chatty|GoogleApiManager|Finsky' | tail -400 > out/logcat-errors.txt

# The minified release APK (what the download page serves) must sign in without crashing.
adb uninstall $PKG.test >/dev/null 2>&1
adb uninstall $PKG >/dev/null 2>&1
adb install -r -g android/app/build/outputs/apk/release/app-release.apk >/dev/null
if python3 .github/scripts/release_smoke.py > out/release-smoke.txt 2>&1; then cat out/release-smoke.txt; else cat out/release-smoke.txt; touch out/RELEASE-SMOKE-FAILED; fi
ls -la out/screens
exit 0
