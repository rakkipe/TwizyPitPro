"""Standalone Android SDK build. No global installation and no embedded signing secret."""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, urllib.request, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
TOOLS=pathlib.Path(os.environ.get('PIT_ANDROID_TOOLS', str(ROOT/'android-tools')))
ANDROID=ROOT/'android'
SRC=ANDROID/'app/src/main'
BUILD=ANDROID/'build'
DIST=ROOT/'releases/android'
def run(args,**kwargs):
    print('Build:',pathlib.Path(str(args[0])).name,flush=True)
    subprocess.run([str(a) for a in args],check=True,**kwargs)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unsigned',action='store_true');parser.add_argument('--qa',action='store_true');args=parser.parse_args()
    BUILD.mkdir(parents=True,exist_ok=True);DIST.mkdir(parents=True,exist_ok=True)
    jdk=next((TOOLS/'jdk').glob('*/bin')).parent
    sdk=TOOLS/'sdk';bt=sdk/'build-tools/35.0.0';android=sdk/'platforms/android-35/android.jar'
    annotation=TOOLS/'annotation-1.7.1.jar'
    if not annotation.exists():
        annotation.write_bytes(urllib.request.urlopen('https://dl.google.com/dl/android/maven2/androidx/annotation/annotation-jvm/1.7.1/annotation-jvm-1.7.1.jar').read())
    usb=TOOLS/'usb-source/usb-serial-for-android-3.10.0/usbSerialForAndroid/src/main/java'
    # Equivalent generated BuildConfig for the unmodified USB driver's release source.
    generated=BUILD/'generated';(generated/'com/hoho/android/usbserial').mkdir(parents=True,exist_ok=True)
    (generated/'com/hoho/android/usbserial/BuildConfig.java').write_text('package com.hoho.android.usbserial; public final class BuildConfig { public static final boolean DEBUG=false; }',encoding='utf-8')
    for folder in ('classes','dex','compiled'): (BUILD/folder).mkdir(exist_ok=True)
    compiled=BUILD/'resources.zip'
    run([bt/'aapt2.exe','compile','--dir',SRC/'res','-o',compiled])
    manifest=SRC/'AndroidManifest.xml'
    if args.qa:
        manifest=BUILD/'qa-manifest.xml'
        manifest.write_text((SRC/'AndroidManifest.xml').read_text().replace('android:debuggable="false"','android:debuggable="true"'),encoding='utf-8')
    run([bt/'aapt2.exe','link','-o',BUILD/'resources.apk','-I',android,'--manifest',manifest,'--java',generated,'--auto-add-overlay','-A',SRC/'assets',compiled])
    files=list((SRC/'java').rglob('*.java'))+list(usb.rglob('*.java'))+list(generated.rglob('*.java'))
    if args.qa:
        # QA runs the exact same security logic; only screenshot protection is off in this separate artifact.
        qa=BUILD/'qa-src/MainActivity.java';qa.parent.mkdir(exist_ok=True)
        main=SRC/'java/be/peter/twizypitpro/MainActivity.java'
        qa.write_text(main.read_text(encoding='utf-8').replace('getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);','/* QA screenshot capture only */'),encoding='utf-8')
        files=[qa if f==main else f for f in files]
    argfile=BUILD/'javac-args.txt'
    javac=['-encoding','UTF-8','-source','11','-target','11','-classpath',str(android)+';'+str(annotation),'-d',str(BUILD/'classes')]+[str(f) for f in files]
    argfile.write_text('\n'.join('"'+s.replace('\\','/')+'"' for s in javac),encoding='utf-8')
    run([jdk/'bin/javac.exe','@'+str(argfile)])
    run([jdk/'bin/jar.exe','--create','--file',BUILD/'classes.jar','-C',BUILD/'classes','.'])
    run([jdk/'bin/java.exe','-cp',bt/'lib/d8.jar','com.android.tools.r8.D8','--release','--min-api','30','--lib',android,'--classpath',annotation,'--output',BUILD/'dex',BUILD/'classes.jar'])
    unsigned=BUILD/'unsigned.apk';shutil.copy2(BUILD/'resources.apk',unsigned)
    with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as archive:
        for dex in (BUILD/'dex').glob('*.dex'):archive.write(dex,dex.name)
    aligned=BUILD/'aligned.apk';run([bt/'zipalign.exe','-f','4',unsigned,aligned])
    if args.unsigned:return
    signing=ROOT/'android-signing';keystore=signing/'owner-release.p12'
    if not keystore.exists():raise RuntimeError('Run Initialize-AndroidSigning.ps1 before signing.')
    if 'PIT_SIGNING_PASSWORD' not in os.environ:raise RuntimeError('Signing password must be supplied in environment by the owner wrapper.')
    out=DIST/('TwizyPitPro-QA-DO-NOT-DISTRIBUTE.apk' if args.qa else 'TwizyPitPro-0.3.0.apk')
    run([jdk/'bin/java.exe','-jar',bt/'lib/apksigner.jar','sign','--ks',keystore,'--ks-key-alias','twizypit-owner','--ks-pass','env:PIT_SIGNING_PASSWORD','--key-pass','env:PIT_SIGNING_PASSWORD','--v4-signing-enabled','false','--out',out,aligned])
    check=subprocess.check_output([str(jdk/'bin/java.exe'),'-jar',str(bt/'lib/apksigner.jar'),'verify','--verbose','--print-certs',str(out)],text=True)
    (DIST/(out.stem+'-signature.txt')).write_text(check,encoding='utf-8')
    (DIST/(out.name+'.sha256')).write_text(hashlib.sha256(out.read_bytes()).hexdigest()+'  '+out.name+'\n',encoding='ascii')
    print(check);print('APK:',out,flush=True)
if __name__=='__main__':main()
