"""Exercise the real M5/SDO/service path against a simulated PitBridge 1.

These fixtures test protocol compatibility, not physical vehicle qualification.
"""
from collections import deque
import tempfile
import unittest
from unittest.mock import patch

from pit.canopen import BusError, M5Link, SDO
from pit.service import PitService


class BridgeSerial:
    def __init__(self, product=0x0712302D, software="0712.0002", capture=True):
        self.objects = {
            (0x1008, 0): b"SEVCON Gen4",
            (0x1009, 0): b"HW1",
            (0x100A, 0): software.encode("ascii"),
            (0x1018, 1): (30).to_bytes(4, "little"),
            (0x1018, 2): product.to_bytes(4, "little"),
            (0x1018, 3): {"0712.0001": 0x10019, "0712.0002": 0x10021}.get(software, 0x12345).to_bytes(4, "little"),
            (0x1018, 4): (123).to_bytes(4, "little"),
            (0x1001, 0): b"\0", (0x6041, 0): b"\0\0", (0x1003, 0): b"\0",
        }
        self.supports_capture = capture
        self.lines = deque()
        self.commands = []
        self.remaining = b""
        self.closed = False

    def reset_input_buffer(self):
        self.lines.clear()

    def write(self, command):
        self.commands.append(command)
        if command == b"HELLO\n":
            self.lines.append(b"PITBRIDGE 1 READONLY\n")
        elif command == b"CAPTURE\n":
            self.lines.extend([b"FRAME 599 0000000000000000\n", b"CAPTURE END\n"] if self.supports_capture else [b"ERR FORMAT\n"])
        else:
            if not command.startswith(b"READ "):
                raise AssertionError("Unexpected adapter command")
            request = bytes.fromhex(command[5:].decode("ascii"))
            if len(request) != 8 or request[0] not in (0x40, 0x60, 0x70):
                raise AssertionError("Non-upload CAN request")
            if request[0] == 0x40:
                index, sub = int.from_bytes(request[1:3], "little"), request[3]
                raw = self.objects.get((index, sub))
                if raw is None:
                    reply = b"\x80" + request[1:4] + bytes.fromhex("00000206")
                elif len(raw) <= 4:
                    reply = bytes([0x43 | (4-len(raw)) << 2]) + request[1:4] + raw.ljust(4, b"\0")
                else:
                    self.remaining = raw
                    reply = b"\x41" + request[1:4] + len(raw).to_bytes(4, "little")
            else:
                chunk, self.remaining = self.remaining[:7], self.remaining[7:]
                if not chunk:
                    raise AssertionError("Segment without initiated upload")
                flag = request[0] & 0x10
                if not self.remaining:
                    flag |= 1 | (7-len(chunk)) << 1
                reply = bytes([flag]) + chunk.ljust(7, b"\0")
            self.lines.append(b"RX 581 " + reply.hex().encode("ascii") + b"\n")
        return len(command)

    def readline(self):
        if not self.lines:
            raise AssertionError("Unexpected extra serial read")
        return self.lines.popleft()

    def close(self):
        self.closed = True


class M5CompatibilityTests(unittest.TestCase):
    def test_one_bridge_connects_and_diagnoses_both_models_across_versions(self):
        for product, model in ((0x0712301B, "45"), (0x0712302D, "80")):
            for software in ("0712.0001", "0712.0002", "0712.0003", "0712.9999", "9999.9999", "future-version"):
                with self.subTest(model=model, software=software), tempfile.TemporaryDirectory() as directory:
                    bridge = BridgeSerial(product, software)
                    service = PitService(directory)
                    with patch("serial.Serial", return_value=bridge), patch("pit.canopen.time.sleep"), patch.object(service, "ports", return_value=[{"port": "TEST"}]):
                        # Live identification must ignore client-side demo choices.
                        state = service.connect("live", port="TEST", adapter="m5", model="auto", software="not-a-demo-version")
                        self.assertTrue(state["connected"])
                        self.assertEqual(state["identity"]["software"], software)
                        self.assertEqual(state["compatibility"]["model"], model)
                        self.assertEqual(state["current"], {})
                        report = service.diagnose()
                        self.assertIn("1001:00", {r["address"] for r in report["registers"]})
                        known = software in ("0712.0001", "0712.0002")
                        self.assertEqual(report["inventory_count"], 75 if known else 0)
                        self.assertFalse(state["limits"]["live_write"])
                        self.assertEqual(bridge.commands[0], b"HELLO\n")
                        service.disconnect()
                        self.assertTrue(bridge.closed)

    def test_missing_version_keeps_partial_identity_without_guessing(self):
        bridge = BridgeSerial()
        del bridge.objects[(0x100A, 0)]
        link = M5Link("TEST")
        with patch("serial.Serial", return_value=bridge), patch("pit.canopen.time.sleep"):
            link.open()
            identity = SDO(link).identity()
            self.assertNotIn("software", identity)
            self.assertEqual(identity["product"], 0x0712302D)
            self.assertTrue(identity["errors"])
            link.close()

    def test_old_bridge_without_capture_still_reads_identity(self):
        bridge = BridgeSerial(capture=False)
        link = M5Link("TEST")
        with patch("serial.Serial", return_value=bridge), patch("pit.canopen.time.sleep"):
            link.open()
            self.assertEqual(link.capture(), [])
            self.assertEqual(link.capture(), [])
            self.assertEqual(bridge.commands.count(b"CAPTURE\n"), 1)
            self.assertEqual(SDO(link).identity()["software"], "0712.0002")
            link.close()

    def test_reconnect_redetects_optional_capture(self):
        old, new = BridgeSerial(capture=False), BridgeSerial(capture=True)
        link = M5Link("TEST")
        with patch("serial.Serial", side_effect=[old, new]), patch("pit.canopen.time.sleep"):
            link.open()
            self.assertEqual(link.capture(), [])
            link.close()
            link.open()
            self.assertEqual(link.capture(), [(0x599, bytes(8))])
            link.close()

    def test_upload_rejection_does_not_discard_the_bridge_connection(self):
        bridge = BridgeSerial()
        link = M5Link("TEST")
        with patch("serial.Serial", return_value=bridge), patch("pit.canopen.time.sleep"):
            link.open()
            with self.assertRaises(BusError):
                SDO(link).number(0x7777)
            self.assertEqual(SDO(link).number(0x1018, 2), 0x0712302D)
            self.assertFalse(bridge.closed)
            link.close()


if __name__ == "__main__":
    unittest.main()
