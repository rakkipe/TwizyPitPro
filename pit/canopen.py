"""Bounded CANopen upload client. No download, NMT or clear-fault command exists."""
import re
import time


class BusError(RuntimeError):
    pass


class Abort(BusError):
    def __init__(self, index, sub, code):
        self.code = code
        super().__init__(f"SDO {index:04X}:{sub:02X} geweigerd: 0x{code:08X}")


def parse_elm_frames(text):
    frames = []
    for line in text.replace("\r", "\n").replace(">", "").splitlines():
        line = line.strip()
        if not re.fullmatch(r"[0-9A-Fa-f ]+", line):
            continue
        compact = line.replace(" ", "")
        if len(compact) < 5:
            continue
        can_id = int(compact[:3], 16)
        body = compact[3:]
        if len(body) % 2:  # optional one-nibble DLC
            dlc = int(body[0], 16)
            body = body[1:]
            if dlc > 8 or len(body) != dlc * 2:
                continue
        if can_id > 0x7FF or not 0 < len(body) <= 16:
            continue
        frames.append((can_id, bytes.fromhex(body)))
    return frames


class ElmLink:
    name = "vLinker FS / ELM"

    def __init__(self, port, baud=115200):
        self.port, self.baud = port, baud
        self.ser = None

    def command(self, value, timeout=1.5):
        if self.ser is None:
            raise BusError("Adapter niet verbonden.")
        self.ser.reset_input_buffer()
        self.ser.write((value + "\r").encode("ascii"))
        self.ser.flush()
        deadline = time.monotonic() + timeout
        data = bytearray()
        while time.monotonic() < deadline:
            chunk = self.ser.read(self.ser.in_waiting or 1)
            data.extend(chunk)
            if len(data) > 32768:
                raise BusError("Adapterantwoord te groot.")
            if b">" in chunk:
                return data.decode("ascii", errors="replace")
        raise BusError(f"Geen adapterprompt na {value[:10]}; verbinding verbroken of bus stil.")

    def open(self):
        import serial
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.05, write_timeout=1)
            self.command("ATZ", 3)
            for command in ("ATE0", "ATL0", "ATS1", "ATH1", "ATSP6", "ATCAF0", "ATCFC0", "ATD0", "ATV1", "ATSH601", "ATCRA581"):
                if "OK" not in self.command(command).upper():
                    raise BusError(f"Adapter ondersteunt {command} niet.")
            identity = self.command("ATI")
            if not any(x in identity.upper() for x in ("ELM", "STN", "VLINKER", "OBDLINK")):
                raise BusError("Geen ondersteunde ELM-adapter herkend.")
            protocol = self.command("ATDPN").replace(">", "").strip()
            if protocol not in ("6", "A6"):
                raise BusError("CAN-protocol is niet 11-bit / 500 kbit/s.")
            self.name = identity.replace(">", "").strip()
        except Exception:
            self.close()
            raise

    def exchange(self, payload, matcher):
        if len(payload) != 8 or payload[0] not in (0x40, 0x60, 0x70):
            raise BusError("Alleen SDO-upload toegestaan.")
        response = self.command(payload.hex().upper())
        for can_id, data in parse_elm_frames(response):
            if can_id == 0x581 and len(data) == 8 and matcher(data):
                return data
        raise BusError("Geen passend SDO-antwoord; index/subindex en CAN-ID gecontroleerd.")

    def voltage(self):
        response = self.command("ATRV")
        match = re.search(r"\b(\d{1,2}\.\d{1,2})V\b", response, re.I)
        return float(match[1]) if match else None

    def _monitor(self, duration):
        self.ser.reset_input_buffer()
        self.ser.write(b"ATMA\r")
        deadline = time.monotonic() + duration
        data = bytearray()
        prompted = False
        try:
            while time.monotonic() < deadline:
                chunk = self.ser.read(self.ser.in_waiting or 1)
                data.extend(chunk)
                if len(data) > 65536: raise BusError("CAN-monitorbuffer te groot.")
                if b">" in chunk:
                    prompted = True
                    break
        finally:
            if not prompted:
                self.ser.write(b"\r")
                stop = time.monotonic()+1.5
                while time.monotonic()<stop:
                    chunk=self.ser.read(self.ser.in_waiting or 1)
                    data.extend(chunk)
                    if len(data)>98304: raise BusError("CAN-monitor stopt niet binnen de bufferlimiet.")
                    if b">" in chunk:
                        prompted=True
                        break
                if not prompted: raise BusError("CAN-monitor kon niet worden gestopt.")
        text=data.decode("ascii",errors="replace")
        if any(error in text.upper() for error in ("BUFFER FULL","CAN ERROR","BUS ERROR","BUS OFF","?")):
            raise BusError("Adapter meldt een CAN-monitorfout; opname verworpen.")
        return parse_elm_frames(text)

    def capture(self):
        """Bounded, filtered listen-only capture; restore SDO receive filter."""
        try:
            for command in ("ATCSM1","ATCM700","ATCF500"):
                if "OK" not in self.command(command).upper(): raise BusError(f"Monitorconfiguratie {command} geweigerd.")
            frames=self._monitor(1.15)
            if "OK" not in self.command("ATCRA155").upper(): raise BusError("BMS-filter geweigerd.")
            frames.extend(self._monitor(.15))
            return frames
        finally:
            if "OK" not in self.command("ATCRA581").upper():
                raise BusError("SDO-filter herstellen mislukt; verbind opnieuw.")

    def close(self):
        if self.ser:
            self.ser.close()
        self.ser = None


