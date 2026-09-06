# Validatie — 6 september 2026

## Laptop 0.3.2

- 74 Python-tests: vijf nieuwe M5-protocoltests, waaronder twaalf gesimuleerde
  Twizy-model-/versiecombinaties via de echte M5Link-, SDO- en serviceroute.
- Basisdiagnose blijft bereikbaar bij onbekende firmware; ontbrekende versie
  blijft onbekend. Afgewezen registers maken een volgende leesaanvraag niet stuk.
- Oude PitBridge 1 zonder CAPTURE blijft uitlezen. Een regressietest toonde aan
  dat CAPTURE na een firmwarewissel ten onrechte uitgeschakeld bleef; opnieuw
  verbinden detecteert die mogelijkheid nu opnieuw.
- Live verbinding gebruikt de uitgelezen identiteit en negeert demo-keuzes.
- Geen M5- of voertuigflash uitgevoerd. M5-firmware en Android-APK zijn voor
  deze laptopwijziging ongewijzigd; fysieke compatibiliteit blijft onbevestigd.

## Laptop 0.3.1

- 69 Python-tests geslaagd, inclusief lokale profielopslag zonder wachtwoord,
  het negeren van oude wachtwoordgegevens en blokkeren van externe bediening,
  ongeldige Origin, ontbrekende CSRF en onbekende schrijfroutes.
- De zes tests voor de verwijderde wachtwoordmodule zijn vervallen; twee
  HTTP-tests zijn aangepast en twee migratie-/routecontroles toegevoegd.
- JavaScript-syntax gecontroleerd met Node.js. In Chromium zijn een demoronde
  gestart en een profiel opgeslagen zonder wachtwoordvenster, met tijdelijke data.
- Android blijft op 0.3.0; de APK en M5-firmware zijn voor deze wijziging niet
  aangepast of opnieuw getest. Live CAN-schrijven blijft afwezig.

## Release 0.3.0

Zie [STATUS-0.3.md](STATUS-0.3.md) voor de nieuwe functies, 73 Python-tests,
26 Android-controles, GUI-validatie en resterende hardware- en schrijfwerkzaamheden.
De onderstaande controles en APK-hash horen specifiek bij de eerdere 0.2.0-release.

## Release 0.2.0: Android en eigenaarsbeveiliging

- 55 Python-tests geslaagd, inclusief server-side eigenaarsgoedkeuring,
  ontbrekend/wrong wachtwoord, weigeren van herprovisioning, wachtwoordwissel en
  een persistente blokkering na vijf foutieve pogingen. JavaScript syntaxcheck geslaagd.
- 19 Android-kerncontroles geslaagd: 43 velden per model, types en afhankelijkheden,
  exacte model/firmware/revisie, SDO-uploadwhitelist, expedited en segmented upload,
  signed waarden, abort/toggle/lengtefouten en blokkering van publieke viewer-URL's.
- Native APK gebouwd met Android SDK 35 en Java 21; minSdk 30, targetSdk 35.
  Persoonlijke RSA-3072-signatuur / APK v3 geverifieerd.
- Geïnstalleerd en gestart in een Android 11/API 30-emulator. Geen AndroidRuntime-
  crash in de gecontroleerde flow. Definitieve APK is niet debuggable (`run-as`
  wordt geweigerd), backup staat uit en FLAG_SECURE is aanwezig in de release.
- Android-eigenaarsflow getest met de echte Android-toestelcodeprompt en Keystore:
  annuleren en verkeerde code schrijven geen kluisbestand; juiste code schrijft
  een versleutelde kluis. Opgeslagen profiel met 75 km/u bleef na force-stop/herstart
  en een ondertekende app-update behouden. Het profiel is opnieuw in de editor geladen.
- Android-vergelijking 80 → 75 km/u, goedkeuring, gesimuleerde toepassing en
  daaropvolgende expliciete demo-contactcyclus doorlopen.
