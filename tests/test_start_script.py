import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell launcher")
class StartScriptTests(unittest.TestCase):
    def launch(self, local_only, existing=None, missing_lan=False):
        with tempfile.TemporaryDirectory(prefix="twizy-start-") as directory:
            root = Path(directory)
            shutil.copy2(ROOT / "Start.ps1", root / "Start.ps1")
            python = root / ".venv/Scripts/python.exe"
            python.parent.mkdir(parents=True)
            python.touch()  # Never executed: process and HTTP calls are mocked.
            harness = root / "check.ps1"
            harness.write_text('''
param([bool]$LocalOnly, [string]$Existing, [bool]$MissingLan)
$global:pitTestRequests = 0
$global:pitTestLaunches = @()
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    $global:pitTestRequests++
    if ($Existing -eq 'none' -and $global:pitTestRequests -eq 1) { throw 'Not running' }
    if ($MissingLan) { return [pscustomobject]@{version='0.4.1-preview'} }
    $lan = if ($Existing -eq 'none') { -not $LocalOnly } else { $Existing -eq 'lan' }
    return [pscustomobject]@{version='0.4.1-preview';lan=$lan}
}
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle, $RedirectStandardOutput, $RedirectStandardError)
    $global:pitTestLaunches += [pscustomobject]@{arguments=@($ArgumentList);style=$WindowStyle}
}
function Start-Sleep { param($Milliseconds) }
$failure = $null
try { & (Join-Path $PSScriptRoot 'Start.ps1') -LocalOnly:$LocalOnly -NoBrowser }
catch { $failure = $_.Exception.Message }
@{error=$failure;launches=@($global:pitTestLaunches);data=(Test-Path (Join-Path $PSScriptRoot 'data'))} | ConvertTo-Json -Compress -Depth 5
''', encoding="utf-8")
            quoted = "'" + str(harness).replace("'", "''") + "'"
            command = f"& {quoted} -LocalOnly:${str(local_only).lower()} -Existing '{existing or 'none'}' -MissingLan:${str(missing_lan).lower()}"
            result = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                                    capture_output=True, text=True, check=True, timeout=20)
            return json.loads(result.stdout)

    def test_local_only_refuses_existing_lan_server_without_stopping_it(self):
        result = self.launch(True, "lan")
        self.assertIn("gevraagde modus", result["error"])
        self.assertEqual(result["launches"], [])

    def test_lan_request_refuses_existing_local_server(self):
        result = self.launch(False, "local")
        self.assertIn("gevraagde modus", result["error"])
        self.assertEqual(result["launches"], [])

    def test_matching_server_is_reused_in_both_modes(self):
        for local in (True, False):
            with self.subTest(local=local):
                result = self.launch(local, "local" if local else "lan")
                self.assertIsNone(result["error"])
                self.assertEqual(result["launches"], [])

    def test_missing_mode_cannot_silently_satisfy_local_only(self):
        result = self.launch(True, "local", missing_lan=True)
        self.assertIn("gevraagde modus", result["error"])
        self.assertEqual(result["launches"], [])

    def test_new_server_uses_requested_mode_and_hidden_window(self):
        for local in (True, False):
            with self.subTest(local=local):
                result = self.launch(local)
                self.assertIsNone(result["error"])
                self.assertTrue(result["data"])
                self.assertEqual(len(result["launches"]), 1)
                self.assertEqual("--lan" in result["launches"][0]["arguments"], not local)
                self.assertEqual(result["launches"][0]["style"], "Hidden")
