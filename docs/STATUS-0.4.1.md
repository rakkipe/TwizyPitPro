# Laptop 0.4.1-preview en Android 0.3.1

De laptop opent nu tijdelijke SEVCON level-4-toegang voordat beschermde instellingen worden gelezen. In 0.4.0 werd de beginsnapshot bij level 0 gelezen: dat faalde op de aangesloten controller. Ook de nacontrole na een contactcyclus en de herstelprocedure gebruiken nu een eigen toegangssessie.

## Gebruik via vLinker FS

1. Verbind via Hardware met de aanwezige USB-adapter. Zet contact aan, N, GO uit, gas los en haal de laadstekker uit het stopcontact.
2. Kies in Tuning **75 instellingen uitlezen**. De app journaliseert de toegang, logt in, bewaart de 75 getypeerde waarden en controleert het uitloggen. Er wordt hierbij geen tuning, NMT of kaartcommit uitgevoerd.
3. Bewerk de gewenste velden. Bewerkte velden worden geselecteerd; via de selectie kun je ook een referentiewaarde bewust kiezen. Snelheid, koppel, stroom en beide vermogensdoelen moeten samen worden geselecteerd, omdat zij dezelfde vermogenskaart bepalen. Beide remlichtdrempels vormen ook een set. Controleer alle doelen in zo'n set.
4. Los actieve storingen op, bevestig de mechanische uitvoering en houd de voetrem ingedrukt tijdens de schrijfprocedure. Kies **Schrijfplan voorbereiden** en controleer de echte oude en nieuwe registerwaarden. Niet-geselecteerde registers behouden hun uitgelezen waarde.
5. Bevestig het concrete plan. De app controleert de beginsnapshot opnieuw en bewaart de tuningbackup voordat configuratiemodus of tuningregisters worden gewijzigd. Iedere write vereist een geldige ACK en read-back.
6. Laat de adapter aangesloten, zet contact uit tot de app de UIT-overgang via CAN ziet, zet weer aan, N en rem, en kies **Na contactcyclus controleren**.

## Storingen en herstel

De vLinker-route leest de eerste tien Renault-clusterfoutslots. Actieve meldingen blokkeren nieuwe tuningplannen en toepassing, ook als het SERV-vakje is aangevinkt. Een ECU/code wordt getoond zonder een onbewezen DF-vertaling of oorzaak te verzinnen. Dit is geen volledige Renault-scan van alle ECU's.

Een onderbroken toegangssessie wordt apart opgeslagen. **Toegangssessie afsluiten** controleert identiteit, stilstand en toegang opnieuw. Bij een open tuningtransactie gebruik je het herstelplan. Bij onbekende schrijfuitkomst volgen geen automatische herhaling, rollback of ECU-reset. Het toegangjournaal is geen backup van voertuigconfiguratie: de volledige tuningbackup wordt afzonderlijk opgeslagen vóór NMT of parameterwijzigingen.

## Correcties en controles

- Accuspanning uit CAN 55F gebruikt 0,1 V per eenheid, overeenkomstig OVMS `rt_battmon.cpp`, in laptop en Android.
- CAN 59B accepteert voor N de bekende waarden 00 en 20. D=80, R=08; overige waarden blijven onbekend en blokkeren schrijven. De decoder accepteert niet willekeurig elke andere waarde als N.
- 123 Python-tests geslaagd: inclusief beschermde registers, alle vier ondersteunde model/firmware-combinaties, sessiejournalen, verloren login-ACK, uitloggen, herstel, behoud van niet-geselecteerde registers, actieve Renault-fout en ISO-TP met telleromloop.
- 26 Android-kerncontroles geslaagd; APK 0.3.1 bevat de CAN-weergavecorrecties. De zelfstandige Android- en M5-schrijfroute zijn nog niet geïmplementeerd.
- Op een echte Twizy 80 / 0712.0001 zijn level 4 en alle 75 registerlezingen bevestigd. De twee logincommando's moeten aansluitend verstuurd worden, binnen de bestaande veiligheidsdeadline. Bij uitloggen kan deze firmware SEVCON-fout 9 geven; alleen wanneer het uitgebreide foutnummer 9 is én niveau 0 vervolgens wordt teruggelezen, geldt uitloggen als bevestigd. Andere fouten of ontbrekende antwoorden blijven blokkeren.
- De aangesloten vLinker heeft identiteit en Renault-foutgeheugen gelezen. Een volledige tuningwijziging en contactcyclus op de echte Twizy zijn nog niet gevalideerd.

## Bronnen

- [OVMS SEVCON-toegang](https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3/blob/master/vehicle/OVMS.V3/components/vehicle_renaulttwizy/src/rt_sevcon.cpp)
- [OVMS packvoltage-eenheid](https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3/blob/master/vehicle/OVMS.V3/components/vehicle_renaulttwizy/src/rt_battmon.cpp)
- [OVMS CAN-status](https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3/blob/master/vehicle/OVMS.V3/components/vehicle_renaulttwizy/src/rt_can.cpp)
- [OVMS Renault-clusterprotocol](https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3/blob/master/vehicle/OVMS.V3/components/vehicle_renaulttwizy/src/rt_obd2.cpp)

Voertuigsnapshots, foutgegevens en toegangs-/tuningjournalen blijven onder lokale `data/`; ze horen niet in de openbare repository.
