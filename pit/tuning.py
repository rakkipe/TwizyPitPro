"""Complete register target compiler; no bus writes.

Adapted from Michael Balzer's OVMS rt_sevcon_tuning.cpp (2017), MIT.
The original notice is retained in reference/rt_sevcon_tuning.cpp.
Only the standard 45/80 drivetrain and default OVMS breakdown calculation
are modeled. A target set is not a qualified or ordered live transaction.
"""
from .catalog import defaults, parameters, scale, sdo_candidates, validate


CONFIG = {
    "80": dict(kph=80, rpm=7250, reverse=900, offsets=(400, 800, 1250), warn=89,
               warnrpm=8050, hysteresis=550, torque=55000, rated=57000, delta=0,
               current=450000, stator=450, boost=540, low=12182, high=13000,
               motorpower=4608, fmap=(964,9728,1122,9984), extended=(1122,10089,2240,11901),
               pmap=(880,0,880,2115,659,2700,608,3000,516,3500,421,4500,360,5500,307,6500,273,7250),
               mapspeed=(3000,3500,4500,6000)),
    "45": dict(kph=45, rpm=5814, reverse=1307, offsets=(686,1386,2686), warn=56,
               warnrpm=7200, hysteresis=900, torque=32500, rated=33000, delta=500,
               current=270000, stator=290, boost=330, low=7050, high=7650,
               motorpower=2688, fmap=(480,8192,576,8960), extended=(656,9600,1328,11901),
               pmap=(520,0,520,2050,437,2500,363,3000,314,3500,279,4000,247,4500,226,5000,195,6000),
               mapspeed=(4357,5083,6535,8714)),
}


