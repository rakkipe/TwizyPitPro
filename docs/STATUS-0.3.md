# Stand van zaken — 0.3.0

Deze versie breidt de echte uitleescode en registerberekeningen uit. **Het is nog geen volledig werkende voertuigtuner.** Er is geen voertuig aangesloten bij ontwikkeling en validatie van deze release. Registerdoelen worden niet naar een echte controller geschreven.

## Toegevoegd

- Alle 43 ontwerpvelden hebben een vertaling naar in totaal **75 getypeerde registers**, inclusief snelheidsgrenzen, stroom/koppel, PMAP, FMAP, D/N/B-kaarten en remlichtflags.
- De volledige leesinventaris wordt op een exact herkende controller opgevraagd. Alleen geslaagde uitlezingen gelden als beginwaarde; verkeerde registerbreedtes en ontbrekende antwoorden blijven zichtbaar als fout.
- De Android-editor kiest model en firmware uit de actuele USB-identiteit. Een onbekende controller krijgt geen aangenomen Twizy-model.
- Beide GUI's tonen en exporteren de registerdoelen. De laptop koppelt de vergelijking aan de controllerfingerprint; Android gebruikt uitsluitend het rapport van de huidige controller en passende model-/firmwarecombinatie.
- Het remlichtregister gebruikt een bitmasker: andere control bits blijven behouden. Zonder geslaagde uitlezing blijft het doel onbekend. Aangepaste remlichthardware blijft noodzakelijk.
- Passieve CAN-decoders voor voertuigsnelheid, SOC, accustroom, accuspanning, berekend elektrisch vermogen, moduletemperaturen en voertuigstatus. Onbekende of ongeldige waarden worden niet door simulatie vervangen.
- vLinker/ELM wisselt tijdelijk naar gefilterde stille monitoring, stopt de opname begrensd en herstelt het SDO-filter. De M5 krijgt een nieuw `CAPTURE`-commando in listen-only. Oudere PitBridge-firmware houdt alleen SDO-uitlezing.
- Strengere controle van de SDO-antwoordlengte en index/subindex, ook als een transport verkeerde data teruggeeft.

## Gecontroleerd

- 73 Python-tests en 26 Android/JVM-tests geslaagd.
- Python en Java leveren dezelfde 75 registerdoelen voor 14 volledige testprofielen. De tests omvatten afzonderlijke gepubliceerde referentiewaarden, datatypes, onbekende beginwaarden en control-bitbehoud.
- De kaartvolgordeplanner behoudt de puntvolgorde bij 4.900 combinaties. Dit is een softwaretest; er is nog geen uitvoerende voertuigtransactie.
- Browser: 75 unieke registeradressen zichtbaar in de dialoog; geen consolefouten in de gecontroleerde flow.
- Android: getekende APK 0.3.0 als update geïnstalleerd op de Android 11-emulator; native dialoog met 75 registers geopend; niet debuggable. Het officiële certificaat blijft hetzelfde.
- APK-integriteit: gewijzigde inhoud wordt afgewezen; een update met een andere sleutel wordt door Android geweigerd.
- PitBridge gecompileerd voor `esp32:esp32:m5stack_stickc_plus2`: 503999 bytes programma (15%) en 26264 bytes globale data (8%), met ESP32-core 3.3.10, M5Unified 0.2.18 en M5GFX 0.2.25. Geen firmware geflasht.

## Wat nog ontbreekt voor volledige voertuigtuning

1. Een verse uitleestest met de fysieke vLinker FS en Twizy; controle van exacte identiteit, firmware, registerbreedtes en ontvangen CAN-frames. De oorspronkelijke motoraandrijving/reductiekast en eventuele BMS-vervanging moeten bekend zijn.
2. Kwalificatie en implementatie van de uitvoerende schrijftransactie: eigenaarsgoedkeuring voor één vast plan, backup, login en pre-op, verse fysieke/CAN-controles, afhankelijke schrijfvolgorde, read-back, write-only kaartcommit, persistent hersteljournaal en hercontrole na een echte contactcyclus.
3. Bench- en voertuigtests van onderbrekingen, onverwachte antwoorden, verkeerde identiteit, fouten tijdens schrijven en herstel. Geen automatische rollback over een onbekende of onveilige bus.
4. USB/OTG en biometrie op de fysieke Android-telefoon, GPS buiten en de M5 met de werkelijke CAN Unit.

Firmware 0712.0003 en hoger heeft volgens de Twizy/OVMS-bronnen schrijfbeperkingen. Deze release heft die niet op. Een softwareversie herkennen is geen nieuwe ECU-firmware genereren. ECU-flashen en een volledige Renault DTC-scan voor alle modules zijn niet geïmplementeerd.

## Herkomst van de vertaling

De berekeningen volgen de standaard Twizy 45/80-configuratie in [OVMS rt_sevcon_tuning.cpp](../reference/rt_sevcon_tuning.cpp), inclusief de standaardinstelling waarbij aangepaste breakdown-parameters uit staan. Hybride reductiekasten en afwijkende breakdown-instellingen zijn niet gemodelleerd.

De registertypen zijn vergeleken met de [gepubliceerde Twizy 0712.0002 DCF-tabel](https://github.com/dexterbg/Twizy-Cfg/blob/master/extras/Twizy-DCF-0712-0002.ods). Deze referentietabel is geen backup van het aangesloten voertuig. Expliciete percentages kunnen door integerafronding één registereenheid van een fabriekswaarde verschillen; een modelreferentie mag dus nooit als volledige fabrieksrestore worden gebruikt.

CAN-decoders volgen [OVMS rt_can.cpp](https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3/blob/master/vehicle/OVMS.V3/components/vehicle_renaulttwizy/src/rt_can.cpp). Het middelen van de twee packspanningswaarden is de upstream-benadering. De capture is geen bewijs van een veilige schrijftoestand: daarvoor zijn versheid per veiligheidsframe en extra foutcontroles nodig.
