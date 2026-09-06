"""Version-aware profile definitions, never vehicle default/qualification claims.

The documented parameter scales below follow Michael Balzer's OVMS Twizy
implementation. See reference/rt_sevcon_tuning.cpp and its MIT copyright notice.
Only a bounded subset is translated to raw SDO candidates. The other parameters
remain macro-level engineering targets; no incomplete write plan is executable.
"""
import hashlib
import json
import math
import re

SOURCE = "https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3/blob/master/vehicle/OVMS.V3/components/vehicle_renaulttwizy/src/rt_sevcon_tuning.cpp"
PRODUCTS = {0x0712302D: "80", 0x0712301B: "45"}
REVISIONS = {"0712.0001": 0x10019, "0712.0002": 0x10021}


def fingerprint(identity):
    keys = ("vendor", "product", "revision", "serial", "software", "hardware")
    return hashlib.sha256(json.dumps({k: identity.get(k) for k in keys}, sort_keys=True).encode()).hexdigest()


def compatibility(identity):
    model = PRODUCTS.get(identity.get("product"))
    software = identity.get("software", "")
    match = re.fullmatch(r"(\d{4})\.(\d{4})", software)
    version = tuple(map(int, match.groups())) if match else None
    locked = version is not None and version >= (712, 3)
    known = bool(model and software in REVISIONS and identity.get("revision") == REVISIONS[software])
    return {
        "model": model, "label": f"Twizy {model}" if model else "Onbekende controller",
        "software": software or "Onbekend", "locked": locked, "known": known,
        "variant": f"T{model}-{software}" if model and known else "diagnostics-only",
        "fingerprint": fingerprint(identity), "live_write": False,
        "status": "Firmware vergrendeld" if locked else "Referentiefamilie herkend" if known else "Onbekende combinatie",
        "reason": "Renault-schrijfbeperking vanaf 0712.0003." if locked else
                  "Live schrijfroute nog niet op deze controller gekwalificeerd." if known else
                  "Geen exact passende model-, firmware- en revisiecombinatie.",
        "model_note": "Controllerfamilie herkend; een verwisselde motor/reductiekast is niet automatisch vast te stellen.",
    }


def parameters(model="80"):
    t45 = model == "45"
    rows = []
    def add(key, name, group, unit, low, high, default, note, mapping="macro"):
        rows.append(dict(key=key, name=name, group=group, unit=unit, min=low, max=high,
                         default=default, step=1, note=note, mapping=mapping))
    add("speed", "Maximumsnelheid", "Vermogen", "km/u", 6, 100 if t45 else 120, 45 if t45 else 80,
        "Circuitdoel. Snelheid, overspeedgrenzen en vermogenskaart vormen één afhankelijke set.")
    add("warn", "Overspeedwaarschuwing", "Vermogen", "km/u", 10, 110 if t45 else 130, 56 if t45 else 89,
        "Beïnvloedt de waarschuwing en vereist controle van alle overspeedgrenzen.")
    add("torque", "Piekmotorkoppel", "Vermogen", "%", 10, 130, 100, "Percentage van de modelreferentie, geen gemeten wielkoppel.")
    add("power_low", "Vermogen lage snelheid", "Vermogen", "%", 10, 139, 100, "Mechanisch doel vóór verliezen; gekoppeld aan de volledige PMAP.")
    add("power_high", "Vermogen hoge snelheid", "Vermogen", "%", 10, 130, 100, "Vermogenskaart en fluxkaart moeten gezamenlijk worden gevalideerd.")
    add("current", "Motorstroomlimiet", "Vermogen", "%", 10, 123, 100, "Motor-/statorstroom; dit is niet de accustroom. Referentie 270 A (45) / 450 A (80).")
    add("drive", "Aandrijfniveau", "Gasrespons", "%", 10, 100, 100, "Schaalt de beschikbare aandrijving.", "sdo")
    add("neutral", "Regeneratie bij gas los", "Regeneratie", "%", 0, 100, 21 if t45 else 18, "Wordt ook begrensd door BMS, SOC en temperatuur.", "sdo")
    add("brake", "Regeneratie bij remmen", "Regeneratie", "%", 0, 100, 21 if t45 else 18, "Aanvullend op de mechanische remmen.", "sdo")
    for key, name, low, val, unit in (
        ("ramp_start", "Starthelling", 1, 30 if t45 else 40, "‰"),
        ("ramp_accel", "Opbouw aandrijfkoppel", 1, 21 if t45 else 25, "%"),
        ("ramp_decel", "Afbouw aandrijfkoppel", 0, 20, "%"),
        ("ramp_neutral", "Opbouw gas-los-regeneratie", 0, 40, "%"),
        ("ramp_brake", "Opbouw remregeneratie", 0, 40, "%"),
        ("rampl_accel", "Toerentalhelling omhoog", 1, 30, "%"),
        ("rampl_decel", "Toerentalhelling omlaag", 0, 30, "%"),
        ("smooth", "Smoothing", 0, 70, "%"),
    ):
        add(key, name, "Gasrespons", unit, low, 250 if key == "ramp_start" else 100, val,
            "OVMS-schaal. Referenties zijn geen voertuigbackup; hogere rampwaarden geven snellere verandering.", "sdo")
    for key, name in (("brakelight_on", "Remlichtdrempel aan"), ("brakelight_off", "Remlichtdrempel uit")):
        add(key, name, "Remlicht", "%", 0, 100, 100,
            "Vereist aangepaste remlichthardware. De standaard Twizy-bedrading ondersteunt dit niet; 100/100 = uit.")
    for letter, group in (("D", "Koppelkaart · drive"), ("N", "Koppelkaart · gas los"), ("B", "Koppelkaart · rem")):
        for i, (speed, level) in enumerate(zip((33, 39, 50, 66), (100, 100, 100, 100) if letter == "D" else (100, 80, 50, 20)), 1):
            add(f"{letter}_speed{i}", f"Punt {i} · snelheid", group, "km/u", 0, 130, speed,
                "Vier oplopende punten. Definitieve registervolgorde hangt af van de uitgelezen kaart.")
            add(f"{letter}_level{i}", f"Punt {i} · koppelniveau", group, "%", 0, 100, level,
                "Percentage van beschikbaar koppel. Kaartbewerking is in deze versie een ontwerpdoel.")
    return rows


