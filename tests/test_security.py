import tempfile
import unittest
from pathlib import Path
from pit.security import OwnerGuard, OwnerRequired

class OwnerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=1000;self.guard=OwnerGuard(self.temp.name,clock=lambda:self.now)
    def test_unprovisioned_is_locked(self):
        with self.assertRaises(OwnerRequired):self.guard.require("anything")
    def test_hash_salted_and_no_plaintext(self):
        self.guard.setup("my-own-secret-pass")
        self.assertNotIn("my-own-secret-pass",self.guard.path.read_text())
        self.guard.require("my-own-secret-pass")
        with self.assertRaises(OwnerRequired):self.guard.require("")
    def test_cannot_setup_twice_or_weak_password(self):
        with self.assertRaises(OwnerRequired):self.guard.setup("1234")
        self.guard.setup("my-own-secret-pass")
        with self.assertRaises(OwnerRequired):self.guard.setup("takeover-password")
    def test_lockout_persists_restart(self):
        self.guard.setup("my-own-secret-pass")
        for _ in range(5):
            with self.assertRaises(OwnerRequired):self.guard.require("wrong-password")
        restarted=OwnerGuard(self.temp.name,clock=lambda:self.now)
        with self.assertRaises(OwnerRequired):restarted.require("my-own-secret-pass")
        self.now+=301;restarted.require("my-own-secret-pass")
    def test_password_change_requires_old_password(self):
        self.guard.setup("my-own-secret-pass")
        with self.assertRaises(OwnerRequired):self.guard.change("wrong-password","new-secret-pass")
        self.guard.change("my-own-secret-pass","new-secret-pass")
        with self.assertRaises(OwnerRequired):self.guard.require("my-own-secret-pass")
        self.guard.require("new-secret-pass")
    def test_corrupt_state_fails_closed(self):
        self.guard.path.parent.mkdir(parents=True)
        self.guard.path.write_text('{"algorithm":"none"}')
        with self.assertRaises(ValueError):OwnerGuard(self.temp.name)

if __name__=='__main__':unittest.main()
