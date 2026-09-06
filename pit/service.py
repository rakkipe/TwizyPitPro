import csv
import io
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid
from datetime import datetime, timezone

from .catalog import compatibility, defaults, fingerprint, parameters, sdo_candidates, validate, variant_bundle
from .canopen import BusError, ElmLink, M5Link, SDO
from .tuning import register_inventory, compare_snapshot, targets
from .telemetry import decode_frames


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, allow_nan=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, path)


class PitService:
    def __init__(self, directory, clock=time.monotonic):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.bus_lock = threading.Lock()
        self.clock = clock
        self.stop = threading.Event()
        self.link = None
        self.mode = "demo"
        self.connected = True
        self.busy = False
        self.running = False
        self.fault_scenario = "none"
        self.identity = self.demo_identity("80", "0712.0002")
        self.current = defaults("80")
        self.profile_name = "Modelreferentie · demo"
        self.sample = {}
        self.history = []
        self.events = []
        self.scan = None
        self.plan = None
        self.revision = 0
        self.session = None
        self.started = clock()
        self.pending_path = self.directory / "pending-demo.json"
        self.pending = None
        if self.pending_path.exists():
            try:
                self.pending = json.loads(self.pending_path.read_text(encoding="utf-8"))
                saved = self.pending
                comp = compatibility(saved["identity"])
                if saved["mode"] != "demo" or saved["identity"].get("source") != "simulation" or not comp["known"] or not re_id(saved["id"]):
                    raise ValueError("Ongeldig demo-journaal.")
                validate(saved["before"], comp["model"])
                validate(saved["after"], comp["model"])
                self.identity = saved["identity"].copy()
                self.current = saved["before"].copy()
                saved["previous_phase"] = saved["phase"]
                saved["phase"] = "interrupted-demo"
            except (ValueError, OSError, KeyError, TypeError):
                self.pending = {"phase": "corrupt", "message": "Onleesbaar demo-transactiejournaal."}
        self.event("Systeem gestart", "Demo actief. Geen voertuigverbinding geopend.")
        self.tick()

    @staticmethod
    def demo_identity(model, software):
        return dict(name="Gen4 (Renault Twizy) · DEMO", hardware="DEMO-HW", software=software,
                    vendor=0x1E, product=0x0712302D if model == "80" else 0x0712301B,
                    revision=0x10019 if software == "0712.0001" else 0x10021,
                    serial=80000001 if model == "80" else 45000001, source="simulation")

    def event(self, title, detail, level="info"):
        item = dict(at=now(), title=title, detail=detail, level=level, mode=self.mode)
        self.events.insert(0, item)
        self.events = self.events[:150]
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def tick(self):
        with self.lock:
            if self.mode != "demo":
                return
            t = self.clock() - self.started
            speed = max(0, 48 + 23 * math.sin(t / 7) + 8 * math.sin(t / 2.7)) if self.running else 0
            speed = min(speed, self.current["speed"])
            power = (4.2 + 9 * math.sin(t / 7 + .7)) * self.current["drive"] / 100 if self.running else 0
            battery = 54.5 - max(power, 0) * .12
            self.sample = dict(at=now(), age=0, speed=round(speed, 1), rpm=round(speed*(5814/45 if compatibility(self.identity)["model"] == "45" else 7250/80)),
                               soc=round(82.4-(t % 1200)/150, 1), voltage=round(battery, 1),
                               current=round(power * 1000 / battery, 1), power=round(power, 1),
                               motor_temp=round(47+7*math.sin(t/60), 1), controller_temp=round(34+3*math.sin(t/50), 1),
                               battery_temp=26.0, aux=10.7 if self.fault_scenario == "12v" else 13.1,
                               source="simulation", connected=True)
            if self.fault_scenario == "thermal":
                self.sample["motor_temp"] = 118
            self._append_sample()

    def _append_sample(self):
        if self.history and self.clock() - self.last_sample < .9:
            return
        self.last_sample = self.clock()
        self.history.append(dict(self.sample))
        self.history = self.history[-300:]
        if self.session:
            with (self.directory / "sessions" / f"{self.session['id']}.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(self.sample, allow_nan=False) + "\n")
            self.session["samples"] += 1

    def start_worker(self):
        def worker():
            while not self.stop.wait(.25):
                try:
                    if self.mode == "demo":
                        self.tick()
                    elif self.connected and not self.busy:
                        self.live_sample()
                        self.stop.wait(1.5)
                except Exception as exc:
                    with self.lock:
                        self.connected = False
                        self.sample = {"at": now(), "source": "live", "connected": False}
                        self.plan = None
                        self.event("Verbinding onderbroken", str(exc), "error")
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def live_sample(self):
        with self.bus_lock:
            with self.lock:
                if self.mode != "live" or not self.link or self.busy:
                    return
                link = self.link
            client = SDO(link)
            sample = dict(at=now(), source="live", connected=True, errors=[])
            for key, index, sub, width, signed in (("rpm", 0x606C, 0, 4, True), ("motor_temp", 0x4600, 3, 2, True), ("controller_temp", 0x5100, 4, 1, True)):
                try:
                    sample[key] = client.number(index, sub, width, signed)
                except BusError as exc:
                    sample[key] = None
                    sample["errors"].append(str(exc))
            if all(sample[k] is None for k in ("rpm", "motor_temp", "controller_temp")):
                raise BusError("Geen geldige telemetrie meer ontvangen.")
            # No speed from a controller alone: gearbox changes cannot be excluded.
            try:
                sample["aux"] = link.voltage()
            except BusError as exc:
                sample["errors"].append(str(exc))
            try:
                decoded=decode_frames(link.capture())
                sample.update({k:v for k,v in decoded.items() if k!="source"})
                sample["can_capture_at"]=now()
            except BusError as exc:
                sample["errors"].append("CAN-broadcasts: "+str(exc))
            sample["at"]=now()
            with self.lock:
                self.sample = sample
                self._append_sample()

    def ports(self):
        try:
            from serial.tools import list_ports
            return [dict(port=p.device, description=p.description, vid=p.vid, pid=p.pid) for p in list_ports.comports()]
        except ImportError:
            return []

    def connect(self, mode, port=None, adapter="elm", model="80", software="0712.0002"):
        if mode not in ("demo", "live"):
            raise ValueError("Ongeldige verbindingsmodus.")
        if model not in ("45", "80") or software not in ("0712.0001", "0712.0002", "0712.0003", "9999.9999"):
            raise ValueError("Onbekend demoscenario.")
        with self.lock:
            if self.session or self.pending or self.busy:
                raise ValueError("Rond eerst de sessie of demo-transactie af.")
            self.busy = True
        link = None
        try:
            if mode == "live":
                if adapter not in ("elm", "m5") or port not in {p["port"] for p in self.ports()}:
                    raise ValueError("Selecteer een aanwezige COM-poort en adapter.")
            with self.bus_lock:
                if self.link:
                    self.link.close()
                    self.link = None
                with self.lock:
                    self.connected = False
                    self.mode = mode
                    self.sample = {}
                    self.history = []
                    self.scan = self.plan = None
                    self.running = False
                    self.identity = {}
                    self.current = {}
                    self.revision += 1
                if mode == "demo":
                    identity = self.demo_identity(model, software)
                else:
                    link = (ElmLink if adapter == "elm" else M5Link)(port)
                    link.open()
                    identity = SDO(link).identity()
                    identity["source"] = "live"
                with self.lock:
                    self.identity = identity
                    self.link = link
                    self.connected = True
                    self.current = defaults(model) if mode == "demo" else {}
                    self.profile_name = "Modelreferentie · demo" if mode == "demo" else "Nog niet uitgelezen"
                    self.fault_scenario = "none"
                    self.event("Verbonden", f"{compatibility(identity)['label']} · {identity.get('software', 'onbekend')} · {mode}")
        except Exception as exc:
            if link:
                link.close()
            with self.lock:
                self.connected = False
                self.event("Verbinding mislukt", str(exc), "error")
            raise
        finally:
            with self.lock:
                self.busy = False
        self.tick()
        return self.state()

    def disconnect(self):
        with self.lock:
            if self.busy or self.session:
                raise ValueError("Stop eerst de lopende scan of opnamesessie.")
        with self.bus_lock:
            if self.link:
                self.link.close()
            with self.lock:
                self.link = None
                self.connected = False
                self.running = False
                self.mode = "offline"
                self.sample = {}
                self.plan = None
                self.event("Verbinding gesloten", "Geen busverbinding actief.")

    def diagnose(self):
        with self.lock:
            if self.busy or not self.connected:
                raise ValueError("Geen beschikbare verbinding.")
            self.busy = True
        try:
            report = dict(at=now(), mode=self.mode, identity=self.identity.copy(), observations=[], registers=[], complete=True)
            if self.mode == "demo":
                report["observations"] = [dict(name="Controller", status="ok", text="Gesimuleerde CANopen-identiteit gelezen."),
                                          dict(name="Foutregister", status="ok" if self.fault_scenario == "none" else "attention", text="Geen gesimuleerde fout." if self.fault_scenario == "none" else f"Testscenario: {self.fault_scenario}"),
                                          dict(name="12 V", status="attention" if self.fault_scenario == "12v" else "ok", text=f"{self.sample.get('aux', 0)} V · demo")]
                report["registers"] = sdo_candidates(self.current, compatibility(self.identity)["model"])
                report["scope"] = "Demo: gesimuleerde controller en storingen. Geen echte voertuigdiagnose."
            else:
                with self.bus_lock:
                    client = SDO(self.link)
                    self.identity = client.identity()
                    self.identity["source"] = "live"
                    report["identity"] = self.identity.copy()
                    if self.identity.get("errors"): report["complete"]=False
                    for index, sub, width, title in ((0x1001, 0, 1, "CANopen error register"), (0x6041, 0, 2, "Statusword"), (0x1003, 0, 1, "Aantal opgeslagen fouten")):
                        try:
                            value = client.number(index, sub, width)
                            report["registers"].append(dict(address=f"{index:04X}:{sub:02X}", raw=value, width=width, key=title))
                            report["observations"].append(dict(name=title, status="attention" if value and index in (0x1001, 0x1003) else "info", text=f"0x{value:X} ({value})"))
                            if index == 0x1003:
                                for entry in range(1, min(value, 16)+1):
                                    fault = client.number(index, entry)
                                    report["registers"].append(dict(address=f"1003:{entry:02X}", raw=fault, width=4, key="Fouthistorie (niet per se actief)"))
                        except BusError as exc:
                            report["complete"] = False
                            report["observations"].append(dict(name=title, status="unknown", text=str(exc)))
                    comp = compatibility(self.identity)
                    if comp["known"]:
                        for row in register_inventory(comp["model"]):
                            row = dict(row)
                            try:
                                row["raw"] = client.number(row["index"], row["sub"], row["width"], row.get("signed",False))
                                row["source"] = "live"
                            except BusError as exc:
                                row["raw"] = None
                                row["error"] = str(exc)
                                report["complete"] = False
                            report["registers"].append(row)
                    report["scope"] = "SEVCON CANopen en beschikbare SDO's. Geen volledige Renault ECU/airbag/BMS-DTC-scan. Fouthistorie is niet automatisch een actuele storing."
                    report["inventory_count"]=len(register_inventory(comp["model"])) if comp["known"] else 0
                    report["fingerprint"]=fingerprint(self.identity)
                    report["power_map_commit"]={"address":"4641:01","access":"write-only","readback":False}
            with self.lock:
                self.scan = report
                atomic_json(self.directory / "scans" / f"{uuid.uuid4().hex}.json", report)
                self.event("Diagnoserapport opgeslagen", "Volledig binnen geselecteerde scope." if report["complete"] else "Deels uitgelezen; ontbrekende waarden blijven onbekend.")
            return report
        finally:
            with self.lock:
                self.busy = False

    def set_demo(self, running=None, fault=None):
        with self.lock:
            if self.mode != "demo":
                raise ValueError("Deze bediening is alleen voor de simulator.")
            if running is not None:
                if type(running) is not bool:
                    raise ValueError("Ongeldige sessiestatus.")
                if self.pending and running:
                    raise ValueError("Rond eerst de demo-contactcyclus af.")
                self.running = running
            if fault is not None:
                if fault not in ("none", "12v", "serv", "thermal", "writefail"):
                    raise ValueError("Onbekend foutscenario.")
                self.fault_scenario = fault
            self.plan = None
            self.tick()

    def make_plan(self, values):
        with self.lock:
            comp = compatibility(self.identity)
            model = comp["model"]
            if not model:
                raise ValueError("Eerst een controllerfamilie identificeren.")
            values = validate(values, model)
            meta = {p["key"]: p for p in parameters(model)}
            changes = [dict(key=k, name=meta[k]["name"], unit=meta[k]["unit"], before=self.current.get(k), after=v,
                            mapping=meta[k]["mapping"]) for k, v in values.items() if self.current.get(k) != v]
            blockers = []
            if self.mode != "demo":
                blockers.append("Live tuning is in deze release niet beschikbaar; uitlezen wel.")
            if not comp["known"] or comp["locked"]:
                blockers.append(comp["reason"])
            if not self.connected:
                blockers.append("Geen verbinding.")
            if self.running:
                blockers.append("Simulator rijdt: zet terug in pitstand.")
            if self.fault_scenario not in ("none", "writefail"):
                blockers.append("Los eerst het gesimuleerde storingsscenario op.")
            if self.pending:
                blockers.append("Openstaande transactie: eerst contactcyclus of demo-herstel.")
            if self.busy:
                blockers.append("Er loopt nog een verbindings- of diagnoseactie.")
            if not changes:
                blockers.append("Geen gewijzigde instellingen.")
            keys = {c["key"] for c in changes}
            snapshot=self.scan if self.scan and self.scan.get("mode")=="live" and fingerprint(self.scan.get("identity",{}))==comp["fingerprint"] else None
            register_targets=compare_snapshot(values,model,snapshot["registers"] if snapshot else [])
            candidates=[r for r in register_targets if keys.intersection(r["keys"])]
            plan = dict(id=uuid.uuid4().hex, at=now(), revision=self.revision, fingerprint=comp["fingerprint"],
                        values=values, changes=changes, blockers=blockers, can_simulate=not blockers,
                        candidates=candidates, expires_in=60, mode=self.mode,
                        register_targets=register_targets, mapped_fields=len({k for r in register_targets for k in r["keys"]}),
                        warning="Alle 43 velden zijn vertaald naar registerdoelen. Werkelijke beginwaarden komen alleen uit een identiteitsgebonden scan. Dit is geen uitvoerbare schrijfvolgorde; hardwarekwalificatie, eigenaarstoestemming, verse CAN-controles en kaartcommit blijven vereist.")
            self.plan = dict(plan, deadline=self.clock()+60)
            return plan

    def apply_demo(self, plan_id):
        with self.lock:
            if self.mode != "demo":
                raise ValueError("Live schrijven is niet geïmplementeerd.")
            plan = self.plan
            if not plan or plan["id"] != plan_id or self.clock() > plan["deadline"]:
                raise ValueError("Plan ontbreekt of is verlopen; maak een nieuwe vergelijking.")
            if self.pending or self.running or self.busy or self.fault_scenario not in ("none", "writefail"):
                raise ValueError("Simulator niet gereed voor toepassing.")
            if plan["blockers"] or plan["revision"] != self.revision or plan["fingerprint"] != fingerprint(self.identity):
                raise ValueError("Controller of beginsituatie wijkt af van het plan.")
            transaction = dict(id=uuid.uuid4().hex, phase="prepared", at=now(), mode="demo",
                               identity=self.identity.copy(), before=self.current.copy(), after=plan["values"], attempts=[])
            atomic_json(self.directory / "backups" / f"{transaction['id']}.json", transaction)
            atomic_json(self.pending_path, transaction)
            self.pending = transaction
            try:
                for change in plan["changes"]:
                    transaction["attempts"].append(change["key"])
                    transaction["phase"] = "applying"
                    atomic_json(self.pending_path, transaction)
                    self.current[change["key"]] = change["after"]
                    if self.fault_scenario == "writefail":
                        raise ValueError("Gesimuleerde read-back-fout.")
                    if self.current[change["key"]] != change["after"]:
                        raise ValueError("Demo read-back mismatch.")
                transaction["phase"] = "awaiting-demo-cycle"
                atomic_json(self.pending_path, transaction)
                self.profile_name = "Aangepast · contactcyclus wacht"
                self.event("Demo-profiel toegepast", f"{len(plan['changes'])} instellingen; controle na demo-contactcyclus wacht.")
            except Exception:
                self.current = transaction["before"].copy()
                transaction["phase"] = "rolled-back"
                atomic_json(self.pending_path, transaction)
                self.event("Demo-rollback uitgevoerd", "Testfout: oorspronkelijke simulatie-instellingen teruggezet.", "warning")
                raise
            finally:
                self.revision += 1
                self.plan = None
            return transaction

    def demo_cycle(self, restore=False):
        with self.lock:
            if self.mode != "demo" or not self.pending:
                raise ValueError("Geen openstaande demo-transactie.")
            transaction = self.pending
            if transaction.get("phase") == "corrupt":
                raise ValueError("Journaal beschadigd; handmatige inspectie nodig.")
            if transaction.get("phase") == "interrupted-demo" and not restore:
                raise ValueError("Onderbroken simulatie: kies Demo herstellen vanuit de originele snapshot.")
            if fingerprint(transaction["identity"]) != fingerprint(self.identity):
                raise ValueError("Democontroller wijkt af van het journaal.")
            if restore or transaction["phase"] == "rolled-back":
                self.current = transaction["before"].copy()
                transaction["phase"] = "restored-demo"
            else:
                if self.current != transaction["after"]:
                    raise ValueError("Simulatiebeginsituatie gewijzigd; kies demo herstellen.")
                transaction["phase"] = "verified-demo-cycle"
            atomic_json(self.directory / "transactions" / f"{transaction['id']}.json", transaction)
            self.pending_path.unlink()
            self.pending = None
            self.revision += 1
            self.plan = None
            self.profile_name = "Aangepast · demo gecontroleerd" if not restore else "Herstelde demosnapshot"
            self.event("Demo-transactie afgerond", transaction["phase"] + "; geen bewijs van een echte contactcyclus.")

    def save_profile(self, name, values):
        with self.lock:
            model = compatibility(self.identity)["model"]
            if not model:
                raise ValueError("Onbekende controllerfamilie.")
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
                raise ValueError("Profielnaam: 1–60 tekens.")
            profile = dict(id=uuid.uuid4().hex, name=name.strip(), at=now(), model=model,
                           software=self.identity.get("software"), revision=self.identity.get("revision"),
                           origin=self.mode, values=validate(values, model), qualified=False)
            atomic_json(self.directory / "profiles" / f"{profile['id']}.json", profile)
            self.event("Profiel opgeslagen", profile["name"])
            return profile

    def profiles(self):
        profiles = []
        for path in sorted((self.directory / "profiles").glob("*.json"), reverse=True):
            try:
                profiles.append(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                continue
        return profiles

    def recording(self, action, name="Circuittraining"):
        with self.lock:
            if action == "start":
                if self.session or not self.connected:
                    raise ValueError("Geen vrije verbinding om een sessie te starten.")
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
                    raise ValueError("Sessienaam: 1–80 tekens.")
                self.session = dict(id=uuid.uuid4().hex, name=name.strip(), at=now(), mode=self.mode,
                                    samples=0, laps=[], identity=self.identity.copy(), profile=self.current.copy(), last_lap=self.clock())
                (self.directory / "sessions").mkdir(exist_ok=True)
                self._save_session()
                self.event("Sessie gestart", name)
            elif action == "lap":
                if not self.session:
                    raise ValueError("Start eerst een opnamesessie.")
                elapsed = self.clock() - self.session["last_lap"]
                self.session["laps"].append(dict(number=len(self.session["laps"])+1, seconds=round(elapsed, 3), at=now(), method="manual"))
                self.session["last_lap"] = self.clock()
                self._save_session()
            elif action == "stop":
                if not self.session:
                    raise ValueError("Geen actieve sessie.")
                self.session["ended_at"] = now()
                self._save_session()
                self.event("Sessie opgeslagen", f"{self.session['name']} · {self.session['samples']} samples")
                self.session = None
            else:
                raise ValueError("Ongeldige sessieactie.")

    def _save_session(self):
        atomic_json(self.directory / "sessions" / f"{self.session['id']}.json", {k:v for k,v in self.session.items() if k != "last_lap"})

    def sessions(self):
        result = []
        for path in (self.directory / "sessions").glob("*.json"):
            try:
                result.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(result, key=lambda x: x["at"], reverse=True)

    def csv_session(self, session_id):
        if not re_id(session_id):
            raise ValueError("Ongeldig sessie-ID.")
        path = self.directory / "sessions" / f"{session_id}.jsonl"
        if not path.exists():
            raise ValueError("Nog geen samples voor deze sessie.")
        output = io.StringIO(newline="")
        fields = ("at", "source", "speed", "rpm", "soc", "voltage", "current", "power", "motor_temp", "controller_temp", "battery_temp", "aux")
        writer = csv.DictWriter(output, fields, extrasaction="ignore")
        writer.writeheader()
        for line in path.read_text(encoding="utf-8").splitlines():
            writer.writerow(json.loads(line))
        return output.getvalue()

    def state(self):
        with self.lock:
            sample = self.sample.copy()
            if sample.get("at"):
                sample["age"] = round(max(0, (datetime.now(timezone.utc)-datetime.fromisoformat(sample["at"])).total_seconds()), 1)
            return dict(mode=self.mode, connected=self.connected, running=self.running, busy=self.busy,
                        compatibility=compatibility(self.identity), identity=self.identity, current=self.current,
                        profile_name=self.profile_name, sample=sample, history=self.history[-90:], events=self.events[:30],
                        pending=self.pending, session={k:v for k,v in self.session.items() if k != "last_lap"} if self.session else None,
                        fault_scenario=self.fault_scenario, revision=self.revision, scan=self.scan,
                        parameters=parameters(compatibility(self.identity)["model"] or "80"),
                        limits=dict(live_write=False, firmware_flash=False, full_ecu_diagnostics=False))


def re_id(value):
    return isinstance(value, str) and len(value) == 32 and all(c in "0123456789abcdef" for c in value)
