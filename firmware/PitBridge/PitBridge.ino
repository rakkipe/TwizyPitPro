/* Twizy Pit Pro / PitBridge 1 — M5StickC Plus2 + M5 CAN Unit U085.
 * TX = Grove yellow GPIO32, RX = white GPIO33. Power Unit from Grove 5V.
 * USB 115200. Boot in listen-only, switch to normal for explicit SDO uploads.
 * No SDO download, NMT, login, reset, fault clear, or arbitrary transmit API.
 * See docs/HARDWARE.md. Firmware does not prove wiring/vehicle qualification.
 */
#include <M5Unified.h>
#include <driver/twai.h>

static const gpio_num_t CAN_TX = GPIO_NUM_32;
static const gpio_num_t CAN_RX = GPIO_NUM_33;
static bool installed = false, active = false, segmented = false;
static uint8_t expectedToggle = 0;
static uint32_t lastRead = 0, frames = 0, shown = 0;
static String input;
static uint8_t pendingIndex[3];

static bool startBus(bool readMode) {
  if (installed) { twai_stop(); twai_driver_uninstall(); installed = false; }
  twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX, CAN_RX,
                   readMode ? TWAI_MODE_NORMAL : TWAI_MODE_LISTEN_ONLY);
  general.tx_queue_len = readMode ? 2 : 0;
  general.rx_queue_len = 48;
  twai_timing_config_t timing = TWAI_TIMING_CONFIG_500KBITS();
  twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
  if (twai_driver_install(&general, &timing, &filter) != ESP_OK) return false;
  installed = true;
  if (twai_start() != ESP_OK) { twai_driver_uninstall(); installed = false; return false; }
  active = readMode;
  return true;
}

static void drawStatus() {
  M5.Display.fillScreen(0x1082);
  M5.Display.setTextColor(0xD7E5);
  M5.Display.setTextSize(2);
  M5.Display.setCursor(9, 9); M5.Display.print("TWIZY PIT PRO");
  M5.Display.setTextColor(TFT_WHITE);
  M5.Display.setTextSize(1);
  M5.Display.setCursor(10, 42); M5.Display.print("PITBRIDGE 1 / USB 115200");
  M5.Display.setCursor(10, 64); M5.Display.print(installed ? (active ? "SDO UPLOAD / READ ONLY" : "CAN LISTEN / 500 KBPS") : "CAN INIT FAILED");
  M5.Display.setCursor(10, 86); M5.Display.printf("RX %lu  |  TX32 RX33", (unsigned long)frames);
  M5.Display.setCursor(10, 108); M5.Display.print("NO TUNING / NO FLASH / NO RESET");
}

static int hexNibble(char c) {
  if (c >= '0' && c <= '9') return c-'0';
  if (c >= 'A' && c <= 'F') return c-'A'+10;
  if (c >= 'a' && c <= 'f') return c-'a'+10;
  return -1;
}

static void handleRead(const String& command) {
  if (command.length() != 21 || !command.startsWith("READ ")) { Serial.println("ERR FORMAT"); return; }
  twai_message_t request = {};
  request.identifier = 0x601;
  request.data_length_code = 8;
  request.ss = 1; // bounded single-shot transmission
  for (int i=0; i<8; ++i) {
    int hi=hexNibble(command[5+i*2]), lo=hexNibble(command[6+i*2]);
    if (hi<0 || lo<0) { Serial.println("ERR HEX"); return; }
    request.data[i]=(hi<<4)|lo;
  }
  bool initial = request.data[0] == 0x40;
  bool segment = request.data[0] == (0x60 | (expectedToggle<<4));
  for (int i=initial?4:1; i<8; ++i) if (request.data[i]) { Serial.println("ERR RESERVED"); return; }
  if (!initial && !(segment && segmented && active && (uint32_t)(millis()-lastRead)<1500)) {
    Serial.println("ERR UPLOAD_ONLY"); return;
  }
  if (initial) {
    segmented=false;
    expectedToggle=0;
    for(int i=0;i<3;++i) pendingIndex[i]=request.data[i+1];
  }
  if (!active && !startBus(true)) { Serial.println("ERR CAN_INIT"); return; }
  twai_message_t stale;
  while (twai_receive(&stale,0) == ESP_OK) {}
  if (twai_transmit(&request,pdMS_TO_TICKS(100)) != ESP_OK) {
    Serial.println("ERR TX"); segmented=false; startBus(false); return;
  }
  uint32_t start=millis();
  while ((uint32_t)(millis()-start)<850) {
    twai_message_t response;
    if (twai_receive(&response,pdMS_TO_TICKS(10)) != ESP_OK) continue;
    ++frames;
    if (response.extd || response.rtr || response.identifier!=0x581 || response.data_length_code!=8) continue;
    bool sameIndex=true;
    for(int i=0;i<3;++i) if(response.data[i+1]!=pendingIndex[i]) sameIndex=false;
    const uint8_t cs=response.data[0];
    bool abort=cs==0x80 && sameIndex;
    bool match=initial ? (sameIndex && (cs&0xE0)==0x40) : ((cs&0xE0)==0 && ((cs>>4)&1)==expectedToggle);
    if (!abort && !match) continue;
    Serial.print("RX 581 ");
    for(int i=0;i<8;++i) Serial.printf("%02X",response.data[i]);
    Serial.println();
    if(abort) segmented=false;
    else if(initial) segmented=(cs&2)==0;
    else { segmented=(cs&1)==0; expectedToggle^=1; }
    lastRead=millis();
    return;
  }
  segmented=false;
  lastRead=millis();
  Serial.println("ERR TIMEOUT");
}

void setup() {
  auto cfg=M5.config(); M5.begin(cfg);
  M5.Display.setRotation(1);
  Serial.begin(115200);
  input.reserve(40);
  startBus(false);
  drawStatus();
}

void loop() {
  M5.update();
  while(Serial.available()) {
    char c=(char)Serial.read();
    if(c=='\n') {
      if(input=="HELLO") Serial.println("PITBRIDGE 1 READONLY");
      else handleRead(input);
      input="";
    } else if(c!='\r') {
      if(input.length()<40) input+=c;
      else input="INVALID";
    }
  }
  if(active && (uint32_t)(millis()-lastRead)>1500) { segmented=false; startBus(false); }
  if(installed) {
    twai_message_t message;
    for(int i=0;i<24 && twai_receive(&message,0)==ESP_OK;++i) ++frames;
  }
  if((uint32_t)(millis()-shown)>700) {drawStatus();shown=millis();}
  delay(2);
}