def _trunc_div(value, divisor):
    return (abs(value) // divisor) * (-1 if value < 0 else 1)


def targets(values, model, control_flags=None):
    """Map all 43 fields, including dependent limits, PMAP/FMAP and masked flags.

    Missing control_flags stays unresolved: never substitute a factory value
    for a read-modify-write register. Rows describe targets, not execution order.
    """
    if model not in CONFIG:
        raise ValueError("Onbekende aandrijflijn; geen registervertaling.")
    v, c = validate(values, model), CONFIG[model]
    rows = []
    def add(index, sub, raw, keys, width=2, signed=False, **extra):
        if raw is not None and not (-(1 << (width*8-1)) if signed else 0) <= raw < (1 << (width*8-(1 if signed else 0))):
            raise ValueError(f"{index:04X}:{sub:02X}: berekende waarde past niet in datatype.")
        rows.append(dict(index=index, sub=sub, address=f"{index:04X}:{sub:02X}",
                         width=width, signed=signed, raw=raw, keys=list(keys), key=" / ".join(keys), **extra))
    for r in sdo_candidates(v, model):
        add(r["index"], r["sub"], r["raw"], [r["key"]], r["width"], r["address"] == "290A:03")
    rpm = scale(c["rpm"], c["kph"], v["speed"], 400, 65535)
    warning = scale(c["warnrpm"], c["warn"], v["warn"], 400, 65535)
    # Some editor ranges were broad enough to underflow this subtraction.
    if warning < c["hysteresis"]:
        raise ValueError("Waarschuwingssnelheid te laag voor de hysterese van dit model.")
    add(0x3813, 0x34, warning, ["warn"])
    add(0x3813, 0x3c, warning-c["hysteresis"], ["warn"])
    add(0x2920, 5, rpm, ["speed"])
    add(0x2920, 6, min(rpm, c["reverse"]), ["speed"])
    for sub, offset in zip((0x33,0x35,0x3b,0x2d), (*c["offsets"], c["offsets"][2]+1500)):
        add(0x3813, sub, rpm+offset, ["speed"])
    add(0x4624, 0, rpm+c["offsets"][2]+2500, ["speed"])
    add(0x4641, 2, scale(c["stator"],100,v["current"],0,c["boost"]), ["current"])
    add(0x6075, 0, scale(c["current"],100,v["current"],0,c["boost"]*1000), ["current"], 4)
    torque = scale(c["torque"],100,v["torque"],10000,200000)
    low = scale(c["low"],100,v["power_low"],500,200000)
    high = scale(c["high"],100,v["power_high"],500,200000)
    add(0x6076,0,torque+c["delta"],["torque"],4)
    add(0x2916,1,c["rated"] if v["torque"]==100 else torque+c["delta"],["torque"],4)
    add(0x3813,0x23,c["motorpower"] if v["power_low"]==v["power_high"]==100 else int(max(low,high)*.353),["power_low","power_high"],signed=True)
    powerkeys = ["speed","torque","power_low","power_high","current"]
    if (rpm,torque,low,high)==(c["rpm"],c["torque"],c["low"],c["high"]):
        pmap, fmap = c["pmap"], c["fmap"]
    else:
        rpm2 = min(low*9549//torque,rpm)
        # Default OVMS disables custom breakdown parameters. For the bounded
        # editor domain region 3 must remain above the requested maximum RPM.
        rpm3 = 1000/9.549*10000*10000*(v["current"]/100)/high
        if rpm3 < rpm or rpm2 <= 0:
            raise ValueError("Vermogenskaart vereist een nog niet ondersteunde breakdown-configuratie.")
        trq = (torque*16+500)//1000
        fmap = c["extended"] if trq > c["fmap"][2] else c["fmap"]
        pmap = [trq,0]
        drpm, dpwr = (rpm-rpm2)//21, _trunc_div(high-low,21)
        for fib in (0,1,2,3,5,8,13,21):
            point_rpm, point_power = rpm2+fib*drpm, low+fib*dpwr
            point_torque = (((point_power*9549+(point_rpm>>1))//point_rpm)*16+500)//1000
            pmap.extend((point_torque,point_rpm))
    for sub, raw in enumerate(pmap,1): add(0x4611,sub,raw,powerkeys)
    for sub, raw in enumerate(fmap,0x0f): add(0x4610,sub,raw,powerkeys)
    for letter, base in (("D",0x24),("N",0x1b),("B",7)):
        for n, (refspeed, kph) in enumerate(zip(c["mapspeed"],(33,39,50,66)),1):
            speedkey, levelkey = f"{letter}_speed{n}", f"{letter}_level{n}"
            add(0x3813,base+2*(n-1),scale(32767,100,v[levelkey],0,32767),[levelkey], map=letter, point=n, component="level")
            add(0x3813,base+2*(n-1)+1,scale(refspeed,kph,v[speedkey],0,65535),[speedkey], map=letter, point=n, component="speed")
    # Strict editor ordering alone does not ensure ordering after per-point scaling.
    for letter in "DNB":
        speeds=[r["raw"] for r in rows if r.get("map")==letter and r.get("component")=="speed"]
        if any(a>=b for a,b in zip(speeds,speeds[1:])):
            raise ValueError(f"Koppelkaart {letter}: omgerekende toerentalpunten lopen niet strikt op.")
    add(0x3813,5,scale(1024,100,v["brakelight_off"],64,1024),["brakelight_off"])
    add(0x3813,6,scale(1024,100,v["brakelight_on"],64,1024),["brakelight_on"])
    enabled = v["brakelight_on"]!=100 or v["brakelight_off"]!=100
    if control_flags is not None and (type(control_flags) is not int or not 0<=control_flags<=65535):
        raise ValueError("Ongeldige uitgelezen control flags.")
    flags = None if control_flags is None else (control_flags|0x2000 if enabled else control_flags&~0x2000)
    add(0x2910,1,flags,["brakelight_on","brakelight_off"],mask=0x2000,set_bits=0x2000 if enabled else 0)
    return rows


def register_inventory(model):
    return [{k:v for k,v in row.items() if k not in ("raw","set_bits")} for row in targets(defaults(model),model)]


def compare_snapshot(values, model, registers):
    """Bind a target set to an actually read snapshot; don't guess unread values."""
    by_address={r["address"]:r for r in registers if r.get("source")=="live" and r.get("raw") is not None and not r.get("error")}
    control=by_address.get("2910:01",{})
    flags=control.get("raw") if control.get("width")==2 else None
    result=[]
    for row in targets(values,model,flags):
        old=by_address.get(row["address"])
        row=dict(row, before=old["raw"] if old and old.get("width")==row["width"] else None)
        row["verified_width"]=bool(old and old.get("width")==row["width"])
        row["changed"]=row["before"] is None or row["raw"]!=row["before"]
        result.append(row)
    return result


def map_update_order(before, after):
    """Find an order that preserves strictly increasing RPM points at every step."""
    if len(before)!=4 or len(after)!=4 or any(a>=b for seq in (before,after) for a,b in zip(seq,seq[1:])):
        raise ValueError("Ongeldige koppelkaart; geen veilige updatevolgorde.")
    current=list(before);todo={i for i in range(4) if before[i]!=after[i]};order=[]
    while todo:
        candidates=[i for i in sorted(todo) if (i==0 or current[i-1]<after[i]) and (i==3 or after[i]<current[i+1])]
        if not candidates: raise ValueError("Geen begrensde kaartupdatevolgorde gevonden.")
        i=candidates[0];current[i]=after[i];todo.remove(i);order.append(i)
    return order
