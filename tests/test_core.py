import json
from pathlib import Path
import tempfile
import unittest

from pit.catalog import compatibility, defaults, parameters, sdo_candidates, validate, variant_bundle
from pit.canopen import Abort, BusError, ElmLink, M5Link, SDO, parse_elm_frames
from pit.service import PitService


class CatalogTests(unittest.TestCase):
    def test_four_variants_and_43_fields(self):
        self.assertEqual(len(variant_bundle()), 4)
        self.assertEqual(len(parameters()), 43)
        self.assertTrue(all(not v["live_write"] for v in variant_bundle()))

    def test_identity_requires_exact_revision(self):
        identity = PitService.demo_identity("80", "0712.0002")
        self.assertTrue(compatibility(identity)["known"])
        identity["revision"] = 12
        self.assertFalse(compatibility(identity)["known"])

    def test_locked_and_unknown_versions(self):
        for software in ("0712.0003", "0712.0010", "0713.0000"):
            with self.subTest(software=software):
                self.assertTrue(compatibility(PitService.demo_identity("80", software))["locked"])
        for software in ("", "abc", "0712.0002junk", "0712.2", "00010021"):
            with self.subTest(software=software):
                self.assertFalse(compatibility(PitService.demo_identity("80", software))["known"])

    def test_unknown_product_not_assumed_twizy(self):
        self.assertIsNone(compatibility({"product":123, "software":"0712.0002"})["model"])

    def test_bad_profile_numbers_and_shape(self):
        for value in (True, float('nan'), float('inf'), 10.5, "80", None, -10, 1000):
            values = defaults()
            values["drive"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(values)
        for values in ({}, {**defaults(), "login":1}, None):
            with self.assertRaises(ValueError):
                validate(values)

    def test_cross_parameter_invariants(self):
        for edits in ({"warn":79}, {"D_speed2":20}, {"B_speed3":39}, {"brakelight_on":20,"brakelight_off":30}):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                validate({**defaults(), **edits})

    def test_twizy45_reference_is_distinct(self):
        self.assertEqual(defaults("45")["speed"],45)
        self.assertEqual(defaults("45")["neutral"],21)
        self.assertEqual(defaults("45")["ramp_start"],30)

    def test_reference_raw_scaling_preserves_exact_stock(self):
        rows = {r["address"]:r for r in sdo_candidates(defaults("80"),"80")}
        self.assertEqual(rows["2920:03"]["raw"],182)
        self.assertEqual(rows["2920:07"]["raw"],2500)
        self.assertEqual(rows["290A:01"]["raw"],8)
        self.assertEqual(rows["290A:01"]["width"],1)
        rows45 = {r["address"]:r for r in sdo_candidates(defaults("45"),"45")}
        self.assertEqual(rows45["2920:03"]["raw"],209)
        self.assertEqual(rows45["2920:07"]["raw"],2083)

    def test_no_old_mislabelled_aliases(self):
        addresses = {r["address"] for r in sdo_candidates(defaults(),"80")}
        self.assertNotIn("3813:01",addresses)
        self.assertNotIn("3813:02",addresses)
        self.assertNotIn("4600:01",addresses)


class FakeLink:
    def __init__(self, replies):
        self.replies=list(replies)
        self.requests=[]
    def exchange(self, request, matcher):
        self.requests.append(request)
        while self.replies:
            reply=self.replies.pop(0)
            if matcher(reply):
                return reply
        raise BusError("Geen passend antwoord")


class CanopenTests(unittest.TestCase):
    def test_elm_formats(self):
        for raw in ("581 43 18 10 02 2D 30 12 07\r>", "5818431810022D301207", "581431810022D301207"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_elm_frames(raw),[(0x581,bytes.fromhex("431810022D301207"))])

    def test_elm_discards_non_frames_and_bad_dlc(self):
        self.assertEqual(parse_elm_frames("NO DATA\rOK\rSEARCHING...\r5817431810022D301207\rFFF001122\r>"),[])

    def test_index_must_match(self):
        link=FakeLink([bytes.fromhex("431810032D301207"),bytes.fromhex("431810022D301207")])
        self.assertEqual(SDO(link).number(0x1018,2),0x0712302D)
        self.assertEqual(link.requests,[bytes.fromhex("4018100200000000")])

    def test_abort_retains_code(self):
        with self.assertRaises(Abort) as error:
            SDO(FakeLink([bytes.fromhex("8003100000000206")])).upload(0x1003)
        self.assertEqual(error.exception.code,0x06020000)

    def test_segmented_software_string(self):
        link=FakeLink([bytes.fromhex("410A100009000000"),b"\x00"+b"0712.00",b"\x1B"+b"02"+bytes(5)])
        self.assertEqual(SDO(link).upload(0x100A),b"0712.0002")
        self.assertEqual([r[0] for r in link.requests],[0x40,0x60,0x70])

    def test_segment_toggle_mismatch(self):
        with self.assertRaisesRegex(BusError,"toggle"):
            SDO(FakeLink([bytes.fromhex("410A100009000000"),b"\x10"+b"0712.00"])).upload(0x100A)

    def test_segment_length_mismatch(self):
        with self.assertRaisesRegex(BusError,"lengte"):
            SDO(FakeLink([bytes.fromhex("410A100004000000"),b"\x09abc"+bytes(4)])).upload(0x100A)

    def test_excessive_object_rejected_before_segments(self):
        with self.assertRaisesRegex(BusError,"leeslimiet"):
            SDO(FakeLink([bytes.fromhex("410A100000010100")])).upload(0x100A)

    def test_signed_integer(self):
        self.assertEqual(SDO(FakeLink([bytes.fromhex("4B004603F6FF0000")])).number(0x4600,3,2,True),-10)

    def test_width_mismatch_is_not_coerced(self):
        with self.assertRaisesRegex(BusError,"verwacht 4"):
            SDO(FakeLink([bytes.fromhex("4B79600012000000")])).number(0x6079,0,4)

    def test_both_transports_reject_download_and_nmt(self):
        for cls in (ElmLink,M5Link):
            for command in (0x23,0x2B,0x2F,0x22,0x80,0x01,0x81):
                with self.subTest(transport=cls.__name__,command=command), self.assertRaises(BusError):
                    cls("FAKE").exchange(bytes([command])+bytes(7),lambda _:True)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.time=10.0
        self.service=PitService(self.temp.name,clock=lambda:self.time)
    def tearDown(self):
        self.temp.cleanup()
    def plan(self, **edits):
        return self.service.make_plan({**self.service.current,**edits})

    def test_start_does_not_open_vehicle(self):
        self.assertEqual(self.service.mode,"demo")
        self.assertIsNone(self.service.link)
        self.assertEqual(self.service.sample["source"],"simulation")

    def test_demo_transaction_backup_and_cycle(self):
        original=self.service.current.copy()
        plan=self.plan(drive=85,neutral=22)
        self.service.apply_demo(plan["id"])
        self.assertEqual(self.service.current["drive"],85)
        self.assertEqual(self.service.pending["phase"],"awaiting-demo-cycle")
        backups=list((Path(self.temp.name)/"backups").glob("*.json"))
        self.assertEqual(json.loads(backups[0].read_text())["before"],original)
        self.service.demo_cycle()
        self.assertIsNone(self.service.pending)
        self.assertFalse(self.service.pending_path.exists())
        self.assertEqual(len(list((Path(self.temp.name)/"transactions").glob("*.json"))),1)

    def test_stale_plan_rejected(self):
        plan=self.plan(drive=85)
        self.time+=61
        with self.assertRaisesRegex(ValueError,"verlopen"):
            self.service.apply_demo(plan["id"])

    def test_wrong_plan_id_rejected(self):
        self.plan(drive=80)
        with self.assertRaises(ValueError):
            self.service.apply_demo("wrong")

    def test_changed_identity_and_revision_rejected(self):
        plan=self.plan(drive=85)
        self.service.identity["serial"]+=1
        with self.assertRaises(ValueError):
            self.service.apply_demo(plan["id"])
        self.service.identity["serial"]-=1
        self.service.revision+=1
        with self.assertRaises(ValueError):
            self.service.apply_demo(plan["id"])

    def test_locked_firmware_cannot_simulate_apply(self):
        self.service.connect("demo",software="0712.0003")
        plan=self.plan(drive=85)
        self.assertFalse(plan["can_simulate"])
        with self.assertRaises(ValueError):
            self.service.apply_demo(plan["id"])

    def test_simulator_endpoint_cannot_write_to_vehicle(self):
        plan=self.plan(drive=85)
        self.service.mode="live"
        with self.assertRaisesRegex(ValueError,"alleen de simulator"):
            self.service.apply_demo(plan["id"])

    def test_drive_and_fault_guards(self):
        self.service.set_demo(running=True)
        self.assertFalse(self.plan(drive=85)["can_simulate"])
        self.service.set_demo(running=False)
        for scenario in ("serv","12v","thermal"):
            self.service.set_demo(fault=scenario)
            self.assertFalse(self.plan(drive=85)["can_simulate"])

    def test_injected_readback_error_rolls_back(self):
        original=self.service.current.copy()
        self.service.set_demo(fault="writefail")
        plan=self.plan(drive=85)
        with self.assertRaisesRegex(ValueError,"read-back"):
            self.service.apply_demo(plan["id"])
        self.assertEqual(self.service.current,original)
        self.assertEqual(self.service.pending["phase"],"rolled-back")
        self.assertFalse(self.plan(drive=80)["can_simulate"])
        self.service.demo_cycle(restore=True)
        self.assertIsNone(self.service.pending)

    def test_restart_preserves_pending_identity_and_requires_restore(self):
        self.service.connect("demo",model="45",software="0712.0001")
        before=self.service.current.copy()
        self.service.apply_demo(self.plan(drive=80)["id"])
        restarted=PitService(self.temp.name)
        self.assertEqual(compatibility(restarted.identity)["model"],"45")
        self.assertEqual(restarted.pending["phase"],"interrupted-demo")
        with self.assertRaises(ValueError):
            restarted.demo_cycle()
        restarted.demo_cycle(restore=True)
        self.assertEqual(restarted.current,before)

    def test_corrupt_journal_blocks(self):
        for content in ("{broken", "{}", '{"mode":"live"}'):
            with self.subTest(content=content):
                self.service.pending_path.write_text(content)
                restarted=PitService(self.temp.name)
                self.assertEqual(restarted.pending["phase"],"corrupt")
                with self.assertRaises(ValueError):
                    restarted.connect("demo")

    def test_profile_bound_to_model_and_firmware(self):
        profile=self.service.save_profile("Wet",defaults())
        self.assertEqual(profile["software"],"0712.0002")
        self.assertFalse(profile["qualified"])
        self.assertEqual(len(self.service.profiles()),1)

    def test_names_do_not_become_paths(self):
        profile=self.service.save_profile("../../example",defaults())
        self.assertTrue((Path(self.temp.name)/"profiles"/(profile["id"]+".json")).is_file())

    def test_session_and_csv_preserve_source(self):
        self.service.recording("start","Test stint")
        sid=self.service.session["id"]
        self.time+=2;self.service.tick()
        self.service.recording("lap")
        self.service.recording("stop")
        csv=self.service.csv_session(sid)
        self.assertIn("simulation",csv)
        self.assertEqual(self.service.sessions()[0]["samples"],1)
        self.assertEqual(self.service.sessions()[0]["laps"][0]["method"],"manual")

    def test_export_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.service.csv_session("../../secret")

    def test_live_state_does_not_inject_demo_telemetry(self):
        self.service.mode="live"
        self.service.sample={"source":"live","rpm":25}
        self.service.tick()
        self.assertNotIn("soc",self.service.sample)
        self.assertNotIn("speed",self.service.sample)


if __name__ == "__main__":
    unittest.main()
