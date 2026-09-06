"""Reviewed vLinker transactions, with durable intent and explicit recovery.

Protocol details follow the retained OVMS source and Twizy 0712.0002 DCF.
This module does not open a port or write anything at construction time.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from .canopen import Abort, BusError, ElmLink, SDO, parse_elm_frames
from .catalog import compatibility, fingerprint, validate
from .tuning import compare_snapshot, map_update_order, register_inventory


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, allow_nan=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def ordered_changes(rows):
    """Preserve the four-point map bounds while changing their speed entries."""
    result = [r for r in rows if r["before"] != r["raw"] and not r.get("map")]
    for letter in "DNB":
        speeds = sorted((r for r in rows if r.get("map") == letter and r["component"] == "speed"), key=lambda r: r["point"])
        order = map_update_order([r["before"] for r in speeds], [r["raw"] for r in speeds])
        result.extend(speeds[n] for n in order)
        result.extend(r for r in rows if r.get("map") == letter and r["component"] == "level" and r["before"] != r["raw"])
    return result


class VLinkerControl:
    """Narrow protocol used only by the transaction executor, never a raw API."""
    def __init__(self, link):
        if not isinstance(link, ElmLink):
            raise ValueError("Deze schrijfroute vereist de vLinker/ELM-adapter.")
        self.link = link
        self.sdo = SDO(link)
        self.guard_deadline = 0
        self.expected_identity = None

    def identity(self):
        return self.sdo.identity()

    def read(self, row):
        return self.sdo.number(row["index"], row["sub"], row["width"], row.get("signed", False))

    def guard(self, preop=False):
        if self.expected_identity and fingerprint(self.identity()) != fingerprint(self.expected_identity):
            raise BusError("Controller gewisseld; schrijven geblokkeerd.")
        evidence = self.link.write_guard(preop=preop)
        self.guard_deadline = time.monotonic()+.75
        return evidence

    def _fresh(self):
        if time.monotonic() > self.guard_deadline:
            raise BusError("Veiligheidscontrole verlopen; schrijfcommando niet verstuurd.")

    def download(self, index, sub, value, width=2, signed=False):
        self._fresh()
        if type(value) is not int or width not in (1, 2, 4):
            raise ValueError("Ongeldig schrijfdatatype.")
        header = index.to_bytes(2, "little") + bytes([sub])
        data = value.to_bytes(width, "little", signed=signed)
        request = bytes([{1: 0x2f, 2: 0x2b, 4: 0x23}[width]]) + header + data.ljust(4, b"\0")
        text = self.link.command(request.hex().upper())
        for can_id, response in parse_elm_frames(text):
            if can_id != 0x581 or len(response) != 8 or response[1:4] != header:
                continue
            if response[0] == 0x80:
                raise Abort(index, sub, int.from_bytes(response[4:], "little"))
            if response[0] == 0x60 and response[4:] == bytes(4):
                return
        raise BusError("Geen geldige schrijfbevestiging; uitkomst onbekend, geen automatische herhaling.")

    def level(self):
        return self.sdo.number(0x5000, 1, 1)

    def login(self):
        if self.level() != 4:
            self.download(0x5000, 3, 0)
            self.download(0x5000, 2, 0x4bdf)
        if self.level() != 4:
            raise BusError("SEVCON level 4 niet bevestigd.")

    def logout(self):
        self.download(0x5000, 3, 0)
        self.download(0x5000, 2, 0)
        if self.level() != 0:
            raise BusError("Uitloggen niet bevestigd.")

    def state(self):
        return self.sdo.number(0x5110, 0, 1)

    def mode(self, preop):
        self._fresh()
        try:
            if "OK" not in self.link.command("ATSH000").upper():
                raise BusError("NMT-header niet ingesteld.")
            answer = self.link.command("8001" if preop else "0101").upper()
            if any(err in answer for err in ("ERROR", "BUS OFF", "STOPPED", "?")):
                raise BusError("NMT-aanvraag geweigerd.")
        finally:
            if "OK" not in self.link.command("ATSH601").upper():
                raise BusError("SDO-header niet hersteld; verbind opnieuw.")
        time.sleep(.05)
        if self.state() != (127 if preop else 5):
            raise BusError("Gevraagde controllerstand niet bevestigd.")

    def write(self, row):
        self.download(row["index"], row["sub"], row["raw"], row["width"], row.get("signed", False))

    def commit(self):
        # DCF: 4641:01 is Boolean, write-only. Verify the full map afterwards.
        self.download(0x4641, 1, 1, 1)


class VehicleWriter:
    def __init__(self, directory, clock=time.monotonic):
        self.directory = Path(directory)
        self.path = self.directory / "pending-vehicle.json"
        self.clock = clock
        self.plan = None
        self.pending = None
        if self.path.exists():
            try:
                journal = json.loads(self.path.read_text(encoding="utf-8"))
                backup = self.directory / "vehicle-backups" / (journal["id"] + ".json")
                if not isinstance(journal["id"], str) or len(journal["id"]) != 32 or any(c not in "0123456789abcdef" for c in journal["id"]):
                    raise ValueError("Ongeldig transactie-ID")
                original = json.loads(backup.read_text(encoding="utf-8"))
                if digest(original) != journal["backup_sha256"]:
                    raise ValueError("Backup-hash wijkt af")
                # The immutable backup supplies the identity and complete targets.
                journal.update(identity=original["identity"], rows=original["rows"])
                journal["interrupted"] = True
                journal["cycle_off_seen"] = False
                self.pending = journal
            except (OSError, ValueError, KeyError, TypeError):
                self.pending = {"phase": "corrupt", "error": "Voertuigjournaal of backup beschadigd; handmatige inspectie vereist."}

    def status(self):
        pending = self.pending
        if not pending:
            return None
        return {k: copy.deepcopy(v) for k, v in pending.copy().items() if k not in ("identity", "rows")}

    def _persist(self):
        save_json(self.path, self.pending)

    def _identity(self, control, expected=None):
        identity = control.identity()
        comp = compatibility(identity)
        if identity.get("errors") or not comp["known"] or comp["locked"] or identity.get("vendor") != 30 or not identity.get("serial"):
            raise ValueError("Geen volledige, exact ondersteunde controlleridentiteit.")
        if expected and fingerprint(identity) != fingerprint(expected):
            raise ValueError("Controlleridentiteit wijkt af; niets verder schrijven.")
        control.expected_identity = copy.deepcopy(identity)
        return identity, comp["model"]

    def prepare(self, control, values, stock_drivetrain=False, brake_hardware=False, faults_resolved=False):
        self.plan = None
        if self.pending:
            raise ValueError("Eerst de openstaande voertuigtransactie controleren of herstellen.")
        if stock_drivetrain is not True:
            raise ValueError("Bevestig de originele motor/reductiekastcombinatie.")
        if faults_resolved is not True:
            raise ValueError("Los eerst de gemelde voertuigstoringen op, inclusief SERV. Bevestig dit vóór tuning.")
        identity, model = self._identity(control)
        values = validate(values, model)
        if (values["brakelight_on"], values["brakelight_off"]) != (100, 100) and brake_hardware is not True:
            raise ValueError("Aangepaste remlichthardware is niet bevestigd.")
        control.guard()
        if control.state() != 5:
            raise ValueError("Controller moet vóór voorbereiding operational zijn.")
        snapshot = []
        for row in register_inventory(model):
            snapshot.append(dict(row, raw=control.read(row), source="live"))
        self._identity(control, identity)
        rows = compare_snapshot(values, model, snapshot)
        if any(r["before"] is None or r["raw"] is None or not r["verified_width"] for r in rows):
            raise ValueError("De volledige beginsnapshot ontbreekt.")
        changes = ordered_changes(rows)
        if not changes:
            raise ValueError("Alle registerdoelen zijn al gelijk aan de uitgelezen waarden.")
        evidence = control.guard()
        plan = dict(id=uuid.uuid4().hex, identity=identity, model=model, values=values, rows=rows,
                    changes=changes, safety=evidence, expires_in=120, deadline=self.clock()+120)
        plan["review_hash"] = digest({k: plan[k] for k in ("id", "identity", "values", "rows")})
        self.plan = copy.deepcopy(plan)
        return {k: copy.deepcopy(v) for k, v in plan.items() if k != "deadline"}

    def apply(self, control, plan_id, review_hash):
        plan, self.plan = self.plan, None  # single-use even on failure
        if self.pending or not plan or plan["id"] != plan_id or plan["review_hash"] != review_hash or self.clock() > plan["deadline"]:
            raise ValueError("Schrijfplan ontbreekt, wijkt af of is verlopen.")
        self._identity(control, plan["identity"])
        control.guard()
        if control.state() != 5:
            raise ValueError("Controllerstand gewijzigd.")
        for row in plan["rows"]:
            if control.read(row) != row["before"]:
                raise ValueError("Beginwaarde gewijzigd bij " + row["address"] + "; maak een nieuw plan.")
        self._identity(control, plan["identity"])
        control.guard()
        if self.clock() > plan["deadline"]:
            raise ValueError("Plan verlopen tijdens de controle; maak een nieuw plan.")
        original = dict(id=plan["id"], identity=plan["identity"], rows=plan["rows"], values=plan["values"])
        save_json(self.directory / "vehicle-backups" / (plan["id"] + ".json"), original)
        self.pending = dict(original, backup_sha256=digest(original), phase="prepared", attempts=[], cycle_off_seen=False)
        self._persist()  # durable BEFORE the first login/state/write command
        self._execute(control, plan["changes"], restore=False)
        return self.status()

    def _execute(self, control, changes, restore):
        try:
            self.pending["phase"] = "entering-configuration"
            self._persist()
            control.guard(preop=control.state() == 127)
            control.login()
            control.guard(preop=control.state() == 127)
            control.mode(True)
            for row in changes:
                control.guard(preop=True)
                if control.level() != 4 or control.state() != 127:
                    raise BusError("Schrijfrechten of configuratiemodus verloren.")
                if control.read(row) != row["before"]:
                    raise BusError("Beginwaarde gewijzigd tijdens toepassing: " + row["address"])
                attempt = dict(address=row["address"], before=row["before"], after=row["raw"], verified=False)
                self.pending.update(phase="restoring" if restore else "writing", current=row["address"])
                self.pending["attempts"].append(attempt)
                self._persist()  # includes unacknowledged writes after a crash
                control.write(row)
                if control.read(row) != row["raw"]:
                    raise BusError("Teruggelezen waarde wijkt af: " + row["address"])
                attempt["verified"] = True
                self._persist()
            if any(r["index"] in (0x4610, 0x4611) and r["before"] != r["raw"] for r in self.pending["rows"]):
                control.guard(preop=True)
                self.pending["phase"] = "committing-map"
                self._persist()
                control.commit()
            wanted = "before" if restore else "raw"
            for row in self.pending["rows"]:
                if control.read(row) != row[wanted]:
                    raise BusError("Eindcontrole wijkt af: " + row["address"])
            control.guard(preop=True)
            control.mode(False)
            control.guard()
            control.logout()
            self.pending.update(phase="awaiting-contact-cycle", restored=restore, cycle_off_seen=False)
            self.pending.pop("error", None)
            self._persist()
        except Exception as exc:
            # No automatic rollback, mode change, retry or reset on an uncertain bus.
            self.pending.update(phase="recovery-required", error=str(exc), cycle_off_seen=False)
            self._persist()
            raise

    def review_restore(self, control, transaction_id):
        if not self.pending or self.pending.get("id") != transaction_id or self.pending["phase"] == "corrupt":
            raise ValueError("Geen passende hersteltransactie.")
        self._identity(control, self.pending["identity"])
        if control.state() not in (5, 127):
            raise ValueError("Onbekende controllerstand; herstel geblokkeerd.")
        control.guard(preop=control.state() == 127)
        rows = []
        for original in self.pending["rows"]:
            actual = control.read(original)
            if actual not in (original["before"], original["raw"]):
                raise ValueError("Onverwachte waarde bij herstel: " + original["address"])
            rows.append(dict(original, before=actual, raw=original["before"]))
        return dict(id=transaction_id, rows=rows, changes=ordered_changes(rows), identity=copy.deepcopy(self.pending["identity"]))

    def restore(self, control, transaction_id):
        review = self.review_restore(control, transaction_id)
        self.pending["cycle_off_seen"] = False
        self._persist()
        self._execute(control, review["changes"], restore=True)
        return self.status()

    def observe_contact_off(self, samples):
        if not self.pending or self.pending["phase"] != "awaiting-contact-cycle":
            return
        # Positive, freshly captured CAN evidence; lack of traffic is not OFF.
        for can_id, raw in samples:
            if can_id == 0x597 and len(raw) == 8 and not raw[1] & 0x10:
                self.pending["cycle_off_seen"] = True
                self._persist()
                return

    def verify_cycle(self, control, transaction_id):
        if not self.pending or self.pending.get("id") != transaction_id or self.pending["phase"] != "awaiting-contact-cycle" or not self.pending.get("cycle_off_seen"):
            raise ValueError("Contact UIT is nog niet via CAN waargenomen.")
        self._identity(control, self.pending["identity"])
        control.guard()
        if control.state() != 5 or control.level() != 0:
            raise ValueError("Operational/uitgelogde toestand niet bevestigd.")
        wanted = "before" if self.pending.get("restored") else "raw"
        for row in self.pending["rows"]:
            if control.read(row) != row[wanted]:
                raise ValueError("Controle na contactcyclus wijkt af: " + row["address"])
        self._identity(control, self.pending["identity"])
        control.guard()
        self.pending["phase"] = "verified-after-contact-cycle"
        self._persist()
        save_json(self.directory / "vehicle-transactions" / (transaction_id + ".json"), self.pending)
        result = self.status()
        self.path.unlink()
        self.pending = None
        return result
