from pathlib import Path
import io
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import test_android

ROOT = Path(__file__).resolve().parents[1]
JSON_JAR = test_android.TOOLS / "json-20250517.jar"
try:
    JAVA_TOOLS = test_android.java_tools(test_android.TOOLS)
except RuntimeError:
    JAVA_TOOLS = None


class AndroidProcedureTests(unittest.TestCase):
    def test_failed_download_does_not_poison_dependency_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = Path(directory)
            response = io.BytesIO(b"jar bytes")
            response.read = lambda *args: (_ for _ in ()).throw(OSError("interrupted"))
            with patch.object(test_android.urllib.request, "urlopen", return_value=response):
                with self.assertRaises(OSError): test_android.json_dependency(tools)
            self.assertFalse((tools / "json-20250517.jar").exists())

    def test_import_does_not_launch_a_build_or_network_request(self):
        import importlib
        with patch.object(test_android.subprocess, "run") as process, patch.object(test_android.urllib.request, "urlopen") as network:
            importlib.reload(test_android)
        process.assert_not_called()
        network.assert_not_called()


@unittest.skipUnless(JSON_JAR.is_file() and JAVA_TOOLS, "JDK and cached org.json required for offline JVM integration tests")
class AndroidCompilationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="twizy-android-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "android/app/src/main", self.root / "android/app/src/main")
        shutil.copytree(ROOT / "android/tests", self.root / "android/tests")
        for directory in ("classes", "test-classes"):
            stale = self.root / "android/build" / directory / "be/peter/twizypitpro"
            stale.mkdir(parents=True)
            (stale / "Tuning.class").write_bytes(b"old APK build - must be ignored")
        self.compiler, self.runtime = JAVA_TOOLS

    def run_sources(self):
        run = subprocess.run
        with patch.object(test_android.subprocess, "run", side_effect=lambda *a, **k: run(*a, **k, capture_output=True)):
            test_android.run_core_tests(self.root, JSON_JAR, self.compiler, self.runtime)

    def test_clean_source_compilation_ignores_cached_apk_and_test_classes(self):
        self.run_sources()
        self.assertEqual(list((self.root / "android/build").glob("core-tests-*")), [])

    def test_current_source_regression_is_detected_despite_previous_build_artifacts(self):
        source = self.root / "android/app/src/main/java/be/peter/twizypitpro/Tuning.java"
        source.write_text(source.read_text(encoding="utf-8").replace("80,7250,900", "80,7000,900", 1), encoding="utf-8")
        with self.assertRaises(subprocess.CalledProcessError): self.run_sources()
