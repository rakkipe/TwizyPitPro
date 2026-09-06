# Aansluiten en bouwen

## Laptop + vLinker FS

USB naar laptop; vLinker naar de diagnoseconnector. De adapter moet als COM-poort
beschikbaar zijn (eventueel Vgate-driver nodig). Interface is ELM/STN ASCII,
115200 baud, CAN 11-bit/500 kbit/s. CANopen gebruikt 0x601 naar node 1 en 0x581 retour.
CAF0 en CFC0 voorkomen ISO-TP-formattering en automatische flow-control.
De app opent geen COM-poort bij het starten en doet geen automatische poortprobes.

## M5StickC Plus2 + CAN Unit U085

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
zijn eigen demo en USB-leespad. Beide varianten hebben geen live tuningschrijfroute.
De M5 heeft geen wifi-streaming in deze build. Een homescreen-snelkoppeling voor
de viewer is geen vervanging voor de zelfstandige Android-APK.