class M5Link:
    name = "M5StickC Plus2 · PitBridge"
    def __init__(self, port, baud=115200):
        self.port, self.baud, self.ser = port, baud, None

    def open(self):
        import serial
        # Optional features belong to this connection, not a previous firmware.
        self.capture_supported = True
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.05, write_timeout=1)
            time.sleep(1.5)
            self.ser.reset_input_buffer()
            self.ser.write(b"HELLO\n")
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self.ser.readline().strip() == b"PITBRIDGE 1 READONLY":
                    return
            raise BusError("PitBridge 1 READONLY niet gevonden; gebruik de meegeleverde firmware.")
        except Exception:
            self.close()
            raise

    def exchange(self, payload, matcher):
        if len(payload) != 8 or payload[0] not in (0x40, 0x60, 0x70):
            raise BusError("Alleen SDO-upload toegestaan.")
        self.ser.reset_input_buffer()
        self.ser.write(b"READ " + payload.hex().upper().encode() + b"\n")
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            line = self.ser.readline().decode("ascii", errors="replace").strip()
            if line.startswith("ERR"):
                raise BusError(line)
            if line.startswith("RX "):
                for can_id, data in parse_elm_frames(line[3:]):
                    if can_id == 0x581 and len(data) == 8 and matcher(data):
                        return data
        raise BusError("M5: geen passend SDO-antwoord.")

    def voltage(self):
        return None

    def capture(self):
        if getattr(self,"capture_supported",True) is False: return []
        self.ser.reset_input_buffer()
        self.ser.write(b"CAPTURE\n")
        deadline=time.monotonic()+2.5
        frames=[]
        count=0
        while time.monotonic()<deadline:
            line=self.ser.readline().decode("ascii",errors="replace").strip()
            count+=len(line)
            if count>8192: raise BusError("PitBridge-capture te groot.")
            if line=="CAPTURE END": return frames
            if line in ("ERR FORMAT","ERR UPLOAD_ONLY"):
                self.capture_supported=False
                return []
            if line.startswith("ERR"): raise BusError(line)
            if line.startswith("FRAME "): frames.extend(parse_elm_frames(line[6:]))
        raise BusError("PitBridge-capture niet afgerond.")

    def close(self):
        if self.ser:
            self.ser.close()
        self.ser = None


class SDO:
    def __init__(self, link):
        self.link = link

    def upload(self, index, sub=0, max_bytes=256):
        header = index.to_bytes(2, "little") + bytes([sub])
        def initial(data):
            return data[1:4] == header and (data[0] == 0x80 or data[0] & 0xE0 == 0x40)
        response = self.link.exchange(b"\x40" + header + bytes(4), initial)
        if len(response)!=8 or not initial(response): raise BusError("Ongeldig SDO-initantwoord.")
        def abort(data):
            if data[0] == 0x80:
                raise Abort(index, sub, int.from_bytes(data[4:8], "little"))
        abort(response)
        command = response[0]
        if command & 2:
            count = 4 - ((command >> 2) & 3) if command & 1 else 4
            return response[4:4+count]
        expected = int.from_bytes(response[4:], "little") if command & 1 else None
        if expected is not None and expected > max_bytes:
            raise BusError("SDO-object overschrijdt leeslimiet.")
        result, toggle = bytearray(), 0
        for _ in range(max_bytes // 7 + 2):
            def segment_match(data):
                return (data[0] == 0x80 and data[1:4] == header) or data[0] & 0xE0 == 0
            segment = self.link.exchange(bytes([0x60 | toggle << 4]) + bytes(7), segment_match)
            if len(segment)!=8 or not segment_match(segment): raise BusError("Ongeldig SDO-segmentantwoord.")
            abort(segment)
            if (segment[0] >> 4) & 1 != toggle:
                raise BusError("SDO segment-toggle fout.")
            last, unused = segment[0] & 1, (segment[0] >> 1) & 7
            if not last and unused:
                raise BusError("Ongeldige tussensegmentlengte.")
            result.extend(segment[1:8-unused if last else 8])
            if len(result) > max_bytes:
                raise BusError("SDO-object te lang.")
            if last:
                if expected is not None and len(result) != expected:
                    raise BusError("SDO-lengte wijkt af van aangekondigde lengte.")
                return bytes(result)
            toggle ^= 1
        raise BusError("SDO-segmenten niet afgerond.")

    def number(self, index, sub=0, width=4, signed=False):
        raw = self.upload(index, sub)
        if len(raw) != width:
            raise BusError(f"{index:04X}:{sub:02X}: {len(raw)} bytes, verwacht {width}.")
        return int.from_bytes(raw, "little", signed=signed)

    def identity(self):
        data, errors = {}, []
        for name, index in (("name", 0x1008), ("hardware", 0x1009), ("software", 0x100A)):
            try:
                raw = self.upload(index)
                # Hardware version may be a binary integer on some controllers.
                data[name] = raw.rstrip(b"\0").decode("ascii") if all(x == 0 or 32 <= x < 127 for x in raw) else "0x"+raw[::-1].hex().upper()
            except (BusError, UnicodeError) as exc:
                errors.append(str(exc))
        for sub, name in enumerate(("vendor", "product", "revision", "serial"), 1):
            try:
                data[name] = self.number(0x1018, sub)
            except BusError as exc:
                errors.append(str(exc))
        if not data:
            raise BusError("Geen controlleridentiteit uitgelezen. " + "; ".join(errors[:2]))
        data["errors"] = errors
        return data
