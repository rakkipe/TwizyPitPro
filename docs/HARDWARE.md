# Aansluiten en bouwen

## Laptop + vLinker FS

USB naar laptop; vLinker naar de diagnoseconnector. De adapter moet als COM-poort
beschikbaar zijn (eventueel Vgate-driver nodig). Interface is ELM/STN ASCII,
115200 baud, CAN 11-bit/500 kbit/s. CANopen gebruikt 0x601 naar node 1 en 0x581 retour.
CAF0 en CFC0 voorkomen ISO-TP-formattering en automatische flow-control.
De app opent geen COM-poort bij het starten en doet geen automatische poortprobes.

## M5StickC Plus2 + CAN Unit U085

### Eén bridge voor verschillende Twizy-versies

PitBridge 1 draagt CANopen-leesaanvragen over zonder een Twizy-model of
controllerfirmware in de M5 vast te leggen. De app leest model en firmware bij
elke voertuigverbinding opnieuw uit. Wisselen tussen Twizy 45/80 of een andere
Twizy-firmware vereist daarom geen modelspecifieke M5-flash, zolang hetzelfde
CANopen-protocol wordt ondersteund.

Onbekende firmware verhindert de beschikbare basisuitlezing niet. Ontbrekende
registers blijven als fout zichtbaar; de app veronderstelt geen vervangende
waarden of schrijfcompatibiliteit. Een exacte registerinventaris en toekomstige
schrijfondersteuning vereisen afzonderlijk gekwalificeerde schema's.

Laptop 0.3.2 test dit met twaalf gesimuleerde model-/versiecombinaties: 45 en 80,
elk met 0712.0001, 0712.0002, 0712.0003 en drie onbekende versieaanduidingen.
Dit is geen bewijs dat alle bestaande of toekomstige voertuigfirmware fysiek
werkt. De huidige firmware ondersteunt alleen lezen; een toekomstige uitbreiding
met schrijven kan een eenmalige M5-update vereisen.

Een reguliere app-update hoeft geen M5-update te vragen zolang PitBridge 1
compatibel blijft. Oudere PitBridge 1 zonder CAPTURE blijft voor SDO-uitlezing
bruikbaar. Bij opnieuw verbinden worden optionele meetfuncties opnieuw ontdekt.
Willekeurige andere M5-firmware, zoals een PowerBox, spreekt mogelijk een ander
protocol en wordt niet automatisch als PitBridge behandeld.

### Aansluiten

Controleer het opschrift: onderstaande pinnen zijn voor **CAN Unit U085** met
CA-IS3050G. Dit is een transceiver voor de ESP32-TWAI-controller; geen MCP2515 SPI-board.

| Grove-draad | M5StickC Plus2 | CAN Unit |
|---|---|---|
| zwart | GND | GND |
| rood | 5 V | 5 V |
| geel | GPIO32 | CAN_TX |
| wit | GPIO33 | CAN_RX |

Voed de M5 via USB. Sluit CANH/CANL via een correct bedrade diagnosekabel aan.
Controleer de voertuigspecifieke connector/kabel vóór aansluiting. Sluit geen
12 V aan op de Grove-voeding. Voeg geen 120-ohm-afsluitweerstand toe aan een reeds
afgesloten voertuigbus. Laat andere actieve tuningapparatuur losgekoppeld.

`firmware/PitBridge/PitBridge.ino` start in TWAI listen-only. Alleen een expliciet
READ-verzoek van de laptop schakelt tijdelijk naar normale CAN-modus om een
SDO-upload te verzenden. Dat is een actieve leesaanvraag, geen volledig passieve
diagnose. Na 1,5 seconde zonder vervolg keert hij terug naar listen-only.

Protocol: `HELLO` → `PITBRIDGE 1 READONLY`; `READ <16 hextekens>` →
`RX 581 <16 hextekens>` of `ERR ...`. Alleen upload-initiate en de bijbehorende
uploadsegmenten worden doorgelaten. Geen NMT, willekeurige TX, login of writes.
Versie 0.3 voegt `CAPTURE` toe: 1,2 seconde uitsluitend listen-only, gevolgd door
maximaal zes `FRAME <CAN-ID> <16 hextekens>`-regels en `CAPTURE END`.
Bij gemiste frames, overflow of CAN-fouten wordt de opname verworpen.
Oudere PitBridge-firmware blijft bruikbaar voor SDO-uitlezing en mist deze opname.
De firmware is niet uitwisselbaar met eerdere M5CanBridge- of Powerbox-protocollen.

Build met Arduino CLI (gecontroleerd met esp32 core 3.3.10, M5Unified 0.2.18
en M5GFX 0.2.25; installeer deze afhankelijkheden eerst):

```powershell
arduino-cli compile --fqbn esp32:esp32:m5stack_stickc_plus2 --output-dir firmware/build firmware/PitBridge
```

Gebruik het juiste board-ID uit `arduino-cli board listall` als je core een andere
naam hanteert. Compileerresultaat staat in `docs/VALIDATIE.md`. Een succesvolle
build bewijst geen elektrische of CAN-buswerking. Tijdens deze levering is niets
naar de M5 of voertuigcontroller geflasht.

## Nothing/Android-telefoon

De zelfstandige native APK vereist Android 11 of nieuwer. Hij heeft een offline
demo, sessieopname en USB-hostondersteuning voor vLinker FS of de bovenstaande
PitBridge. Gebruik een passende USB-C/OTG-verbinding. De app vraagt Android-
USB-toestemming; GPS gebruikt een aparte optionele locatiepermissie. De telefoon,
USB/OTG-voeding en de adapters zijn nog niet fysiek getest. Zie [ANDROID.md](ANDROID.md).

Daarnaast is er een afzonderlijke browserviewer voor de laptop. Start met
`Start.vbs`, verbind telefoon en laptop met hetzelfde vertrouwde netwerk en open
de link die de GUI onder **Hardware** toont. De laptop blijft de CAN-host.
De server moet bereikbaar zijn op poort 8765; firewalltoegang wordt niet automatisch
aangepast. Gebruik geen port-forwarding. De link bevat de tijdelijke viewer-sleutel.

In deze browserviewer kun je dashboard en rapporten lezen. Aansluiten, scannen en
sessies bedienen van de laptop gebeurt op de laptop zelf. De native APK heeft
zijn eigen demo en USB-leespad. Alleen laptop 0.4.0 heeft de afzonderlijke vLinker-schrijfroute; zie [de procedure](STATUS-0.4.md).
De M5 heeft geen wifi-streaming in deze build. Een homescreen-snelkoppeling voor
de viewer is geen vervanging voor de zelfstandige Android-APK.
