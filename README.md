# Twizy Pit Pro — archief

Deze map is sinds 12 oktober 2026 een **archief**, geen werkende app. De actieve bron en de startbare app staan in `D:\downloads\TwizyPitPro`:

- Pc: **0.4.9-preview** — start met `Start.ps1 -LocalOnly` in die map, daarna `http://127.0.0.1:8765`.
- Android: **0.4.33** — `D:\downloads\TwizyPitPro\releases\android\TwizyPitPro-0.4.33.apk`.

`Start.ps1` in deze map verwijst alleen door naar die locatie.

## Wat hier nog staat

- De volledige 0.4.1-bron en -historie in `.git` (HEAD `1fbdb58`). De working tree is opgeruimd; alles is met `git checkout` of vanaf GitHub te herstellen.
- `unieke-wijzigingen/`: kopieen van de versleutelde voertuigopslag (`VehicleStore`, `Vault`, `VehicleWriter`) en de strengere netwerkcontrole. Deze bestanden zijn byte-identiek aan Git HEAD; ze zijn alleen uniek ten opzichte van de actieve locatie, die een andere `JournalStore` gebruikt.
- `openrlink-multicar/`: het zusterproject OpenRLink met eigen Git (1.7.0-preview).
- `data/`: demo-sessie, scans en gebeurtenissen van 11 oktober 2026.
- De APK's `OpenRLink-1.5.0-preview.apk` en `OpenRLink-1.6.0-preview.apk` met hun SHA-256.

## Wat hier niet meer staat

De Python-app, Android-bron, web-GUI, firmware-bron, tests en build-tools zijn verwijderd. Ze staan in de Git-historie, in `D:\downloads\TwizyPitPro` of zijn opnieuw te downloaden. Gebruik deze map niet als zelfstandige app.
