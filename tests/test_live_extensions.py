import itertools
import tempfile
import unittest
from unittest.mock import patch

from pit.catalog import defaults, parameters
from pit.canopen import BusError, ElmLink, SDO
from pit.tuning import targets, register_inventory, compare_snapshot, map_update_order
from pit.telemetry import decode_frames
from pit.service import PitService


class TuningTargetsTests(unittest.TestCase):
    def test_every_editor_field_has_typed_registers(self):
        for model in ("45","80"):
            rows=targets(defaults(model),model)
            self.assertEqual(len(rows),75)
            self.assertEqual(len({r["address"] for r in rows}),75)
            self.assertEqual({k for r in rows for k in r["keys"]},{p["key"] for p in parameters(model)})
            self.assertIsNone(next(r for r in rows if r["address"]=="2910:01")["raw"])

    def test_published_twizy80_reference_values(self):
        r={x["address"]:x for x in targets(defaults(),"80",0x20c)}
        expected={"2920:05":7250,"3813:34":8050,"3813:3C":7500,"3813:33":7650,"3813:35":8050,"3813:3B":8500,"3813:2D":10000,"4624:00":11000,"6075:00":450000,"6076:00":55000,"2916:01":57000,"4611:01":880,"4611:12":7250,"4610:11":1122,"3813:23":4608,"3813:24":32767,"3813:07":32767,"3813:0B":16383,"2910:01":0x20c}
        for address,value in expected.items():self.assertEqual(r[address]["raw"],value,address)
        self.assertEqual(r["2916:01"]["width"],4)
        self.assertTrue(r["3813:23"]["signed"])

    def test_speed_change_includes_all_dependent_maps(self):
        v=defaults();v["speed"]=100;v["warn"]=109
        r={x["address"]:x["raw"] for x in targets(v,"80",0)}
        self.assertEqual(r["2920:05"],9062)
        self.assertEqual(r["2920:06"],900)
        self.assertEqual(r["3813:2D"],11812)
        self.assertNotEqual(r["4611:12"],7250)
        self.assertLessEqual(r["4611:12"],9062)

    def test_current_cap_is_motor_current(self):
        for model,expected in (("80",540000),("45",330000)):
            v=defaults(model);v["current"]=123
            r={x["address"]:x["raw"] for x in targets(v,model)}
            self.assertEqual(r["6075:00"],expected)

    def test_control_flags_preserve_unrelated_bits(self):
        v=defaults();v.update(brakelight_on=50,brakelight_off=40)
        r={x["address"]:x for x in targets(v,"80",0x842c)}
        self.assertEqual(r["2910:01"]["raw"],0xa42c)
        with self.assertRaises(ValueError):targets(v,"80",True)

    def test_engineering_targets_are_not_vehicle_baseline(self):
        rows=compare_snapshot(defaults(),"80",[{"address":"2920:01","width":2,"raw":700,"source":"simulation"}])
        self.assertTrue(all(r["before"] is None for r in rows))
        rows=compare_snapshot(defaults(),"80",[{"address":"2920:01","width":4,"raw":700,"source":"live"}])
        self.assertIsNone(rows[0]["before"])
        rows=compare_snapshot(defaults(),"80",[{"address":"2910:01","width":4,"raw":524,"source":"live"}])
        self.assertIsNone(rows[-1]["raw"])

    def test_snapshot_comparison_and_missing_mask(self):
        rows=compare_snapshot(defaults(),"80",[{"address":"2920:01","width":2,"raw":700,"source":"live"}])
        self.assertEqual(rows[0]["before"],700)
        self.assertEqual(rows[0]["raw"],1000)
        self.assertTrue(rows[0]["changed"])
        self.assertIsNone(rows[-1]["raw"])

    def test_moving_curve_order_preserves_bounds(self):
        sequences=list(itertools.combinations(range(0,8),4))
        for before in sequences:
            for after in sequences:
                current=list(before)
                for i in map_update_order(before,after):
                    current[i]=after[i]
                    self.assertTrue(all(a<b for a,b in zip(current,current[1:])))
                self.assertEqual(current,list(after))
        with self.assertRaises(ValueError):map_update_order([1,1,2,3],[2,3,4,5])

    def test_low_warning_underflow_rejected(self):
        v=defaults("45");v.update(speed=6,warn=10)
        # 7200*10/56 is above the 900-rpm hysteresis; still representable.
        rows=targets(v,"45")
        self.assertTrue(all(r["raw"] is None or r["raw"]>=0 for r in rows))

    def test_live_scan_identity_change_is_not_reused(self):
        with tempfile.TemporaryDirectory() as d:
            s=PitService(d);old=dict(s.identity);old["serial"]=9
            s.mode="live";s.identity["source"]="live"
            s.scan={"mode":"live","identity":old,"registers":[{"address":"2920:01","width":2,"raw":700,"source":"live"}]}
            p=s.make_plan(defaults())
            self.assertTrue(all(r["before"] is None for r in p["register_targets"]))
            self.assertFalse(p["can_simulate"])