def defaults(model="80"):
    return {p["key"]: p["default"] for p in parameters(model)}


def validate(values, model="80"):
    if not isinstance(values, dict):
        raise ValueError("Profiel moet een object zijn.")
    expected = {p["key"] for p in parameters(model)}
    if set(values) != expected:
        raise ValueError("Onvolledig profiel of onbekende instellingen.")
    for p in parameters(model):
        val = values[p["key"]]
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or int(val) != val:
            raise ValueError(f"{p['name']}: gebruik een geheel getal.")
        if not p["min"] <= val <= p["max"]:
            raise ValueError(f"{p['name']}: toegestaan {p['min']}–{p['max']} {p['unit']}.")
    if values["warn"] <= values["speed"]:
        raise ValueError("Overspeedwaarschuwing moet boven de maximumsnelheid liggen.")
    if values["brakelight_on"] < values["brakelight_off"]:
        raise ValueError("Remlicht-aan moet minstens gelijk zijn aan remlicht-uit.")
    for letter in "DNB":
        points = [values[f"{letter}_speed{i}"] for i in range(1, 5)]
        if any(a >= b for a, b in zip(points, points[1:])):
            raise ValueError(f"Koppelkaart {letter}: snelheden moeten strikt oplopen.")
    return {k: int(v) for k, v in values.items()}


def scale(default, base, value, low, high):
    return default if value == base else max(low, min(high, default * value // base))


def sdo_candidates(values, model):
    """Read/engineering candidates only. Widths qualified separately before writes."""
    t45 = model == "45"
    defs = {
        "drive": (0x2920, 1, 2, values["drive"] * 10),
        "neutral": (0x2920, 3, 2, scale(209 if t45 else 182, 21 if t45 else 18, values["neutral"], 0, 1000)),
        "brake": (0x2920, 4, 2, scale(209 if t45 else 182, 21 if t45 else 18, values["brake"], 0, 1000)),
        "ramp_start": (0x291C, 2, 2, scale(300 if t45 else 400, 30 if t45 else 40, values["ramp_start"], 10, 10000)),
        "ramp_accel": (0x2920, 7, 2, scale(2083 if t45 else 2500, 21 if t45 else 25, values["ramp_accel"], 10, 10000)),
        "ramp_decel": (0x2920, 11, 2, scale(2000, 20, values["ramp_decel"], 10, 10000)),
        "ramp_neutral": (0x2920, 13, 2, scale(4000, 40, values["ramp_neutral"], 10, 10000)),
        "ramp_brake": (0x2920, 14, 2, scale(4000, 40, values["ramp_brake"], 10, 10000)),
        "rampl_accel": (0x2920, 15, 2, scale(6000, 30, values["rampl_accel"], 0, 20000)),
        "rampl_decel": (0x2920, 16, 2, scale(6000, 30, values["rampl_decel"], 0, 20000)),
        "smooth": (0x290A, 3, 2, scale(800, 70, values["smooth"], 0, 1000)),
    }
    rows = [dict(key=k, index=i, sub=s, width=w, raw=v, address=f"{i:04X}:{s:02X}") for k, (i, s, w, v) in defs.items()]
    rows.append(dict(key="smooth", index=0x290A, sub=1, width=1, raw=1+values["smooth"]//10, address="290A:01"))
    return rows


def variant_bundle():
    return [dict(model=model, software=software, revision=revision,
                 live_write=False, status="reference-only", parameters=parameters(model))
            for model in ("45", "80") for software, revision in REVISIONS.items()]
