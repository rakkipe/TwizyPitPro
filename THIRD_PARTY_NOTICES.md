# Onderdelen van derden

De MIT-licentie in de hoofdmap geldt voor het nieuwe Twizy Pit Pro-applicatiewerk. De onderstaande notices blijven afzonderlijk van toepassing.

| Onderdeel | Gebruik | Licentie / notice |
|---|---|---|
| [OVMS Renault Twizy](https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3/tree/master/vehicle/OVMS.V3/components/vehicle_renaulttwizy) | Twee lokale C++-referenties en onderbouwing van controller-/tuningmodellen; geen volledige OVMS-distributie | Michael Balzer en vermelde bijdragers, MIT; [originele notice](reference/OVMS-LICENSE), notices ook in de C++-bestanden en APK-assets |
| [USB Serial for Android 3.10.0](https://github.com/mik3y/usb-serial-for-android/tree/v3.10.0) | USB-drivers, tijdens de Android-build opgehaald en in de APK gecompileerd | Mike Wakerly en bijdragers, MIT; [originele notice](android/app/src/main/assets/USB-SERIAL-LICENSE.txt), opgenomen in de APK |
| [pySerial 3.5](https://github.com/pyserial/pyserial/tree/v3.5) | Python-runtimeafhankelijkheid, geïnstalleerd via pip | BSD-3-Clause; upstream-distributie bevat de licentie |

Java, Android SDK, AndroidX-annotaties, JSON-testbibliotheek en ESP32/M5-bouwafhankelijkheden worden niet als toolchain met deze repository verspreid. Hun eigen uitgeversvoorwaarden en notices blijven gelden. Zie de [bouwregistratie](docs/android-build-dependencies.json) en de setup-/buildscripts voor gebruikte versies en downloadbronnen.

Het eigen appicoon is gegenereerd voor dit project; de prompt en herkomst staan in [BRONNEN.md](docs/BRONNEN.md#origineel-appicoon). Er is geen Renault-beeldmerk overgenomen. Productnamen identificeren de beoogde apparatuur en vormen geen claim van officiële ondersteuning.
