from pathlib import Path
import subprocess,urllib.request
ROOT=Path(__file__).resolve().parents[1];TOOLS=ROOT/'android-tools';BUILD=ROOT/'android/build'
jdk=next((TOOLS/'jdk').glob('*/bin'));android=TOOLS/'sdk/platforms/android-35/android.jar'
jsonjar=TOOLS/'json-20250517.jar'
if not jsonjar.exists():jsonjar.write_bytes(urllib.request.urlopen('https://repo.maven.apache.org/maven2/org/json/json/20250517/json-20250517.jar').read())
cp=';'.join(str(x) for x in [jsonjar,BUILD/'classes',android])
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(BUILD/'test-classes'),str(ROOT/'android/tests/CoreTests.java'),str(ROOT/'android/app/src/main/java/be/peter/twizypitpro/Model.java')],check=True)
subprocess.run([str(jdk/'java.exe'),'-cp',str(BUILD/'test-classes')+';'+cp,'be.peter.twizypitpro.CoreTests',str(ROOT/'android/app/src/main/assets/catalog.json')],check=True)
