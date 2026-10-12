> Android 0.4.0-preview voegt de gecontroleerde vLinker USB-schrijf- en herstelroute toe. M5 en de laptopviewer blijven alleen lezen. Fysieke tuningvalidatie staat nog open.

# Twizy Pit Pro voor Android — 0.4.0-preview

Een native Android-app, met eigen Java-schermen, offline simulator, versleutelde
opslag en USB-hostondersteuning. De APK bevat de app zelf en start zonder laptop
of internet. Minimum: **Android 11 / API 30**. Getest in een Android 11-emulator;
de Nothing/CMF-telefoon en de voertuigadapters zijn nog niet fysiek getest.

## Installeren

1. Download [TwizyPitPro-0.4.0-preview.apk](https://github.com/rakkipe/TwizyPitPro/releases/download/android-v0.4.0-preview/TwizyPitPro-0.4.0-preview.apk) op je telefoon, of kopieer deze uit `releases/android/` via USB. Deze APK gebruikt hetzelfde officiële certificaat als 0.3.1 en kan die installatie bijwerken zonder de app te verwijderen.
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

Nieuw in 0.4.0-preview: 75 beschermde instellingen uitlezen via tijdelijke level-4-toegang, selectie per instelling, een bekeken schrijfplan, getypeerde writes, read-back, echte contactcycluscontrole en expliciet herstel. De eerdere registervertaling en CAN-uitlezing blijven aanwezig.

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
- Voertuigschrijven en herstel via vLinker USB met toestelgoedkeuring per actie, verse CAN-controles, een versleutelde beginsnapshot en duurzame hersteljournalen.
- Kijktoegang tot de laptop via de tijdelijke telefoonviewerlink.
- Instellingen voor scherm aanhouden, trilsignalen, GPS en foutscenario's.
- Eigen adaptief appicoon, goedkeuringslogboek en exports via Android Bestanden.

## Schrijven en herstellen via USB

1. Verbind de vLinker FS via USB-C/OTG en controleer de uitgelezen controlleridentiteit. Ondersteund: Twizy 45/80 met exact 0712.0001/0002 en de bijbehorende revisie. Onbekende combinaties en 0712.0003+ blokkeren schrijven.
2. Zet de Twizy stil, N, GO uit en gas los; houd de rem ingedrukt. Een voeding van 12–15 V is vereist. Los storingen (ook SERV) eerst op. Actieve Renault-clustermeldingen, CANopen-fouten en EMCY blokkeren tuning.
3. Open Tuning en kies **75 instellingen uitlezen**. Toestelgoedkeuring staat één tijdelijke level-4-sessie toe; na de snapshot wordt uitloggen gecontroleerd.
4. Bewerk het ontwerp en kies de te schrijven instellingen. Snelheid, koppel, stroom en beide vermogensdoelen vormen één set; remlichtdrempels horen samen. Niet-geselecteerde registers behouden hun voertuigwaarden. De uiteindelijke snelheid en waarschuwing worden samen gecontroleerd.
5. Bevestig originele motor/reductiekast, opgeloste storingen en zo nodig aangepaste remlichthardware. Bereid het voertuigplan voor, bekijk de echte begin- en doelwaarden en geef daarna afzonderlijk toestelgoedkeuring om dit plan te schrijven. Het plan is eenmalig en maximaal 120 seconden geldig.
6. Na read-back en uitloggen blijft een contactcyclus open. Laat USB aangesloten, zet contact UIT en wacht tot de app dit positief via verse CAN-frames heeft waargenomen. Zet weer AAN, N, GO uit, houd de rem ingedrukt en kies **Na contactcyclus controleren**.
7. Bij een fout wordt niet automatisch teruggeschreven, gereset of opnieuw geprobeerd. De app bewaart de onbekende schrijfuitkomst. Verbind dezelfde controller opnieuw en bekijk een **Herstelplan**. Herstel heeft een eigen hash, vervaltijd en toestelgoedkeuring; gewijzigde beginwaarden vereisen een nieuwe vergelijking. Daarna volgt opnieuw een contactcyclus.

Voor iedere login en configuratiewijziging staat het intentiejournaal al op schijf. Backups en journalen gebruiken AES-256-GCM en AtomicFile met expliciete flush. Een appherstart bewaart de hersteltransactie, maar verwerpt eerdere plannen en eerder waargenomen contact-UIT. Verlaten van de app onderbreekt de actie bij de volgende controle; een nieuwe verbinding geeft geen automatische toestemming om verder te schrijven. Een afzonderlijk onderbroken toegangssessie kan zonder tuning via **Toegangssessie afsluiten** worden afgemeld. Corruptie blijft geblokkeerd voor handmatige inspectie.

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

Laptop 0.4.0 voegt een afzonderlijke vLinker-schrijfprocedure toe; zie
[STATUS-0.4.md](STATUS-0.4.md). Dit verandert de Android-APK niet.

Vanaf laptopversie 0.3.1 is er geen appwachtwoord of wachtwoordvraag per actie.
Bediening is alleen toegestaan via een lokale verbinding met geldige Host,
dezelfde Origin en een sessiegebonden CSRF-token. Wie toegang heeft tot je
Windows-sessie kan de app bedienen. Een bestaand lokaal wachtwoordbestand uit
0.3.0 wordt niet meer gebruikt en blijft behouden bij een update.

De wifi-viewer blijft alleen lezen. De native Android-app blijft voor
wijzigingen de Android-toestelcode of biometrie vragen.

De laptopviewer gebruikt HTTP met een tijdelijke kijktoegangssleutel. Gebruik
uitsluitend je eigen hotspot of vertrouwd wifi; verkeer is daar niet met TLS
versleuteld. De native app weigert publieke adressen, redirects en URL-inloggegevens.

## Grenzen

**Firmwareflash en foutwissen ontbreken. M5 schrijft niet.** De vLinker-schrijfroute is een preview die nog niet op een echte Twizy is gekwalificeerd. De editor
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

Voor de aanvullende vijf opslag-/UI-tests gebruik je een afzonderlijke wegwerpemulator met Android 11+, ingesteld met toestelcode en ontgrendeld. Start die eerst en gebruik het expliciete ADB-serienummer:

```powershell
.\android\TestStorage.ps1 -Serial emulator-5582 -SigningDirectory 'D:\backup\android-signing'
```

Vervang het voorbeeldpad door je eigen sleutelmap. De procedure bouwt de huidige productiebron opnieuw, installeert die APK en een afzonderlijke instrumentatie-APK en controleert echte Android Keystore/AES-GCM, corruptie, AtomicFile, herstel na herstart en automatische veldselectie. De test verandert appgegevens in de emulator en weigert fysieke telefoons. Gebruik daarom een afzonderlijke testemulator. Het wachtwoord wordt alleen tijdelijk door de eigenaarswrapper doorgegeven; de QA-APK wordt nooit gepubliceerd. Resultaat: `android/build/storage-tests/results.txt`.

Primaire bronnen:

- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)
- [Android BiometricPrompt](https://developer.android.com/reference/android/hardware/biometrics/BiometricPrompt)
- [APK-ondertekening](https://developer.android.com/studio/publish/app-signing)
- [USB Serial for Android 3.10.0](https://github.com/mik3y/usb-serial-for-android/tree/v3.10.0)
- [OVMS Twizy-referentie](https://docs.openvehicles.com/en/latest/components/vehicle_renaulttwizy/docs/index.html)

MIT-licenties van USB Serial en OVMS zijn ook in de APK-assets opgenomen.
