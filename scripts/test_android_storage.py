"""Build a separate signed storage-test APK and run it on a named emulator only.

Run after android/Build.ps1 with the owner's signing environment configured.
No physical Android device is accepted and the test APK is never a release.
"""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(os.environ.get("PIT_ANDROID_TOOLS", str(ROOT / "android-tools")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", required=True)
    args = parser.parse_args()
    if not args.serial.startswith("emulator-") or not args.serial[9:].isdigit():
        raise RuntimeError("Storage tests accept only a dedicated emulator serial.")
    sdk = TOOLS / "sdk"
    adb = sdk / "platform-tools/adb.exe"
    command = [str(adb), "-s", args.serial]
    if subprocess.check_output(command + ["shell", "getprop", "ro.kernel.qemu"], text=True).strip() != "1":
        raise RuntimeError("Refusing to install test APK on a physical device.")
    if "PIT_SIGNING_PASSWORD" not in os.environ:
        raise RuntimeError("Owner wrapper must supply signing password through environment.")
    signing = Path(os.environ.get("PIT_ANDROID_SIGNING", str(ROOT / "android-signing")))
    # Test the current production source, never a previously installed APK/class cache.
    subprocess.run([sys.executable, str(ROOT / "scripts/build_android.py")], check=True)
    version = ET.parse(ROOT / "android/app/src/main/AndroidManifest.xml").getroot().get(
        "{http://schemas.android.com/apk/res/android}versionName")
    subprocess.run(command + ["install", "-r", str(ROOT / "releases/android" / f"TwizyPitPro-{version}.apk")], check=True)
    jdk = next((TOOLS / "jdk").glob("*/bin"))
    bt = sdk / "build-tools/35.0.0"
    android = sdk / "platforms/android-35/android.jar"
    build = ROOT / "android/build/storage-tests"
    build.mkdir(parents=True, exist_ok=True)
    classes, dex = build / "classes", build / "dex"
    classes.mkdir(exist_ok=True)
    dex.mkdir(exist_ok=True)
    manifest = build / "AndroidManifest.xml"
    manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="be.peter.twizypitpro.storageqa">
<uses-sdk android:minSdkVersion="30" android:targetSdkVersion="35"/>
<application android:label="Twizy Storage QA" android:debuggable="false"/>
<instrumentation android:name="be.peter.twizypitpro.VehicleStoreInstrumentation" android:targetPackage="be.peter.twizypitpro"/>
</manifest>''', encoding="utf-8")
    def run(values):
        subprocess.run(list(map(str, values)), check=True)
    run([jdk / "javac.exe", "-encoding", "UTF-8", "-source", "11", "-target", "11", "-cp",
         str(android) + os.pathsep + str(ROOT / "android/build/classes"), "-d", classes,
         ROOT / "android/tests/VehicleStoreInstrumentation.java"])
    jar = build / "tests.jar"
    run([jdk / "jar.exe", "--create", "--file", jar, "-C", classes, "."])
    run([jdk / "java.exe", "-cp", bt / "lib/d8.jar", "com.android.tools.r8.D8", "--release", "--min-api", "30",
         "--lib", android, "--classpath", ROOT / "android/build/classes.jar", "--output", dex, jar])
    resources = build / "resources.apk"
    run([bt / "aapt2.exe", "link", "-o", resources, "-I", android, "--manifest", manifest])
    import zipfile
    with zipfile.ZipFile(resources, "a", zipfile.ZIP_DEFLATED) as archive:
        for file in dex.glob("*.dex"):
            archive.write(file, file.name)
    aligned, apk = build / "aligned.apk", build / "Storage-QA-DO-NOT-DISTRIBUTE.apk"
    run([bt / "zipalign.exe", "-f", "4", resources, aligned])
    run([jdk / "java.exe", "-jar", bt / "lib/apksigner.jar", "sign", "--ks", signing / "owner-release.p12",
         "--ks-key-alias", "twizypit-owner", "--ks-pass", "env:PIT_SIGNING_PASSWORD", "--key-pass", "env:PIT_SIGNING_PASSWORD",
         "--v4-signing-enabled", "false", "--out", apk, aligned])
    run(command + ["install", "-r", str(apk)])
    output = subprocess.check_output(command + ["shell", "am", "instrument", "-w",
               "be.peter.twizypitpro.storageqa/be.peter.twizypitpro.VehicleStoreInstrumentation"], text=True)
    (build / "results.txt").write_text(output, encoding="utf-8")
    print(output)
    if "ANDROID STORAGE: 5 tests passed" not in output or "ANDROID STORAGE FAILURE" in output:
        raise RuntimeError("Android storage instrumentation failed.")


if __name__ == "__main__":
    main()
