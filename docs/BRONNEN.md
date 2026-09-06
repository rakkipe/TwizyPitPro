# Bronmateriaal en onderbouwing — 5 september 2026

1. [Open Vehicles: Renault Twizy](https://docs.openvehicles.com/en/latest/components/vehicle_renaulttwizy/docs/index.html)
   noemt SEVCON-monitoring en tuning tot firmware 0712.0002. Gebruikt voor de
   ondersteunde protocolfamilie en het onderscheid tussen lezen en tuning.
2. [Twizy-Cfg, Michael Balzer](https://github.com/dexterbg/Twizy-Cfg)
   beschrijft versie-uitlezing met 100A:00 en de schrijfbeperking vanaf 0712.0003.
   Een nieuwe appversie kan die firmwarebeperking niet opheffen.
3. [OVMS tuning-broncode](https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3/blob/master/vehicle/OVMS.V3/components/vehicle_renaulttwizy/src/rt_sevcon_tuning.cpp)
   documenteert de modelreferenties en tuningmacro's. Een bestaande lokale kopie
   staat in `reference/rt_sevcon_tuning.cpp`, met de originele MIT-licentietekst.
   Deze lokale snapshot is niet als nieuwste upstream commit aangemerkt. De
   bestanden in de releasetag leggen de daadwerkelijk gebruikte inhoud vast.
4. [OVMS controllerbron](https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3/blob/master/vehicle/OVMS.V3/components/vehicle_renaulttwizy/src/rt_sevcon.cpp)
   gebruikt object 1018:02 voor de controllerfamilie. De lokale kopie is bewaard.
5. [OVMS custom configuration](https://docs.openvehicles.com/en/latest/components/vehicle_renaulttwizy/docs/configuration.html)
   noemt afwijkende controller/reductiekastcombinaties. Daarom bewijst de
   automatische controllerdetectie niet de mechanische uitvoering van het voertuig.
6. [M5Stack CAN Unit U085](https://docs.m5stack.com/en/unit/can)
   beschrijft CA-IS3050G, Grove-voeding en CAN_TX/CAN_RX. [StickC-Plus2](https://docs.m5stack.com/en/core/M5StickC%20PLUS2)
   documenteert de ESP32 en uitbreidingsaansluitingen.
7. [ELM327 datasheet](https://www.elmelectronics.com/wp-content/uploads/2017/01/ELM327DS.pdf)
   is de referentie voor ASCII-adaptercommando's en raw-CAN-configuratie.
8. [Espressif TWAI](https://docs.espressif.com/projects/esp-idf/en/v5.1/esp32/api-reference/peripherals/twai.html)
   documenteert controller-modi. PitBridge gebruikt listen-only bij rust en
   normale modus uitsluitend voor aangevraagde uploads. Exact gedrag blijft
   afhankelijk van de ESP32/core/hardwarecombinatie en moet op de bench worden getest.
9. [OVMS regen-remlicht](https://docs.openvehicles.com/en/latest/components/vehicle_renaulttwizy/docs/brakehack.html)
   verklaart waarom de standaard Twizy-bedrading de SEVCON-remlichtuitgang niet
   bruikbaar maakt. De editor noemt deze afhankelijkheid bij beide drempels.

## Hergebruik en grenzen

Er zijn geen persoonlijke voertuiginstellingen, serienummers of eerdere
live-transacties als actuele voertuigstatus overgenomen.
De demo heeft herkenbaar fictieve identiteit en synthetische metingen.

Alle model-/versiepakketten zijn **reference-only**. Met name een productcode en
softwarestring alleen bewijzen geen schrijftoegang of overeenkomst van elke
objectbreedte. De pakketselectie is geen firmwaregeneratie of ECU-update.

## Licentie

De overgenomen OVMS-bronbestanden houden hun originele Michael Balzer/MIT-notice.
Zie ook `reference/OVMS-LICENSE`. Het nieuwe applicatiewerk is beschikbaar onder
de MIT-licentie in `LICENSE`; verdere notices staan in `THIRD_PARTY_NOTICES.md`.

## Origineel appicoon

Gegenereerd met de ingebouwde imagegen-tool, vervolgens als PNG en Windows ICO
verpakt. De oorspronkelijke gegenereerde PNG blijft ongewijzigd bewaard. De
SVG-variant is een apart eenvoudig geometrisch beeldmerk voor kleine weergaven.
Geen Renault-beeldmerk of claim van officiële Renault-software.

Gebruikte prompt:

> Use case: logo-brand. Create ONE original, polished app icon for 'Twizy Pit Pro',
> a Renault Twizy electric track racing pit-service and telemetry application.
> A compact distinctive front-view silhouette of a tandem electric microcar,
> narrow tall cockpit, two visibly outboard front wheels, simplified white body,
> and an electric lime racing apex/pitlane stroke wrapping diagonally beneath it.
> Design must read clearly at favicon sizes. Flat graphic, sharp geometric
> precision, minimal few bold shapes. Icon fills most of a dark charcoal
> rounded-square tile; lime #d2ff38, white, deep graphite #141719. No text, no
> letters, no Renault diamond, no existing logo, no watermark, no multiple
> variations, no mockup, no shadows outside tile. Square 1:1 composition, centered
> with appropriate safe padding, professional motorsport software identity.
