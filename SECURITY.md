# Beveiliging

Laptop 0.4.0 heeft een gecontroleerde vLinker-schrijfroute, alleen offline getest.
De oorspronkelijke instellingen worden opgeslagen vóór login of schrijven. Elk
plan is kort geldig, eenmalig en gebonden aan een exacte controller en beginsnapshot.
Bij fouten stopt de procedure zonder automatische rollback of reset. M5 en de
Android-app 0.3.0 blijven alleen uitlezen. Foutwissen en ECU-flashen ontbreken.
Er is geen onafhankelijke beveiligingsaudit uitgevoerd.

## Een probleem melden

Gebruik **Security → Report a vulnerability** voor een vertrouwelijke melding. Plaats geen wachtwoorden, privésleutels, sessietokens, VIN's of ruwe voertuiglogs in openbare issues. Beschrijf de appversie, het platform en minimale stappen met fictieve data. Gewone fouten zonder gevoelige gegevens kunnen als issue worden gemeld.

## Beschermingsgrenzen

- Android vraagt per goedgekeurde wijziging toestelcode of biometrie en koppelt de aanvraag aan een Keystore-handtekening. Opgeslagen appdata is versleuteld; exports zijn gewone leesbare bestanden.
- De laptop heeft vanaf 0.3.1 geen appwachtwoord. Bediening vereist een lokale verbinding, geldige Host, dezelfde Origin en een sessiegebonden CSRF-token. Wie toegang heeft tot je Windows-sessie kan de app bedienen; de wifi-viewer blijft alleen lezen. Een beheerder of iemand met toegang tot hetzelfde Windows-account kan de lokale installatie wijzigen.
- De laptopviewer gebruikt een tijdelijke sleutel over HTTP, zonder TLS. Gebruik een vertrouwd lokaal netwerk; publiceer die server niet op internet.
- Openbare broncode kan worden geforkt. Controleer officiële APK's met de gepubliceerde SHA-256 en certificaatvingerafdruk. Een zelfgebouwde fork is geen officieel ondertekende update.
- `android-signing/`, `data/`, `.env` en bouw-/releasebestanden horen niet in Git. De officiële signingsleutel is niet aanwezig in deze repository of de release.

De [Android-handleiding](docs/ANDROID.md) beschrijft de werking en grenzen uitgebreider.
