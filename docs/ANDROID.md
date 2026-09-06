# Twizy Pit Pro voor Android — 0.3.0

Een native Android-app, met eigen Java-schermen, offline simulator, versleutelde
opslag en USB-hostondersteuning. De APK bevat de app zelf en start zonder laptop
of internet. Minimum: **Android 11 / API 30**. Getest in een Android 11-emulator;
de Nothing/CMF-telefoon en de voertuigadapters zijn nog niet fysiek getest.

## Installeren

1. Download `TwizyPitPro-0.3.0.apk` bij de [officiële release](https://github.com/rakkipe/TwizyPitPro/releases/tag/v0.3.0)
   en kopieer hem naar je telefoon, bijvoorbeeld via USB.
2. Open de APK in Bestanden. Geef die bestandsapp desgevraagd toestemming om
   apps uit deze bron te installeren en kies Installeren.
3. Open **Twizy Pit Pro**. De app begint met een zelfstandige demo.
4. Stel een privé-toestelcode of biometrie in als je telefoon nog niet vergrendeld
   is. Zonder toestelvergrendeling blijft elke opgeslagen wijziging geblokkeerd.

Via wifi kan het ook: open de telefoonviewerlink uit **Hardware** in de
laptop-app. Plaats de release-APK eerst in `releases/android/` van de laptop-app.
De knop **Android APK ↓** haalt deze APK dan op via de lokale laptop.
De laptop moet bereikbaar zijn op hetzelfde vertrouwde netwerk. Er worden geen
firewallregels automatisch gewijzigd.

Nieuw in 0.3: registerdoelen en scanvergelijking voor alle 43 velden / 75 registers, automatische editorselectie op USB-identiteit en passieve CAN-uitlezing. Zie [de actuele status](STATUS-0.3.md).

## Functies

- Native pitdashboard, synthetische telemetrie en een grafiek.
- 43 ontwerpinstellingen met numerieke invoer, schuifregelaars, zoeken,
  toelichting, grens- en afhankelijkheidscontrole.
- Vier schema's: Twizy 45/80 × 0712.0001/0712.0002. Onbekende combinaties,
  afwijkende dictionaryrevisies en 0712.0003+ krijgen geen demo-toepassing.
- Wijzigingen vergelijken, eigenaarsgoedkeuring, demo-snapshot, gesimuleerde
  read-back, herstel en een expliciete demo-contactcyclus.
- Versleutelde profielen, JSON-import en -export met model-/versiecontrole.
- Sessies met telemetrie, handmatige rondemarkeringen, CSV- en JSON-export.
  Maximaal 12 bewaarde sessies en 3600 metingen per opname. Opname stopt bij
  verlaten van de app; bewaar een openstaande opname voordat je de app sluit.
- GPS-snelheid, nauwkeurigheid en GPS-punten in een sessie, met expliciete
  locatiepermissie. GPS staat apart van CAN-gegevens. Geen automatische rondedetectie.
- USB-C/OTG met vLinker FS of de meegeleverde M5 PitBridge READONLY-firmware.
  USB-toestemming wordt gevraagd. FTDI/CP210x/CH34x/CDC/Prolific-drivers zijn ingebouwd.
- CANopen-identiteit, model-/firmwareherkenning, getypeerde registers,
  foutregister/-historie, toerental, temperaturen en beschikbare 12V-uitlezing.
  Onbekende velden blijven onbekend. Dit is geen volledige Renault DTC-scanner.
- Kijktoegang tot de laptop via de tijdelijke telefoonviewerlink.
- Instellingen voor scherm aanhouden, trilsignalen, GPS en foutscenario's.
- Eigen adaptief appicoon, goedkeuringslogboek en exports via Android Bestanden.

## Jouw toestemming

Opslaan, toepassen, verwijderen, instellingen wijzigen, een verbinding openen en
gegevens exporteren vragen telkens Android-biometrie of de toestelcode. De
bevestiging is gekoppeld aan één onveranderlijke aanvraag en een willekeurige
nonce. Een Android Keystore-sleutel ondertekent die aanvraag na authenticatie.
De app controleert die handtekening vóór de opslagtransactie. Goedkeuring verloopt
na 120 seconden; er is geen blijvende ontgrendeling en geen universele app-pincode.

Een schuifregelaar bewerkt alleen een nog niet opgeslagen ontwerp. Een gestarte
sessie geeft toestemming voor die opname en handmatige rondemarkeringen. Bewaren
vraagt opnieuw bevestiging. Lezen en door de schermen navigeren vereisen geen code.

De kluis gebruikt AES-256-GCM met een niet-exporteerbare Android Keystore-sleutel,
atomaire bestandsvervanging en controle van de authenticatietag. Een onleesbare of
gewijzigde kluis wordt niet stilzwijgend vervangen. Cloudback-up, overdracht van
appgegevens, debugging en schermopnamen zijn uitgeschakeld in de aflever-APK.
Een handmatig geëxporteerd JSON-/CSV-bestand is leesbaar op de gekozen bestemming.

Iedereen die jouw toestelcode kent of geregistreerde biometrie op die telefoon
heeft, kan Android-bevestiging geven. Gebruik daarom je eigen privévergrendeling.
Dit is geen garantie tegen een geroot toestel, beheerderstoegang, iemand met jouw
ontgrendelde Windows-account of iemand die de app/telefoon volledig wist.

## APK en updates

De release is persoonlijk ondertekend. Android weigert een vervangende update
met een andere certificaatsleutel. De app bevat geen automatische updater en
geen route om externe programmacode te laden. Updates zijn nieuwe APK-bestanden
die je zelf installeert.

Certificaat SHA-256:
`96ddf18ee42c411d08f65712b3407c6bb0c825ccc8e6ceae15bbec7de3225574`

Een eigen signingsleutel staat lokaal in `android-signing/`, met Windows-gebruikers-
ACL en een DPAPI-beveiligd wachtwoord. Deze map gaat **niet** mee in Git, APK
of exports. De officiële sleutel wordt niet gepubliceerd; een eigen build gebruikt
een eigen certificaat en kan de officiële APK niet als update vervangen.
Bewaar de sleutel veilig voor toekomstige eigen updates; verlies ervan
betekent dat een compatibele update niet meer met dezelfde identiteit kan worden
ondertekend. Een nieuwe Windows-installatie kan de DPAPI-kopie onbruikbaar maken.

## Laptopbeveiliging

De laptopversie vraagt een eigen wachtwoord (8–128 tekens) dat jij bij eerste
gebruik instelt via **Beveiliging**. Zonder ingesteld wachtwoord zijn mutaties
geblokkeerd. Elke actie vereist opnieuw dat wachtwoord; vergelijken en reeds
toegestane rondemarkeringen zijn geen wijziging van een afstelling. De server
controleert dit zelf; het is geen cosmetische blokkering in de browser.

PBKDF2-HMAC-SHA256, 600.000 iteraties, willekeurig salt en constante-tijdvergelijking.
Na vijf verkeerde pogingen volgt vijf minuten blokkering, ook na een serverherstart.
Wachtwoorden worden niet in logboeken of browseropslag opgeslagen. Wijzig je
wachtwoord via **Beveiliging** met je huidige wachtwoord. De telefoonviewer blijft
alleen lezen en kan de laptop niet ontgrendelen.

De laptopviewer gebruikt HTTP met een tijdelijke kijktoegangssleutel. Gebruik
uitsluitend je eigen hotspot of vertrouwd wifi; verkeer is daar niet met TLS
versleuteld. De native app weigert publieke adressen, redirects en URL-inloggegevens.

## Grenzen

**Live voertuigtuning en firmwareflash ontbreken.** Er bestaat geen USB-/CAN-
schrijfroute die met een verborgen instelling kan worden vrijgegeven. De editor
is geen bewijs dat een race-afstelling thermisch of mechanisch veilig is. De
simulator voorspelt geen prestaties. Een echte voertuigkwalificatie vraagt een
verse scan en bench-/voertuigtests per exacte controller- en firmwarecombinatie.

GPS, echte USB-/CAN-communicatie, echte biometrische sensoren en bediening op jouw
telefoon zijn niet getest. De emulator test de echte Android-toestelcodeflow en
Keystore, maar bewijst niet dat jouw telefoon een hardware-backed sleutel gebruikt.

## Broncode en opnieuw bouwen

`android/app/src/main/` bevat de native app. `scripts/setup_android.py` haalt de
portable bouwtools op; `android/Build.ps1` maakt de ondertekende APK. Java, SDK en
USB-versies worden geregistreerd in `android-tools/dependencies.json`.
`scripts/test_android.py` test de model- en protocolkern met gesimuleerde antwoorden.
Een aparte QA-build kan screenshots toelaten; die wordt nooit afgeleverd als release.

Primaire bronnen:

- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)
- [Android BiometricPrompt](https://developer.android.com/reference/android/hardware/biometrics/BiometricPrompt)
- [APK-ondertekening](https://developer.android.com/studio/publish/app-signing)
- [USB Serial for Android 3.10.0](https://github.com/mik3y/usb-serial-for-android/tree/v3.10.0)
- [OVMS Twizy-referentie](https://docs.openvehicles.com/en/latest/components/vehicle_renaulttwizy/docs/index.html)

MIT-licenties van USB Serial en OVMS zijn ook in de APK-assets opgenomen.
