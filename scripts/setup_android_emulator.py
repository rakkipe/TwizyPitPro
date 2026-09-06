from pathlib import Path
import hashlib,json,urllib.request,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];TOOLS=ROOT/'android-tools';SDK=TOOLS/'sdk'
def get_package(repo_url,path,target):
    repo=ET.fromstring(urllib.request.urlopen(repo_url).read())
    package=next(x for x in repo if x.tag.endswith('remotePackage') and x.get('path')==path)
    archive=next(x for x in package.findall('./archives/archive') if x.findtext('host-os') in (None,'windows'))
    url=archive.findtext('./complete/url');url=url if url.startswith('https:') else repo_url.rsplit('/',1)[0]+'/'+url
    checksum=archive.find('./complete/checksum');dest=TOOLS/(path.replace(';','-')+'.zip')
    if not dest.exists():
        print('Download emulator:',path,flush=True)
        with urllib.request.urlopen(url,timeout=120) as incoming,dest.open('wb') as out:
            while block:=incoming.read(1024*1024):out.write(block)
    if hashlib.new(checksum.get('type','sha1'),dest.read_bytes()).hexdigest()!=checksum.text:raise RuntimeError('Checksum mismatch')
    if not target.exists():
        stage=TOOLS/('unpack-'+path.replace(';','-'));stage.mkdir(exist_ok=True)
        with zipfile.ZipFile(dest) as z:z.extractall(stage)
        folder=next(p for p in stage.iterdir() if p.is_dir());target.parent.mkdir(parents=True,exist_ok=True);folder.rename(target)
    print('Ready:',path,flush=True)
get_package('https://dl.google.com/android/repository/repository2-3.xml','emulator',SDK/'emulator')
get_package('https://dl.google.com/android/repository/sys-img/android/sys-img2-3.xml','system-images;android-30;default;x86_64',SDK/'system-images/android-30/default/x86_64')
avd=TOOLS/'avd/PitQA.avd';avd.mkdir(parents=True,exist_ok=True)
(avd.parent/'PitQA.ini').write_text('avd.ini.encoding=UTF-8\npath='+str(avd)+'\ntarget=android-30\n')
(avd/'config.ini').write_text('''avd.ini.encoding=UTF-8
abi.type=x86_64
hw.cpu.arch=x86_64
hw.cpu.ncore=2
hw.ramSize=2048
hw.lcd.width=432
hw.lcd.height=960
hw.lcd.density=160
hw.keyboard=yes
hw.mainKeys=no
hw.gpu.enabled=yes
hw.gpu.mode=swiftshader_indirect
hw.gps=yes
hw.battery=yes
hw.audioInput=no
hw.camera.back=none
hw.camera.front=none
image.sysdir.1=system-images/android-30/default/x86_64/
disk.dataPartition.size=2048M
tag.id=default
PlayStore.enabled=false
showDeviceFrame=no
''')
print('Emulator configured.',flush=True)