- Wijzigen van de APK-inhoud laat signature-verificatie falen. Een APK met een
  andere certificaatsleutel werd door de emulator geweigerd met
  `INSTALL_FAILED_UPDATE_INCOMPATIBLE`.
- Laptop-GUI via Playwright getest op een geïsoleerde testserver: eigenaar instellen,
  gewijzigde bediening bevestigen en opnieuw een wachtwoordvraag bij de volgende
  handeling. Het testwachtwoord is niet gebruikt voor de gebruiksinstallatie.
- Native screenshots onder `docs/images/`; voor screenshots is uitsluitend
  een afzonderlijke QA-APK zonder schermopnameblokkade gebruikt. Die APK zit niet in
  het afleverpakket. De definitieve APK bevat de blokkade wel.

Nog niet op echte hardware getest: Nothing/CMF-telefoon, biometrische sensor,
USB/OTG-adapters, CAN-bus, GPS en wifi tussen fysieke apparaten. Dit is geen
onafhankelijke beveiligingsaudit of vrijgave voor live voertuigtuning.

## Eerdere basisvalidatie, herhaald waar geraakt

## Uitgevoerd

- **47 oorspronkelijke Python-tests, nu onderdeel van de 55 geslaagde tests** (`unittest discover -s tests -q`).
  Firmware-/product-/revisiematching, typen en grenzen, CAN-ID-/indexmatching,
  segmented SDO incl. toggle/abort/lengtefouten, signed waarden, blokkering van
  download/NMT, verlopen plannen, identiteitwissel, snapshots, rollback,
  herstel na herstart, CSV-herkomst, HTTP Host/Origin/CSRF en telefoonrechten.
- Pythonmodules gecompileerd en JavaScript gecontroleerd met `node --check`.
- Chrome via Playwright: tuningveld 100 → 85, vergelijking, demo-toepassing,
  demo-contactcyclus, profiel opslaan, sessie starten, handmatige rondemarkering,
  sessie stoppen en diagnose uitvoeren.
- Twizy 45 / 0712.0003 in de GUI: toepasknop blijft geblokkeerd.
- Desktopweergave 1440 × 1050 en responsive telefoonweergave 390 × 844.
  Dashboard en diagnose: documentbreedte 390 bij viewport 390, geen horizontale
  pagina-overloop. Geen browserfouten of waarschuwingen in de gecontroleerde flow.
- Eigen icoon als ongewijzigde PNG en ICO met 16/24/32/48/64/128/256-pixelsubbeelden.
- **PitBridge succesvol gecompileerd**: esp32:esp32:m5stack_stickc_plus2,
  ESP32-core 3.3.10, M5Unified 0.2.18, M5GFX 0.2.25.
  Sketch 503259 bytes (15%), globale variabelen 26264 bytes (8%).

## Grenzen van dit resultaat

Alle tests zijn offline; geen echte COM-poort geopend. Geen firmware geüpload.
Een compilerbuild en een mockprotocoltest zijn geen bewijs van werking aan een
echte Twizy. Live tuningschrijven ontbreekt bewust in deze release.
De responsieve browserweergave is getest, niet de echte telefoon/wifiverbinding.
De demo gebruikt synthetische data en fictieve identifiers.

De oorspronkelijke laptop-screenshots zijn lokaal bewaard en maken geen deel uit
van deze repository. De openbare broncode wordt vastgelegd door de Git-commit en
releasetag; bouwafhankelijkheden staan in `android-build-dependencies.json`.

SHA-256 van de officiële `TwizyPitPro-0.2.0.apk`:
`39d7e56bb54e08e7a6d4d1c1802b8e9808d07d8f90e93a06f92567048f4e8d0a`.
Het bijbehorende checksum- en ondertekeningsbestand worden als release-assets
gepubliceerd. Een andere eigen signingsleutel levert een andere APK-hash op.
