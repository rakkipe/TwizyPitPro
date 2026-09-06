> Historische beschrijving van 0.4.0. Gebruik [0.4.1](STATUS-0.4.1.md) voor de actuele toegangssessie en schrijfprocedure.

# Laptop 0.4.0 — vLinker-schrijfprocedure

De laptop heeft nu uitvoerende schrijfcode. **Alleen offline gevalideerd; geen
fysieke adapter- of voertuigtest uitgevoerd.** Android 0.3.0 en PitBridge/M5 zijn
ongewijzigd en ondersteunen alleen uitlezen. ECU-flash en foutcodes wissen zijn
niet toegevoegd. De gemelde SERV-melding is niet uitgelezen of gewist.

## Bediening

1. Sluit de vLinker FS aan en kies expliciet een live verbinding. Opstarten blijft
   demo; aansluiten leest alleen de controlleridentiteit.
2. Los gemelde voertuigstoringen, waaronder SERV, eerst op. Identificeer de
   oorzaak met een passende diagnose; een klepmelding mag niet worden aangenomen
   op basis van uitsluitend het SERV-lampje.
3. Bewerk je ontwerp in Tuning studio. Bevestig de originele motor/reductiekast,
   opgeloste storingen en, indien van toepassing, aangepaste remlichthardware.
4. Kies **Voertuigplan voorbereiden**. Dit leest de identiteit en alle 75
   registerbeginwaarden opnieuw, controleert de voertuigstatus en maakt een
   vergelijking. Er wordt nog niets geschreven.
5. Controleer de concrete begin- en doelwaarden en bevestig het plan. Dat is
   eenmalig en maximaal 120 seconden geldig. Onbekende firmware, onjuiste
   revisie, ontbrekende gegevens of gewijzigde beginwaarden blokkeren uitvoering.
6. Na schrijven: adapter aangesloten laten, contact UIT zetten en wachten tot de
   app dat via CAN heeft waargenomen. Dan contact AAN, N, GO uit en rem ingedrukt;
   kies **Na contactcyclus controleren**. Verbindingsverlies alleen bewijst geen
   contactcyclus. Zonder waargenomen UIT-overgang blijft de controle open.

## Uitvoering en herstel

- Ondersteunde schema's: standaard Twizy 45/80, exact 0712.0001 of 0712.0002 en
  de bijbehorende revisie, vendor en serienummer. Dit is schemaherkenning, geen
  automatisch bewijs van een originele mechanische aandrijflijn.
- Voor elk plan: volledige getypeerde beginsnapshot, herhaalde identiteit,
  hash van de te bevestigen inhoud en controle op veranderingen vóór login.
- Backup en hersteljournaal worden naar schijf geflusht vóór de eerste
  login-, NMT- of registerwijziging. Die bestanden staan onder lokale `data/`.
- Level 4 wordt gecontroleerd. NMT richt zich uitsluitend op node 1; de
  controllerstand wordt teruggelezen via 5110:00.
- Elke schrijfbevestiging moet exact bij CAN-ID, index en subindex passen.
  Elk leesbaar register wordt teruggelezen. D/N/B-snelheidspunten worden in een
  volgorde aangepast die hun onderlinge grenzen bewaart.
- 4641:01 is een write-only Boolean voor kaartcommit; de volledige kaart wordt
  daarna teruggelezen. Een write-only register wordt niet als leesbaar voorgesteld.
- Schrijven vereist herhaalde, recent ontvangen CAN-frames voor stilstand, N,
  rem, contact aan, GO uit, gas los, niet laden en laadkabel niet aangesloten;
  daarnaast motor-RPM nul, CANopen-foutregister nul en 12–15 V adaptermeting.
  SEVCON-EMCY of monitorfouten blokkeren de procedure.
- Identiteit wordt opnieuw vergeleken bij elke veiligheidscontrole. Het venster
  vóór een nieuw schrijfcommando is maximaal 0,75 seconde. Ontvangsttijdstempels
  komen van de laptop; adapterbuffering en timing vragen nog fysieke validatie.
- Bij een ontbrekende bevestiging, fout of gewijzigde toestand stopt de app.
  Geen automatische herhaling, reset, rollback of operational-aanvraag op een
  onzekere bus. Daardoor kan de controller in pre-operational achterblijven.
- **Herstelplan bekijken** leest eerst opnieuw en toont de oorspronkelijke
  backupwaarden. Herstel vereist bevestiging en dezelfde controles. Een derde,
  onverwachte registerwaarde blokkeert herstel. Een gewijzigde backup-hash
  blokkeert herstel na herstart. Herstel eindigt ook met een contactcyclus.

## Getest

101 Python-tests, waaronder byte-uitwisseling met een nagebootste ELM-adapter
en CANopen-controller voor beide modellen en beide ondersteunde firmwareversies.
De tests controleren het volledige schrijf-/commit-/cycluspad, een gewijzigd
plan of beginwaarde, verkeerde identiteit, onderbreking en herstel na herstart,
verloren ACK, read-back-fout, verlopen veiligheidscontrole, actieve fouten,
EMCY, beweging, lage spanning, gewijzigde controller tijdens toepassing,
mislukte kaartcommit, beschadigde backup en geblokkeerde HTTP-bediening op afstand.

Dit bewijst geen circuitgeschiktheid, thermische grenzen, elektrische aansluiting
of foutvrije werking van de fysieke vLinker. Een mogelijk SERV-signaal uit een
andere ECU wordt niet volledig afgedekt door alleen het SEVCON-foutregister.
Er is nog geen volledige Renault-DTC-decoder of wisroute voor de laadklep.

## Bronnen

- [OVMS-controllerbron](../reference/rt_sevcon.cpp): level 4 en pre-operational.
- [OVMS-tuningbron](../reference/rt_sevcon_tuning.cpp): maps en kaartcommit.
- [Twizy 0712.0002 DCF](https://github.com/dexterbg/Twizy-Cfg/blob/master/extras/Twizy-DCF-0712-0002.ods): registertypen; 5000:01 en 5110:00 zijn Unsigned8,
  5000:02/03 Unsigned16, 4641:01 Boolean/write-only. De volledige DCF wordt niet
  opnieuw gepubliceerd in deze repository.
- [Renault Twizy-waarschuwingslampjes](https://www.user-manual.renault.com/nl/hoofdstuk-1-ken-uw-auto/waarschuwingslampjes): laadklepmelding en waarschuwingen.
