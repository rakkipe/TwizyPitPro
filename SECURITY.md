# Beveiliging

Versie 0.2.0 is een preview voor demo en uitlezen. Er is geen live tuning- of flashroute en er is geen onafhankelijke beveiligingsaudit uitgevoerd.

## Een probleem melden

Gebruik **Security → Report a vulnerability** voor een vertrouwelijke melding. Plaats geen wachtwoorden, privésleutels, sessietokens, VIN's of ruwe voertuiglogs in openbare issues. Beschrijf de appversie, het platform en minimale stappen met fictieve data. Gewone fouten zonder gevoelige gegevens kunnen als issue worden gemeld.

## Beschermingsgrenzen

- Android vraagt per goedgekeurde wijziging toestelcode of biometrie en koppelt de aanvraag aan een Keystore-handtekening. Opgeslagen appdata is versleuteld; exports zijn gewone leesbare bestanden.
- De laptop vraagt per wijziging het eigenaarswachtwoord en controleert dat op de server. Een beheerder of iemand met toegang tot hetzelfde Windows-account kan de lokale installatie wijzigen.
- De laptopviewer gebruikt een tijdelijke sleutel over HTTP, zonder TLS. Gebruik een vertrouwd lokaal netwerk; publiceer die server niet op internet.
- Openbare broncode kan worden geforkt. Controleer officiële APK's met de gepubliceerde SHA-256 en certificaatvingerafdruk. Een zelfgebouwde fork is geen officieel ondertekende update.
- `android-signing/`, `data/`, `.env` en bouw-/releasebestanden horen niet in Git. De officiële signingsleutel is niet aanwezig in deze repository of de release.

De [Android-handleiding](docs/ANDROID.md) beschrijft de werking en grenzen uitgebreider.
