"""Download verified portable Android build dependencies from their publishers."""
from pathlib import Path
import hashlib, json, urllib.request, zipfile, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'android-tools'
TOOLS.mkdir(exist_ok=True)
def download(url, name, digest=None, algorithm='sha256'):
    dest = TOOLS / name
    if not dest.exists():
        print('Download:', name, flush=True)
        with urllib.request.urlopen(url, timeout=90) as response, dest.open('wb') as out:
            while block := response.read(1024*1024): out.write(block)
    if digest and hashlib.new(algorithm, dest.read_bytes()).hexdigest().lower() != digest.lower():
        dest.unlink()
        raise RuntimeError('Checksum mismatch: '+name)
    return dest
def extract(archive, directory):
    directory.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z: z.extractall(directory)

release = json.load(urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/adoptium/temurin21-binaries/releases/latest', headers={'User-Agent':'TwizyPitPro-build'})))
asset=next(a for a in release['assets'] if a['name'].startswith('OpenJDK21U-jdk_x64_windows_hotspot_') and a['name'].endswith('.zip'))
checksum=urllib.request.urlopen(asset['browser_download_url']+'.sha256.txt').read().decode().split()[0]
pkg={'link':asset['browser_download_url'],'checksum':checksum}
jdk=download(pkg['link'], 'jdk21.zip', pkg['checksum'])
if not list((TOOLS/'jdk').glob('*/bin/javac.exe')): extract(jdk, TOOLS/'jdk')
repo=ET.fromstring(urllib.request.urlopen('https://dl.google.com/android/repository/repository2-3.xml').read())
manifest={'jdk':{'version':release['tag_name'],'url':pkg['link'],'sha256':pkg['checksum']},'sdk':[]}
for name in ('build-tools;35.0.0','platforms;android-35','platform-tools'):
    package=next(x for x in repo if x.tag.endswith('remotePackage') and x.get('path')==name)
    archive=next(a for a in package.findall('./archives/archive') if a.findtext('host-os') in (None,'windows'))
    url='https://dl.google.com/android/repository/'+archive.findtext('./complete/url')
    check=archive.find('./complete/checksum')
    file=download(url, name.replace(';','-')+'.zip',check.text,check.get('type','sha1'))
    target=TOOLS/'sdk'/name.replace(';','/')
    if not target.exists():
        stage=TOOLS/('unpack-'+name.replace(';','-'))
        extract(file,stage)
        dirs=[p for p in stage.iterdir() if p.is_dir()]
        target.parent.mkdir(parents=True,exist_ok=True)
        dirs[0].rename(target)
    manifest['sdk'].append({'package':name,'url':url,'checksum':check.text})
    lic=package.find('uses-license')
    if lic is not None:
        license_element=next(x for x in repo if x.tag.endswith('license') and x.get('id')==lic.get('ref'))
        (TOOLS/(lic.get('ref')+'.txt')).write_text(license_element.text,encoding='utf-8')
usb=download('https://github.com/mik3y/usb-serial-for-android/archive/refs/tags/v3.10.0.zip','usb-serial-v3.10.0.zip')
if not (TOOLS/'usb-source').exists(): extract(usb,TOOLS/'usb-source')
manifest['usb']={'version':'3.10.0','sha256':hashlib.sha256(usb.read_bytes()).hexdigest()}
(TOOLS/'dependencies.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Android build tools ready.',flush=True)
