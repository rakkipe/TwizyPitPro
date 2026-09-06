import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import PropertyMock, patch

from app import Handler, Server
from pit.service import PitService


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        # Upgrades must ignore old password state, including an unreadable record.
        cls.legacy_owner=Path(cls.temp.name)/"security"/"owner.json"
        cls.legacy_owner.parent.mkdir()
        cls.legacy_owner.write_text("obsolete-password-record",encoding="utf-8")
        cls.service=PitService(cls.temp.name)
        cls.server=Server(("127.0.0.1",0),cls.service)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.host=f"127.0.0.1:{cls.server.server_port}"
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
        cls.temp.cleanup()
    def request(self,method,path,body=None,headers=None):
        connection=http.client.HTTPConnection(self.host,timeout=3)
        connection.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers or {})
        response=connection.getresponse();data=response.read();status=response.status
        connection.close();return status,data
    def headers(self):
        return {"Origin":"http://"+self.host,"X-Pit-CSRF":self.server.csrf,"Content-Type":"application/json"}

    def test_local_profile_saved_without_password(self):
        status,data=self.request("POST","/api/profile",{"name":"Local setup","values":self.service.current},self.headers())
        self.assertEqual(status,200,data)
        self.assertTrue(any(profile["name"]=="Local setup" for profile in self.service.profiles()))

    def test_obsolete_password_header_is_ignored(self):
        headers=self.headers();headers["X-Pit-Owner"]="wrong-password"
        before=self.service.running
        status,_=self.request("POST","/api/demo",{"running":not before},headers)
        self.assertEqual(status,200);self.assertEqual(self.service.running,not before)
    def test_password_state_is_unused_and_preserved(self):
        status,data=self.request("GET","/api/security/status")
        self.assertEqual(status,200)
        self.assertEqual(json.loads(data),{"password_required":False,"local_control_only":True})
        self.assertEqual(self.legacy_owner.read_text(encoding="utf-8"),"obsolete-password-record")
    def test_password_setup_and_change_routes_removed(self):
        for path in ("/api/security/setup","/api/security/change"):
            with self.subTest(path=path):
                status,_=self.request("POST",path,{"password":"unused-password"},self.headers())
                self.assertEqual(status,404)
    def test_page_and_bootstrap(self):
        status,data=self.request("GET","/")
        self.assertEqual(status,200);self.assertIn(b"Twizy Pit Pro",data)
        status,data=self.request("GET","/api/bootstrap")
        self.assertEqual(status,200);self.assertTrue(json.loads(data)["local"])
    def test_host_rebinding_rejected(self):
        status,_=self.request("GET","/api/bootstrap",headers={"Host":"attacker.example"})
        self.assertEqual(status,403)
    def test_cross_origin_rejected(self):
        headers=self.headers();headers["Origin"]="https://attacker.example"
        status,_=self.request("POST","/api/demo",{"running":True},headers)
        self.assertEqual(status,403)
    def test_missing_token_rejected(self):
        headers=self.headers();headers.pop("X-Pit-CSRF")
        status,_=self.request("POST","/api/demo",{"running":True},headers)
        self.assertEqual(status,403)
    def test_raw_live_write_endpoint_absent(self):
        status,_=self.request("POST","/api/write",{"index":0x2920,"value":1000},self.headers())
        self.assertEqual(status,404)
    def test_nonobject_request_rejected(self):
        status,_=self.request("POST","/api/demo",[],self.headers())
        self.assertEqual(status,400)
    def test_authorized_demo_operation(self):
        status,_=self.request("POST","/api/demo",{"running":True},self.headers())
        self.assertEqual(status,200)
        status,data=self.request("GET","/api/state")
        self.assertTrue(json.loads(data)["running"])
    def test_static_path_traversal(self):
        status,_=self.request("GET","/../app.py")
        self.assertEqual(status,404)
    def test_remote_viewer_requires_token(self):
        with patch.object(Handler,"local",new_callable=PropertyMock,return_value=False):
            status,_=self.request("GET","/api/state")
            self.assertEqual(status,401)
    def test_remote_viewer_read_hides_csrf(self):
        self.server.lan=True
        try:
            with patch.object(Handler,"local",new_callable=PropertyMock,return_value=False):
                status,data=self.request("GET","/api/bootstrap",headers={"X-Pit-Viewer":self.server.viewer_token})
                self.assertEqual(status,200)
                self.assertIsNone(json.loads(data)["csrf"])
        finally:
            self.server.lan=False
    def test_remote_mutation_rejected_even_with_tokens(self):
        headers=self.headers();headers["X-Pit-Viewer"]=self.server.viewer_token
        with patch.object(Handler,"local",new_callable=PropertyMock,return_value=False):
            status,_=self.request("POST","/api/demo",{"running":True},headers)
            self.assertEqual(status,403)


if __name__ == "__main__":
    unittest.main()
