"""Bounded Twizy cluster diagnostics, following OVMS rt_obd2.cpp.

No CANopen download, controller login, reset, calibration, or NMT operations.
"""
from .canopen import BusError, parse_elm_frames


class ClusterService:
    def __init__(self, link, audit, device='cluster'):
        if device not in ('cluster','charger'):
            raise BusError('Unsupported diagnostic device')
        self.device = device
        self.txid, self.rxid = (0x743,0x763) if device=='cluster' else (0x792,0x793)
        self.link, self.audit = link, audit

    def configure(self):
        for cmd in ('ATCSM0', f'ATSH{self.txid:03X}', f'ATCRA{self.rxid:03X}', 'ATST64'):
            if 'OK' not in self.link.command(cmd).upper():
                raise BusError('Cluster configuration rejected: '+cmd)

    def request(self, request):
        allowed = (b'\x10\xc0', b'\x21\x13', b'\x21\x80') if self.device == 'cluster' else (b'\x10\xc0', b'\x21\x80', b'\x21\xf2')
        if request not in allowed:
            raise BusError('Alleen ondersteunde Renault-uitlezing toegestaan.')
        tx=(bytes([len(request)])+request).ljust(8,b'\0')
        text=self.link.command(tx.hex().upper(),timeout=2)
        self.audit.append({'request':request.hex(),'response':text})
        frames=[b for cid,b in parse_elm_frames(text) if cid==self.rxid]
        if len(frames)!=1:
            raise BusError('Missing or ambiguous initial cluster reply')
        first=frames[0]
        kind=first[0]>>4
        if kind==0:
            size=first[0]&15
            if not 0<size<=min(7,len(first)-1):
                raise BusError('Malformed single frame')
            payload=first[1:1+size]
        elif kind==1:
            if len(first)!=8:
                raise BusError('Malformed first frame')
            size=((first[0]&15)<<8)|first[1]
            if not 7<size<=256:
                raise BusError('Response exceeds the diagnostic size limit')
            data=bytearray(first[2:])
            text=self.link.command('3000000000000000',timeout=2)
            self.audit.append({'flow_control':'300000','response':text})
            seq=1
            for cid,b in parse_elm_frames(text):
                if cid!=self.rxid:
                    continue
                remaining=size-len(data)
                if remaining<=0 or not b or b[0]!=(0x20|seq) or len(b)<1+min(7,remaining):
                    raise BusError('Missing, extra, or out-of-sequence consecutive frame')
                data.extend(b[1:1+min(7,remaining)])
                seq=(seq+1)&15
            if len(data)!=size:
                raise BusError('Truncated cluster response')
            payload=bytes(data)
        else:
            raise BusError('Unexpected ISO-TP response type')
        if payload.startswith(b'\x7f'):
            raise BusError('Cluster rejected request: '+payload.hex())
        expected=bytes([request[0]+0x40])+request[1:2]
        if not payload.startswith(expected):
            raise BusError('Mismatched diagnostic acknowledgement')
        return payload

    def read_store(self):
        payload=self.request(b'\x21\x13')
        if len(payload)!=112:
            raise BusError('Unexpected DTC store length')
        raw=payload[2:]
        entries=[]
        for offset in range(0,110,11):
            b=raw[offset:offset+11]
            if b[:2]==b'\0\0':
                continue
            entries.append({'slot':offset//11+1,'ecu':b[0],'code':b[1],
                            'present':bool(b[2]&4),'serv_flag':bool(b[2]&16),'raw':b.hex()})
        return {'raw':raw.hex(),'entries':entries}


def read_cluster(link):
    audit = []
    client = ClusterService(link, audit)
    try:
        client.configure()
        client.request(b'\x10\xc0')
        identity = client.request(b'\x21\x80').hex()
        return dict(identity=identity, **client.read_store(), transport=audit)
    finally:
        for command in ('ATSH601', 'ATCRA581', 'ATST32'):
            if 'OK' not in link.command(command).upper():
                raise BusError('SDO-instellingen herstellen mislukt; verbind opnieuw.')