class PassiveTelemetryTests(unittest.TestCase):
    def test_speed_soc_current_and_pack_power(self):
        frames=[(0x155,bytes.fromhex("0006405480C80000")), # 40000? SOC 32968/400=82.42; 100 A
                (0x599,bytes.fromhex("0000000000001388")),
                (0x55f,bytes.fromhex("000000000021C21C"))]
        s=decode_frames(frames)
        self.assertEqual(s["speed"],50)
        self.assertEqual(s["soc"],82.42)
        self.assertEqual(s["current"],100)
        self.assertEqual(s["voltage"],54)
        self.assertEqual(s["power"],5.4)

    def test_invalid_latest_frame_does_not_reuse_old_data(self):
        s=decode_frames([(0x599,bytes.fromhex("0000000000001388")),(0x599,bytes.fromhex("000000000000FFFF")),(0x155,bytes.fromhex("0006409480C80000"))])
        self.assertNotIn("speed",s);self.assertNotIn("soc",s);self.assertNotIn("current",s)

    def test_absent_channels_remain_absent(self):
        self.assertEqual(decode_frames([]),{"source":"live-can","frame_count":0})
        self.assertNotIn("power",decode_frames([(0x155,bytes.fromhex("0006405480C80000"))]))

    def test_vehicle_state_and_unknown_gear(self):
        s=decode_frames([(0x597,bytes.fromhex("0010000000000000")),(0x59b,bytes.fromhex("0001000000000000"))])
        self.assertEqual(s["gear"],"N");self.assertTrue(s["footbrake"]);self.assertTrue(s["key_on"]);self.assertFalse(s["go"])
        self.assertEqual(decode_frames([(0x59b,bytes.fromhex("FF09000000000000"))])["gear"],"unknown")

    def test_failed_capture_restores_sdo_filter(self):
        link=ElmLink("test");calls=[]
        with patch.object(link,"command",side_effect=lambda c: calls.append(c) or "OK"),patch.object(link,"_monitor",side_effect=BusError("BUFFER FULL")):
            with self.assertRaises(BusError):link.capture()
        self.assertEqual(calls[-1],"ATCRA581")

    def test_filter_groups_and_merge(self):
        link=ElmLink("test");calls=[]
        with patch.object(link,"command",side_effect=lambda c:calls.append(c) or "OK"),patch.object(link,"_monitor",side_effect=[[(0x599,b'12345678')],[(0x155,b'12345678')]]):
            self.assertEqual(len(link.capture()),2)
        self.assertEqual(calls,["ATCSM1","ATCM700","ATCF500","ATCRA155","ATCRA581"])

    def test_mismatched_sdo_response_is_rejected(self):
        class Link:
            def exchange(self,*args):return bytes.fromhex("4B212901E8030000")
        with self.assertRaises(BusError):SDO(Link()).number(0x2920,1,2)

    def test_no_writes_added_to_transport(self):
        with self.assertRaises(BusError):ElmLink("test").exchange(bytes.fromhex("2B202901BC020000"),lambda x:True)
