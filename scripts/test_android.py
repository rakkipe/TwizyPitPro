from pathlib import Path
import subprocess,urllib.request,os,sys,json
ROOT=Path(__file__).resolve().parents[1];TOOLS=Path(os.environ.get('PIT_ANDROID_TOOLS',str(ROOT/'android-tools')));BUILD=ROOT/'android/build'
sys.path.insert(0,str(ROOT))
from pit.catalog import defaults
from pit.tuning import targets
vectors=[]
for car in ('80','45'):
    for change in ({},{'drive':70,'neutral':15,'brake':20,'ramp_accel':15,'smooth':85},
                   {'speed':90,'warn':100,'torque':130,'current':123,'power_low':139,'power_high':130},
                   {'power_low':139,'power_high':10}, {'speed':6,'warn':10,'torque':10},
                   {'brakelight_on':60,'brakelight_off':40}, {'ramp_start':250,'rampl_decel':0}):
        values=defaults(car);values.update(change)
        rows=targets(values,car,0x842c)
        vectors.append(dict(model=car,values=values,flags=0x842c,expected=[{k:r[k] for k in ('address','width','signed','raw')} for r in rows]))
vector_path=BUILD/'cross-language-vectors.json';vector_path.write_text(json.dumps(vectors),encoding='utf-8')
jdk=next((TOOLS/'jdk').glob('*/bin'));android=TOOLS/'sdk/platforms/android-35/android.jar'
jsonjar=TOOLS/'json-20250517.jar'
if not jsonjar.exists():jsonjar.write_bytes(urllib.request.urlopen('https://repo.maven.apache.org/maven2/org/json/json/20250517/json-20250517.jar').read())
cp=';'.join(str(x) for x in [jsonjar,BUILD/'classes',android])
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(BUILD/'test-classes'),str(ROOT/'android/tests/CoreTests.java'),str(ROOT/'android/tests/TuningTests.java'),str(ROOT/'android/app/src/main/java/be/peter/twizypitpro/Model.java')],check=True)
subprocess.run([str(jdk/'java.exe'),'-cp',str(BUILD/'test-classes')+';'+cp,'be.peter.twizypitpro.CoreTests',str(ROOT/'android/app/src/main/assets/catalog.json')],check=True)
subprocess.run([str(jdk/'java.exe'),'-cp',str(BUILD/'test-classes')+';'+cp,'be.peter.twizypitpro.TuningTests',str(ROOT/'android/app/src/main/assets/catalog.json'),str(vector_path)],check=True)
