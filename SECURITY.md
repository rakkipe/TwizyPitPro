# Beveiliging

Laptop 0.4.1-preview gebruikt een gecontroleerde vLinker-schrijfroute. Een aparte toegangssessie wordt naar schijf geflusht vóór level-4-login. Een volledige beginsnapshot en tuningbackup worden bewaard vóór configuratiemodus of tuningwijzigingen. Elk plan is kort geldig, eenmalig en gebonden aan de controller en beginwaarden. Niet-geselecteerde registers blijven behouden.

Bij onbekende schrijfuitkomst stopt de procedure zonder automatische rollback of reset. Actieve Renault-clustermeldingen blokkeren nieuwe tuning. Android 0.3.1 en M5 blijven alleen uitlezen. Foutwissen en ECU-flashen ontbreken in de GUI. Er is geen onafhankelijke beveiligingsaudit of volledige fysieke tuningvalidatie uitgevoerd.

## Een probleem melden

Gebruik **Security → Report a vulnerability** voor een vertrouwelijke melding. Plaats geen wachtwoorden, privésleutels, sessietokens, VIN's of ruwe voertuiglogs in openbare issues. Beschrijf de appversie, het platform en minimale stappen met fictieve data. Gewone fouten zonder gevoelige gegevens kunnen als issue worden gemeld.

## Beschermingsgrenzen

- Android vraagt per goedgekeurde wijziging toestelcode of biometrie en koppelt de aanvraag aan een Keystore-handtekening. Opgeslagen appdata is versleuteld; exports zijn gewone leesbare bestanden.
- De laptop heeft vanaf 0.3.1 geen appwachtwoord. Bediening vereist een lokale verbinding, geldige Host, dezelfde Origin en een sessiegebonden CSRF-token. Wie toegang heeft tot je Windows-sessie kan de app bedienen; de wifi-viewer blijft alleen lezen. Een beheerder of iemand met toegang tot hetzelfde Windows-account kan de lokale installatie wijzigen.
- De laptopviewer gebruikt een tijdelijke sleutel over HTTP, zonder TLS. Gebruik een vertrouwd lokaal netwerk; publiceer die server niet op internet.
- Openbare broncode kan worden geforkt. Controleer officiële APK's met de gepubliceerde SHA-256 en certificaatvingerafdruk. Een zelfgebouwde fork is geen officieel ondertekende update.
- `android-signing/`, `data/`, `.env` en bouw-/releasebestanden horen niet in Git. De officiële signingsleutel is niet aanwezig in deze repository of de release.

De [Android-handleiding](docs/ANDROID.md) beschrijft de werking en grenzen uitgebreider.
