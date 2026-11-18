"""Smoke-test the minified release APK on the emulator: launch it and sign in through the UI.

Code shrinking (R8) can strip classes the app needs at runtime, such as JSON serializers. This
walks welcome -> phone -> code -> profile against the local test server, which exercises the
network and JSON code, and fails if the app crashes or the profile screen never appears.
"""

import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PKG = "ai.pickup.app"


def adb(*args: str) -> str:
    return subprocess.run(["adb", *args], capture_output=True, text=True, errors="replace").stdout


def screen() -> ET.Element | None:
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    try:
        return ET.fromstring(adb("shell", "cat", "/sdcard/ui.xml"))
    except ET.ParseError:
        return None


def find(text: str) -> tuple[int, int] | None:
    root = screen()
    if root is None:
        return None
    for node in root.iter("node"):
        if text in (node.get("text") or "") or text in (node.get("content-desc") or ""):
            x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds", "")))
            return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def wait_for(text: str, timeout: int = 40) -> tuple[int, int]:
    end = time.time() + timeout
    while time.time() < end:
        if crashed():
            fail(f"crashed while waiting for '{text}'")
        spot = find(text)
        if spot:
            return spot
        time.sleep(1.5)
    fail(f"'{text}' never appeared")
    raise SystemExit(1)


def tap(text: str) -> None:
    x, y = wait_for(text)
    adb("shell", "input", "tap", str(x), str(y))


def crashed() -> bool:
    return "FATAL EXCEPTION" in adb("logcat", "-d", "-s", "AndroidRuntime:E")


def fail(why: str) -> None:
    with open("out/release-smoke.png", "wb") as fh:
        fh.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True).stdout)
    print("RELEASE SMOKE FAILED:", why)
    root = screen()
    if root is not None:
        texts = [t for node in root.iter("node") for t in (node.get("text"), node.get("content-desc")) if t]
        print("On screen:", " | ".join(texts)[:2000])
    print(adb("logcat", "-d", "-s", "AndroidRuntime:E", "PickupApi:*", "okhttp.OkHttpClient:*")[-4000:])
    try:
        with open("server.log") as fh:
            print("Server log (last lines):\n" + "".join(fh.readlines()[-30:]))
    except OSError:
        pass
    sys.exit(1)


def main() -> None:
    adb("logcat", "-c")
    adb("shell", "monkey", "-p", PKG, "-c", "android.intent.category.LAUNCHER", "1")
    tap("Get started")
    tap("98765 43210")
    adb("shell", "input", "text", "9800000003")
    tap("Send code")
    wait_for("Enter the code")
    tap("······")
    adb("shell", "input", "text", "123456")
    wait_for("Make it yours")
    with open("out/release-smoke.png", "wb") as fh:
        fh.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True).stdout)
    print("Release APK smoke test passed: signed in and reached the profile screen.")


if __name__ == "__main__":
    main()
