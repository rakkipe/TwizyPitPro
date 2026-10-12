"""Compile current Android core sources and run isolated JVM tests.

Android/USB stubs reject platform access. These checks do not build an APK
or validate its UI, Keystore or USB hardware.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(os.environ.get("PIT_ANDROID_TOOLS", str(ROOT / "android-tools")))
sys.path.insert(0, str(ROOT))
from pit.catalog import defaults
from pit.tuning import targets

CORE_SOURCES = ("Model", "Tuning", "CanReader", "CanTelemetry", "LaptopLink", "VehicleWriter", "VehicleControl")


def java_tools(tools):
    suffix = ".exe" if os.name == "nt" else ""
    for bin_dir in sorted((tools / "jdk").glob("*/bin")):
        compiler, runtime = bin_dir / ("javac"+suffix), bin_dir / ("java"+suffix)
        if compiler.is_file() and runtime.is_file():
            return str(compiler), str(runtime)
    compiler, runtime = shutil.which("javac"), shutil.which("java")
    if not compiler or not runtime:
        raise RuntimeError("Installeer een JDK 11 of nieuwer of voer scripts/setup_android.py uit.")
    return compiler, runtime


def json_dependency(tools):
    path = tools / "json-20250517.jar"
    if not path.is_file():
        tools.mkdir(parents=True, exist_ok=True)
        # Failed downloads cannot leave a truncated jar in the cache.
        with urllib.request.urlopen("https://repo.maven.apache.org/maven2/org/json/json/20250517/json-20250517.jar", timeout=30) as response:
            data = response.read()
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
    return path


def test_vectors():
    vectors = []
    for car in ("80", "45"):
        for change in ({}, {"drive": 70, "neutral": 15, "brake": 20, "ramp_accel": 15, "smooth": 85},
                       {"speed": 90, "warn": 100, "torque": 130, "current": 123, "power_low": 139, "power_high": 130},
                       {"power_low": 139, "power_high": 10}, {"speed": 6, "warn": 10, "torque": 10},
                       {"brakelight_on": 60, "brakelight_off": 40}, {"ramp_start": 250, "rampl_decel": 0}):
            values = {**defaults(car), **change}
            rows = targets(values, car, 0x842c)
            vectors.append(dict(model=car, values=values, flags=0x842c,
                                expected=[{k: r[k] for k in ("address", "width", "signed", "raw")} for r in rows]))
    return vectors


def run_core_tests(root, jsonjar, compiler, runtime):
    build = root / "android" / "build"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="core-tests-", dir=build) as directory:
        fresh = Path(directory)
        classes = fresh / "classes"
        classes.mkdir()
        vector_path = fresh / "cross-language-vectors.json"
        vector_path.write_text(json.dumps(test_vectors()), encoding="utf-8")
        source = root / "android/app/src/main/java/be/peter/twizypitpro"
        tests = root / "android/tests"
        files = [source / (name + ".java") for name in CORE_SOURCES]
        files += [tests / "CoreTests.java", tests / "TuningTests.java", tests / "VehicleWriteTests.java"]
        files += sorted((tests / "stubs").rglob("*.java"))
        # Previous APK and test classes are never on the classpath.
        subprocess.run([compiler, "--release", "11", "-encoding", "UTF-8", "-cp", str(jsonjar),
                        "-d", str(classes), *map(str, files)], check=True)
        cp = os.pathsep.join((str(classes), str(jsonjar)))
        for name in ("CoreTests", "TuningTests", "VehicleWriteTests"):
            subprocess.run([runtime, "-cp", cp, "be.peter.twizypitpro." + name,
                            str(root / "android/app/src/main/assets/catalog.json"), str(vector_path)], check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Android-kern- en schrijfchecks op huidige broncode; JVM-stubs, geen APK/USB/UI-test.")
    parser.add_argument("--tools", type=Path, default=TOOLS, help="Cache voor JDK en org.json; standaard PIT_ANDROID_TOOLS of android-tools")
    args = parser.parse_args(argv)
    compiler, runtime = java_tools(args.tools)
    print("Android-kernchecks: verse JVM-compilatie met Android/USB-stubs; geen APK- of hardwarevalidatie.", flush=True)
    run_core_tests(ROOT, json_dependency(args.tools), compiler, runtime)


if __name__ == "__main__":
    main()
