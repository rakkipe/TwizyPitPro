"""Passive Twizy frame decoding, based on OVMS rt_can.cpp (MIT, M. Balzer).

Only values present in this capture are returned. A capture is not a CAN guard
or permission to write. Invalid flags/sentinels invalidate their values.
"""


def decode_frames(frames):
    out={"source":"live-can", "frame_count":0}
    latest={can_id:bytes(data) for can_id,data in frames if type(can_id) is int and 0<=can_id<=0x7ff and len(data)==8}
    out["frame_count"]=len(latest)
    for can_id,b in latest.items():
        if can_id==0x155 and b[3]==0x54:
            soc=int.from_bytes(b[4:6],"big");current=((b[1]&15)<<8)|b[2]
            if 0<soc<=40000:out["soc"]=(soc>>2)/100
            if 0<current<0xf00:out["current"]=(2000-current)/4
        elif can_id==0x599:
            speed=int.from_bytes(b[6:8],"big")
            if speed!=65535:out["speed"]=speed/100
        elif can_id==0x55f and b[5]!=255:
            v1=(b[5]<<4)|(b[6]>>4);v2=((b[6]&15)<<8)|b[7]
            if v1 not in (0,4095) and v2 not in (0,4095):out["voltage"]=((v1+v2+1)>>1)/64
        elif can_id==0x597:
            out.update(key_on=bool(b[1]&16),charging=bool(b[1]&32),transition=bool(b[1]&64))
        elif can_id==0x59b:
            out.update(gear={0:"N",0x80:"D",8:"R"}.get(b[0],"unknown"),go=bool(b[1]&8),footbrake=bool(b[1]&1),throttle_raw=b[3])
        elif can_id==0x554:
            temps=[v-40 for v in b if 0<v<240]
            if temps:out["battery_temp"]=max(temps)
    if "voltage" in out and "current" in out:out["power"]=out["voltage"]*out["current"]/1000
    return out
