import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pit.canopen import Abort, BusError
from pit.catalog import defaults
from pit.renault import ClusterService, read_cluster
from pit.service import PitService
from pit.telemetry import decode_frames
from pit.vehicle_write import VehicleWriter, VLinkerControl
from test_vehicle_write import BenchElm


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.link = BenchElm()
        self.link.protected_reads = True
        self.writer = VehicleWriter(self.temp.name)
        self.link.journal = self.writer.path
        self.control = VLinkerControl(self.link)

    def plan(self, **changes):
        return self.writer.prepare(self.control, {**defaults(), **changes},
                                   stock_drivetrain=True, faults_resolved=True)

    def test_locked_reads_snapshot_and_logout(self):
        with self.assertRaises(Abort):
            self.control.read({"index": 0x2920, "sub": 1, "width": 2})
        result = self.writer.snapshot(self.control)
        self.assertEqual(len(result["registers"]), 75)
        self.assertTrue(result["logged_out"])
        self.assertFalse(result["tuning_changed"])
        self.assertEqual(self.control.level(), 0)
        self.assertIsNone(self.writer.access)
        self.assertTrue(all(key[0] == 0x5000 for key, _ in self.link.downloads))
        self.assertNotIn("ATSH000", self.link.sent)
        self.assertEqual(len(list(Path(self.temp.name).glob("vehicle-snapshots/*.json"))), 1)

    def test_protected_reads_complete_apply_and_cycle_for_all_supported_variants(self):
        for model in ("45", "80"):
            for software in ("0712.0001", "0712.0002"):
                with self.subTest(model=model, software=software), tempfile.TemporaryDirectory() as d:
                    link = BenchElm(model, software)
                    link.protected_reads = True
                    control, writer = VLinkerControl(link), VehicleWriter(d)
                    link.journal = writer.path
                    plan = writer.prepare(control, {**defaults(model), "drive": 70}, stock_drivetrain=True, faults_resolved=True)
                    writer.apply(control, plan["id"], plan["review_hash"])
                    self.assertEqual(link.objects[0x2920, 1], (700).to_bytes(2, "little"))
                    self.assertEqual(control.level(), 0)
                    writer.observe_contact_off([(0x597, bytes(8))])
                    writer.verify_cycle(control, plan["id"])
                    self.assertIsNone(writer.pending)
                    self.assertIsNone(writer.access)
                    self.assertEqual(control.level(), 0)

    def test_missing_login_ack_is_not_retried_or_automatically_logged_out(self):
        self.link.bad_ack = (0x5000, 2)
        with self.assertRaises(BusError):
            self.writer.snapshot(self.control)
        self.assertEqual(len(self.link.downloads), 2)
        self.assertEqual(self.writer.access["phase"], "recovery-required")
        self.writer = VehicleWriter(self.temp.name)
        with self.assertRaises(ValueError): self.writer.snapshot(self.control)
        self.writer.close_access(self.control)
        self.assertEqual(self.control.level(), 0)
        self.assertIsNone(self.writer.access)

    def test_read_failure_closes_known_access_without_tuning(self):
        with patch.object(self.control, "read", side_effect=BusError("read failure")):
            with self.assertRaisesRegex(BusError, "read failure"):
                self.writer.snapshot(self.control)
        self.assertEqual(self.control.level(), 0)
        self.assertIsNone(self.writer.access)
        self.assertFalse(self.writer.path.exists())

    def test_journal_must_be_saved_before_login(self):
        with patch("pit.vehicle_write.save_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError): self.writer.snapshot(self.control)
        self.assertEqual(self.link.downloads, [])

    def test_access_commands_are_adjacent_with_fresh_deadline(self):
        self.writer.snapshot(self.control)
        for n, command in enumerate(self.link.sent):
            if command == "2B00500300000000":
                self.assertIn(self.link.sent[n+1], ("2B005002DF4B0000", "2B00500200000000"))

    def test_logout_error_nine_requires_readback_level_zero(self):
        self.link.objects[0x5310, 0] = (9).to_bytes(2, "little")
        command = self.link.command
        def response(request, timeout=1.5):
            result = command(request, timeout)
            if request == "2B00500200000000":
                return "581 8000500200000008\r>"
            return result
        with patch.object(self.link, "command", side_effect=response):
            self.assertTrue(self.writer.snapshot(self.control)["logged_out"])
        self.assertEqual(self.control.level(), 0)

    def test_logout_error_nine_does_not_hide_still_logged_in_state(self):
        self.link.objects[0x5310, 0] = (9).to_bytes(2, "little")
        command = self.link.command
        def response(request, timeout=1.5):
            result = command(request, timeout)
            if request == "2B00500200000000":
                self.link.objects[0x5000, 1] = b"\x04"
                return "581 8000500200000008\r>"
            return result
        with patch.object(self.link, "command", side_effect=response):
            with self.assertRaisesRegex(BusError, "Uitloggen niet bevestigd"):
                self.writer.snapshot(self.control)
        self.assertEqual(self.writer.access["phase"], "recovery-required")

    def test_existing_external_login_is_not_taken_over(self):
        self.link.objects[0x5000, 1] = b"\x04"
        with self.assertRaisesRegex(ValueError, "buiten deze app"):
            self.writer.snapshot(self.control)
        self.assertEqual(self.link.downloads, [])

    def test_protected_restore_after_interruption(self):
        plan = self.plan(drive=70)
        self.link.bad_ack = (0x2920, 1)
        with self.assertRaises(BusError): self.writer.apply(self.control, plan["id"], plan["review_hash"])
        writer = VehicleWriter(self.temp.name)
        review = writer.review_restore(self.control, plan["id"])
        self.assertEqual(len(review["changes"]), 1)
        self.assertEqual(self.control.level(), 0)
        writer.restore(self.control, plan["id"])
        self.assertEqual(self.link.objects[0x2920, 1], (1000).to_bytes(2, "little"))

    def test_selected_field_preserves_custom_registers(self):
        self.link.objects[0x6075, 0] = (520000).to_bytes(4, "little")
        self.link.objects[0x2920, 3] = (310).to_bytes(2, "little")
        plan = self.writer.prepare(self.control, {**defaults(), "drive": 70}, stock_drivetrain=True,
                                   faults_resolved=True, selected_keys=["drive"])
        self.assertEqual([row["address"] for row in plan["changes"]], ["2920:01"])
        self.writer.apply(self.control, plan["id"], plan["review_hash"])
        self.assertEqual(self.link.objects[0x6075, 0], (520000).to_bytes(4, "little"))
        self.assertEqual(self.link.objects[0x2920, 3], (310).to_bytes(2, "little"))

    def test_invalid_and_partial_power_selections_block_before_login(self):
        for keys in ([], ["speed"], ["not-a-setting"], "drive", ["brakelight_on"]):
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                self.writer.prepare(self.control, defaults(), stock_drivetrain=True,
                                    faults_resolved=True, selected_keys=keys)
        self.assertEqual(self.link.downloads, [])

    def test_fresh_neutral_20_is_accepted_and_unknown_or_drive_rejected(self):
        capture = self.link.safety_capture
        for byte in (0x20, 0x80, 0x08, 0xff, 0x28):
            def frames():
                return [(i, bytes([byte])+b[1:] if i == 0x59b else b, at) for i, b, at in capture()]
            with self.subTest(byte=byte), patch.object(self.link, "safety_capture", side_effect=frames):
                if byte == 0x20: self.control.guard()
                else:
                    with self.assertRaises(BusError): self.control.guard()

    def test_access_does_not_relax_configuration_brake_guard(self):
        capture = self.link.safety_capture
        def frames():
            return [(i, b[:1]+b"\0"+b[2:] if i == 0x59b else b, at) for i, b, at in capture()]
        with patch.object(self.link, "safety_capture", side_effect=frames):
            self.control.guard(access_only=True)
            with self.assertRaises(BusError): self.control.guard()

    def test_renault_active_fault_blocks_even_when_user_checkbox_is_true(self):
        service = PitService(self.temp.name)
        service.mode, service.link = "live", self.link
        with patch("pit.service.read_cluster", return_value={"entries": [{"ecu": 2, "code": 83, "present": True}]}):
            with self.assertRaisesRegex(BusError, "2/83"):
                service.vehicle_action("prepare", values=defaults(), stock_drivetrain=True, faults_resolved=True)
        self.assertEqual(self.link.downloads, [])

    def test_known_controller_diagnosis_uses_supported_active_fault_counter(self):
        self.link.protected_reads = False
        self.link.objects[0x5300, 1] = bytes(2)
        service = PitService(self.temp.name)
        service.mode, service.link = "live", self.link
        with patch("pit.service.read_cluster", return_value={"entries": []}):
            result = service.diagnose()
        self.assertTrue(result["complete"])
        self.assertIn("5300:01", [row["address"] for row in result["registers"]])
        self.assertNotIn("4003100000000000", self.link.sent)
        self.assertEqual(self.link.downloads, [])

    def test_pack_voltage_uses_tenths_and_known_neutral_code(self):
        result = decode_frames([(0x55f, bytes.fromhex("000000000022D22D")), (0x59b, bytes.fromhex("2001000000000000"))])
        self.assertEqual(result["voltage"], 55.7)
        self.assertEqual(result["gear"], "N")


class DiagnosticLink:
    def __init__(self, payload):
        self.payload, self.commands = payload, []
        self.bad_sequence = False

    def command(self, command, timeout=1.5):
        self.commands.append(command)
        if command.startswith("AT"): return "OK\r>"
        if command == "3000000000000000":
            return "\r".join("763 " + (bytes([0x20 | ((n+1) % 16)]) + self.payload[6+n*7:13+n*7]).ljust(8,b"\0").hex()
                               for n in range((len(self.payload)-6+6)//7)) + "\r>" if not self.bad_sequence else "763 2200000000000000\r>"
        data = self.payload
        if len(data) <= 7: return "763 " + (bytes([len(data)])+data).ljust(8,b"\0").hex()+"\r>"
        return "763 " + (bytes([0x10 | (len(data)>>8), len(data)&255])+data[:6]).hex()+"\r>"


class RenaultTests(unittest.TestCase):
    def test_long_store_with_sequence_wrap_and_present_flag(self):
        payload = b"\x61\x13" + bytes.fromhex("0253260b00000000000000") + bytes(99)
        link = DiagnosticLink(payload)
        result = ClusterService(link, []).read_store()
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["code"], 83)
        self.assertTrue(result["entries"][0]["present"])

    def test_writes_and_reset_are_not_exposed_by_reader(self):
        link = DiagnosticLink(b"\x54")
        client = ClusterService(link, [])
        for request in (b"\x14\xff\xff\xff", b"\x3b\xf2\x00", b"\x11\x01"):
            with self.assertRaises(BusError): client.request(request)
        self.assertEqual(link.commands, [])

    def test_negative_and_incomplete_responses_rejected(self):
        for payload in (b"\x7f\x21\x12", b"\x61\x13"+bytes(109), b"\x61\x80"):
            with self.subTest(payload=payload), self.assertRaises(BusError):
                ClusterService(DiagnosticLink(payload), []).read_store()

    def test_bad_sequence_rejected(self):
        link = DiagnosticLink(b"\x61\x13"+bytes(110))
        link.bad_sequence = True
        with self.assertRaises(BusError): ClusterService(link, []).read_store()

    def test_sdo_settings_restored_after_failed_read(self):
        link = DiagnosticLink(b"\x7f\x10\x12")
        with self.assertRaises(BusError): read_cluster(link)
        self.assertEqual(link.commands[-3:], ["ATSH601", "ATCRA581", "ATST32"])
