"""Owner consent for laptop mutations; no reusable unlocked browser session."""
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import threading
import time

from .service import atomic_json


class OwnerRequired(ValueError):
    pass


class OwnerGuard:
    def __init__(self, directory, clock=time.time):
        self.path = Path(directory) / "security" / "owner.json"
        self.lock = threading.RLock()
        self.clock = clock
        self.record = None
        if self.path.exists():
            record = json.loads(self.path.read_text(encoding="utf-8"))
            if (record.get("algorithm") != "pbkdf2-sha256" or record.get("iterations") != 600000
                    or len(bytes.fromhex(record["salt"])) != 32 or len(bytes.fromhex(record["hash"])) != 32):
                raise ValueError("Eigenaarsbeveiliging beschadigd. Bestaand bestand blijft behouden.")
            self.record = record

    def status(self):
        with self.lock:
            return {"configured": self.record is not None, "per_action": True,
                    "retry_after": max(0, int((self.record or {}).get("locked_until", 0) - self.clock()) + 1)
                    if (self.record or {}).get("locked_until", 0) > self.clock() else 0}

    @staticmethod
    def _strength(password):
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise OwnerRequired("Kies een eigenaarswachtwoord van 8–128 tekens.")

    def setup(self, password):
        with self.lock:
            if self.record is not None:
                raise OwnerRequired("Eigenaarsbeveiliging is al ingesteld.")
            self._strength(password)
            salt = secrets.token_bytes(32)
            record = dict(algorithm="pbkdf2-sha256", iterations=600000, salt=salt.hex(),
                          hash=hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000).hex(),
                          failures=0, locked_until=0)
            atomic_json(self.path, record)
            self.record = record

    def require(self, password):
        with self.lock:
            if self.record is None:
                raise OwnerRequired("Stel eerst je eigen wachtwoord in via Beveiliging.")
            if self.record.get("locked_until", 0) > self.clock():
                raise OwnerRequired("Te veel pogingen. Probeer het over enkele minuten opnieuw.")
            if not isinstance(password, str) or not 1 <= len(password) <= 128:
                raise OwnerRequired("Jouw toestemming is vereist voor deze wijziging.")
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(self.record["salt"]), 600000)
            if not hmac.compare_digest(digest, bytes.fromhex(self.record["hash"])):
                self.record["failures"] = self.record.get("failures", 0) + 1
                if self.record["failures"] >= 5:
                    self.record["locked_until"] = self.clock() + 300
                    self.record["failures"] = 0
                atomic_json(self.path, self.record)
                raise OwnerRequired("Eigenaarswachtwoord onjuist; niets gewijzigd.")
            if self.record.get("failures") or self.record.get("locked_until"):
                self.record.update(failures=0, locked_until=0)
                atomic_json(self.path, self.record)

    def change(self, current, new):
        with self.lock:
            self.require(current)
            self._strength(new)
            salt = secrets.token_bytes(32)
            record = dict(algorithm="pbkdf2-sha256", iterations=600000, salt=salt.hex(),
                          hash=hashlib.pbkdf2_hmac("sha256", new.encode(), salt, 600000).hex(),
                          failures=0, locked_until=0)
            atomic_json(self.path, record)
            self.record = record
