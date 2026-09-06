import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from pit.canopen import BusError, ElmLink, M5Link
from pit.catalog import defaults
from pit.tuning import targets
from pit.service import PitService
from pit.vehicle_write import VehicleWriter, VLinkerControl
from test_m5_compatibility import BridgeSerial


class BenchElm(ElmLink):
    """Byte-level fake of ELM raw CAN and a controller, no serial port opened."""
    def __init__(self, model="80", software="0712.0002"):
        super().__init__("BENCH-ONLY")
        self.bridge = BridgeSerial(0x0712302D if model == "80" else 0x0712301B, software)
        self.objects = self.bridge.objects
        for row in targets(defaults(model), model, 0x20c):
            self.objects[row["index"], row["sub"]] = row["raw"].to_bytes(row["width"], "little", signed=row["signed"])
        self.objects.update({(0x5000, 1): b"\0", (0x5000, 3): b"\0\0", (0x5110, 0): b"\x05", (0x606c, 0): bytes(4)})
        self.header = 0x601
        self.sent = []
        self.downloads = []
        self.guard_fault = None
        self.bad_ack = None
        self.bad_readback = None
        self.fail_after_writes = None
        self.journal = None

    def command(self, command, timeout=1.5):
        self.sent.append(command)
        if command == "ATRV":
            return "11.0V\r>" if self.guard_fault == "voltage" else "13.2V\r>"
        if command.startswith("ATSH"):
            self.header = int(command[4:], 16)
            return "OK\r>"
        if command.startswith("AT"):
            return "OK\r>"
        data = bytes.fromhex(command)
        if self.header == 0:
            assert data in (b"\x80\x01", b"\x01\x01")
            self.objects[0x5110, 0] = b"\x7f" if data[0] == 0x80 else b"\x05"
            return "NO DATA\r>"
        assert self.header == 0x601 and len(data) == 8
        key = (int.from_bytes(data[1:3], "little"), data[3])
        if data[0] in (0x23, 0x2b, 0x2f):
            width = {0x23: 4, 0x2b: 2, 0x2f: 1}[data[0]]
            if self.journal:
                assert self.journal.exists(), "Write without durable intent"
            value = data[4:4+width]
            self.downloads.append((key, value))
            if key == (0x5000, 2):
                assert width == 2 and value in (b"\xdfK", b"\0\0")
                self.objects[0x5000, 1] = b"\x04" if value != b"\0\0" else b"\0"
            elif key == (0x4641, 1):
                assert width == 1 and value == b"\x01"
            else:
                assert key in self.objects and len(self.objects[key]) == width
                self.objects[key] = value
            if key == self.bad_ack:
                self.bad_ack = None
                return "NO DATA\r>"  # the value changed, but acknowledgement was lost
            return "581 60" + data[1:4].hex() + "00000000\r>"
        self.bridge.write(b"READ " + command.encode() + b"\n")
        reply = self.bridge.readline().decode().strip().removeprefix("RX ")
        if key == self.bad_readback and self.downloads and self.downloads[-1][0] == key:
            self.bad_readback = None
            return "581 4B" + data[1:4].hex() + "01000000\r>"
        return reply + "\r>"

    def safety_capture(self):
        at = time.monotonic()
        frames = [(0x597, bytes.fromhex("0010000000000000"), at),
                  (0x599, bytes(8), at), (0x59b, bytes.fromhex("0001000000000000"), at)] * 2
        if self.guard_fault == "missing":
            return frames[:2]
        if self.guard_fault == "stale":
            return [(i, data, at-10) for i, data, _ in frames]
        if self.guard_fault == "emcy":
            return frames + [(0x81, bytes.fromhex("0010000000000000"), at)]
        if self.guard_fault == "moving" or self.fail_after_writes is not None and len(self.downloads) >= self.fail_after_writes:
            return [(i, bytes.fromhex("0000000000000001") if i == 0x599 else data, at) for i, data, _ in frames]
        return frames

    def capture(self):
        return [(i, data) for i, data, _ in self.safety_capture()]


class VehicleWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.link = BenchElm()
        self.control = VLinkerControl(self.link)
        self.writer = VehicleWriter(self.temp.name)
        self.link.journal = self.writer.path
        self.values = {**defaults(), "drive": 70}
        self.pause = patch("pit.vehicle_write.time.sleep")
        self.pause.start()
        self.addCleanup(self.pause.stop)

    def prepare(self, values=None):
        return self.writer.prepare(self.control, values or self.values, stock_drivetrain=True, faults_resolved=True)

    def apply(self, plan):
        return self.writer.apply(self.control, plan["id"], plan["review_hash"])

    def finish_cycle(self):
        self.writer.observe_contact_off([(0x597, bytes(8))])
        return self.writer.verify_cycle(self.control, self.writer.pending["id"])

    def test_prepare_is_read_only_and_binds_all_75_original_values(self):
        plan = self.prepare()
        self.assertEqual(len(plan["rows"]), 75)
        self.assertEqual(len(plan["changes"]), 1)
        self.assertEqual(plan["changes"][0]["before"], 1000)
        self.assertEqual(self.link.downloads, [])
        self.assertFalse(self.writer.path.exists())

    def test_full_profiles_use_typed_writes_commit_and_cycle_for_45_and_80(self):
        for model in ("45", "80"):
            for software in ("0712.0001", "0712.0002"):
                with self.subTest(model=model, software=software), tempfile.TemporaryDirectory() as directory:
                    link = BenchElm(model, software)
                    control = VLinkerControl(link)
                    writer = VehicleWriter(directory)
                    link.journal = writer.path
                    values = {**defaults(model), "speed": 90, "warn": 100, "torque": 120, "current": 120, "power_low": 120,
                              "power_high": 115, "D_speed1": 34, "D_level2": 80, "neutral": 20, "smooth": 80}
                    plan = writer.prepare(control, values, stock_drivetrain=True, faults_resolved=True)
                    result = writer.apply(control, plan["id"], plan["review_hash"])
                    self.assertEqual(result["phase"], "awaiting-contact-cycle")
                    self.assertEqual(control.state(), 5)
                    self.assertEqual(control.level(), 0)
                    self.assertIn(((0x4641, 1), b"\x01"), link.downloads)
                    for row in plan["rows"]:
                        self.assertEqual(control.read(row), row["raw"])
                    writer.observe_contact_off([(0x597, bytes(8))])
                    self.assertEqual(writer.verify_cycle(control, plan["id"])["phase"], "verified-after-contact-cycle")
                    self.assertIsNone(writer.pending)

    def test_motor_and_brake_hardware_confirmation_required(self):
        with self.assertRaises(ValueError):
            self.writer.prepare(self.control, self.values)
        with self.assertRaises(ValueError):
            self.writer.prepare(self.control, {**self.values, "brakelight_on": 60, "brakelight_off": 40}, stock_drivetrain=True, faults_resolved=True)
        self.assertEqual(self.link.downloads, [])

    def test_unresolved_serv_blocks_plan(self):
        with self.assertRaisesRegex(ValueError, "SERV"):
            self.writer.prepare(self.control, self.values, stock_drivetrain=True)
        self.assertEqual(self.link.downloads, [])

    def test_unknown_locked_revision_and_missing_identity_block_before_writes(self):
        for key, value in (((0x100A, 0), b"0712.0003"), ((0x1018, 3), bytes(4)), ((0x1018, 4), bytes(4)), ((0x1018, 1), (99).to_bytes(4, "little"))):
            with self.subTest(key=key):
                old = self.link.objects[key]
                self.link.objects[key] = value
                with self.assertRaises(ValueError): self.prepare()
                self.link.objects[key] = old
        self.assertEqual(self.link.downloads, [])

    def test_guards_reject_missing_stale_moving_emcy_and_bad_voltage(self):
        for fault in ("missing", "stale", "moving", "emcy", "voltage"):
            with self.subTest(fault=fault):
                self.link.guard_fault = fault
                with self.assertRaises(BusError): self.prepare()
        self.assertEqual(self.link.downloads, [])

    def test_error_register_and_motor_speed_block_writes(self):
        for key, value in (((0x1001, 0), b"\x01"), ((0x606c, 0), (1).to_bytes(4, "little"))):
            old = self.link.objects[key]
            self.link.objects[key] = value
            with self.assertRaises(BusError): self.prepare()
            self.link.objects[key] = old
        self.assertEqual(self.link.downloads, [])

    def test_changed_baseline_rejects_without_login(self):
        plan = self.prepare()
        self.link.objects[0x2920, 1] = (800).to_bytes(2, "little")
        with self.assertRaises(ValueError): self.apply(plan)
        self.assertEqual(self.link.downloads, [])
        self.assertFalse(self.writer.path.exists())

    def test_changed_identity_rejects_before_login(self):
        plan = self.prepare()
        self.link.objects[0x1018, 4] = (456).to_bytes(4, "little")
        with self.assertRaises(ValueError): self.apply(plan)
        self.assertEqual(self.link.downloads, [])

    def test_approval_hash_is_required_and_consumed_once(self):
        plan = self.prepare()
        with self.assertRaises(ValueError):
            self.writer.apply(self.control, plan["id"], "wrong-hash")
        with self.assertRaises(ValueError): self.apply(plan)
        self.assertEqual(self.link.downloads, [])

    def test_expired_plan_is_not_applied(self):
        plan = self.prepare()
        self.writer.plan["deadline"] = self.writer.clock()-1
        with self.assertRaises(ValueError): self.apply(plan)
        self.assertEqual(self.link.downloads, [])

    def test_client_cannot_mutate_the_frozen_plan(self):
        plan = self.prepare()
        plan["rows"][0]["raw"] = 9999
        plan["changes"][0]["raw"] = 9999
        self.apply(plan)
        self.assertEqual(self.link.objects[0x2920, 1], (700).to_bytes(2, "little"))

    def test_missing_ack_stops_without_retry_and_restores_after_restart(self):
        plan = self.prepare()
        self.link.bad_ack = (0x2920, 1)
        with self.assertRaises(BusError): self.apply(plan)
        self.assertEqual(self.writer.pending["phase"], "recovery-required")
        self.assertEqual(len([x for x in self.link.downloads if x[0] == (0x2920, 1)]), 1)
        self.assertEqual(self.control.state(), 127)
        self.writer = VehicleWriter(self.temp.name)
        self.assertTrue(self.writer.pending["interrupted"])
        result = self.writer.restore(self.control, plan["id"])
        self.assertTrue(result["restored"])
        self.assertEqual(self.link.objects[0x2920, 1], (1000).to_bytes(2, "little"))
        self.finish_cycle()

    def test_readback_mismatch_stops_without_automatic_rollback(self):
        plan = self.prepare()
        self.link.bad_readback = (0x2920, 1)
        with self.assertRaises(BusError): self.apply(plan)
        self.assertEqual(self.writer.pending["phase"], "recovery-required")
        self.assertEqual(self.control.state(), 127)
        self.assertFalse(self.writer.pending["attempts"][-1]["verified"])

    def test_mid_transaction_safety_change_stops_next_write(self):
        plan = self.prepare({**self.values, "neutral": 20})
        self.link.fail_after_writes = 3  # login writes + first tuning register
        with self.assertRaises(BusError): self.apply(plan)
        tuning = [x for x in self.link.downloads if x[0][0] != 0x5000]
        self.assertEqual(len(tuning), 1)
        self.assertEqual(self.writer.pending["phase"], "recovery-required")

    def test_pending_transaction_blocks_new_plan(self):
        self.apply(self.prepare())
        with self.assertRaises(ValueError): self.prepare()

    def test_contact_cycle_requires_positive_off_evidence(self):
        plan = self.prepare()
        self.apply(plan)
        for samples in ([], [(0x597, bytes.fromhex("0010000000000000"))]):
            self.writer.observe_contact_off(samples)
            with self.assertRaises(ValueError): self.writer.verify_cycle(self.control, plan["id"])
        self.assertEqual(self.finish_cycle()["phase"], "verified-after-contact-cycle")

    def test_modified_backup_blocks_restart_recovery(self):
        plan = self.prepare()
        self.apply(plan)
        backup = Path(self.temp.name)/"vehicle-backups"/(plan["id"]+".json")
        value = json.loads(backup.read_text(encoding="utf-8"))
        value["rows"][0]["before"] += 1
        backup.write_text(json.dumps(value), encoding="utf-8")
        restarted = VehicleWriter(self.temp.name)
        self.assertEqual(restarted.pending["phase"], "corrupt")
        with self.assertRaises(ValueError): restarted.restore(self.control, plan["id"])

    def test_restore_rejects_unexpected_third_party_value(self):
        plan = self.prepare()
        self.apply(plan)
        self.link.objects[0x2920, 1] = (300).to_bytes(2, "little")
        before = len(self.link.downloads)
        with self.assertRaises(ValueError): self.writer.restore(self.control, plan["id"])
        self.assertEqual(len(self.link.downloads), before)

    def test_expired_guard_prevents_protocol_transmission(self):
        before = list(self.link.sent)
        with self.assertRaises(BusError): self.control.download(0x2920, 1, 700)
        with self.assertRaises(BusError): self.control.mode(True)
        self.assertEqual(self.link.sent, before)

    def test_m5_cannot_be_used_for_vlinker_writes(self):
        with self.assertRaises(ValueError): VLinkerControl(M5Link("TEST"))

    def test_failed_journal_save_prevents_first_write(self):
        plan = self.prepare()
        with patch("pit.vehicle_write.save_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError): self.apply(plan)
        self.assertEqual(self.link.downloads, [])

    def test_service_routes_and_contact_off_monitor_work_together(self):
        service = PitService(self.temp.name)
        service.mode = "live"
        service.link = self.link
        service.identity = self.control.identity()
        plan = service.vehicle_action("prepare", values=self.values, stock_drivetrain=True, faults_resolved=True)
        self.assertFalse(service.busy)
        result = service.vehicle_action("apply", plan_id=plan["id"], review_hash=plan["review_hash"])
        self.assertEqual(result["phase"], "awaiting-contact-cycle")
        with patch.object(self.link, "safety_capture", return_value=[(0x597, bytes(8), time.monotonic())]):
            service.live_sample()
        self.assertTrue(service.connected)
        self.assertTrue(service.state()["vehicle_transaction"]["cycle_off_seen"])
        result = service.vehicle_action("verify-cycle", transaction_id=plan["id"])
        self.assertEqual(result["phase"], "verified-after-contact-cycle")
        self.assertIsNone(service.state()["vehicle_transaction"])

    def test_controller_swap_during_write_is_detected_by_next_guard(self):
        plan = self.prepare({**self.values, "neutral": 20})
        original = self.control.write
        def swapped(row):
            original(row)
            self.link.objects[0x1018, 4] = (456).to_bytes(4, "little")
        with patch.object(self.control, "write", side_effect=swapped):
            with self.assertRaisesRegex(BusError, "Controller gewisseld"):
                self.apply(plan)
        self.assertEqual(len([x for x in self.link.downloads if x[0][0] != 0x5000]), 1)

    def test_failed_map_commit_is_recommitted_when_original_snapshot_restored(self):
        plan = self.prepare({**self.values, "speed": 100, "warn": 110})
        self.link.bad_ack = (0x4641, 1)
        with self.assertRaises(BusError): self.apply(plan)
        self.assertEqual(self.writer.pending["phase"], "recovery-required")
        self.writer.restore(self.control, plan["id"])
        self.assertEqual(len([x for x in self.link.downloads if x[0] == (0x4641, 1)]), 2)
        self.finish_cycle()


if __name__ == "__main__":
    unittest.main()
