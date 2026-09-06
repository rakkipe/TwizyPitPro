"""Negative signing test against the dedicated emulator only."""
from pathlib import Path
import os,subprocess,zipfile,shutil,json
ROOT=Path(__file__).resolve().parents[1];TOOLS=ROOT/'android-tools';BUILD=ROOT/'android/build'
jdk=next((TOOLS/'jdk').glob('*/bin'));bt=TOOLS/'sdk/build-tools/35.0.0';adb=TOOLS/'sdk/platform-tools/adb.exe'
os.environ['ANDROID_SDK_HOME']=str(TOOLS/'user')
apk=ROOT/'releases/android/TwizyPitPro-0.2.0.apk'
tampered=BUILD/'tampered-test.apk';shutil.copy2(apk,tampered)
with zipfile.ZipFile(tampered,'a') as z:z.writestr('assets/unauthorized-test.txt','signature integrity test')
verify=subprocess.run([str(jdk/'java.exe'),'-jar',str(bt/'lib/apksigner.jar'),'verify',str(tampered)],capture_output=True,text=True)
assert verify.returncode!=0,'Tampered APK must fail verification'
keystore=BUILD/'qa-other-signer.p12'
if not keystore.exists():subprocess.run([str(jdk/'keytool.exe'),'-genkeypair','-keystore',str(keystore),'-alias','test','-keyalg','RSA','-keysize','2048','-validity','30','-dname','CN=TestOnlyOtherSigner','-storepass','qa-test-only-123','-keypass','qa-test-only-123'],check=True,capture_output=True)
other=BUILD/'other-signer-test.apk'
subprocess.run([str(jdk/'java.exe'),'-jar',str(bt/'lib/apksigner.jar'),'sign','--ks',str(keystore),'--ks-key-alias','test','--ks-pass','pass:qa-test-only-123','--key-pass','pass:qa-test-only-123','--v4-signing-enabled','false','--out',str(other),str(apk)],check=True)
installed=subprocess.run([str(adb),'-s','emulator-5580','install','-r',str(other)],capture_output=True,text=True)
assert 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' in installed.stdout+installed.stderr,installed.stdout+installed.stderr
result={'modified_apk_rejected':True,'other_certificate_update_rejected':True,'emulator':'emulator-5580'}
(ROOT/'output/android-signing-tests.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
