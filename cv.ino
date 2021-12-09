#include <Wire.h>
#include <Math.h>
#include <Adafruit_MCP4725.h>
#include <Adafruit_ADS1X15.h>
Adafruit_ADS1015 ads;

//This is the I2C Address of the MCP4725, by default (A0 pulled to GND).
//For devices with A0 pulled HIGH, use 0x63
#define MCP4725_ADDR 0x62

const int HANDSHAKE = 0;
const int START_PAUSE = 4; 
const int READ_SWEEPTIME = 5;
const int READ_VLOW = 6;
const int READ_VHIGH = 7;
const int READ_NUM_SCAN = 8;
const int STOP = 9;
const int vSweepPin = A1;

// Default values
bool continue_scan;
float sweeptime = 20; //seconds
float vLow = -1;
float vHigh = 0.6; 
int numScan = 1; 
float vLow_comp = vLow + 1;
float vHigh_comp = vHigh + 1;

// Instantiate the DAC
Adafruit_MCP4725 dac;

void setup() {
  dac.begin(MCP4725_ADDR);
  ads.setGain(GAIN_ONE);
  ads.begin();
  Serial.begin(115200);
  vLow_comp = vLow + 1;
  vHigh_comp = vHigh + 1;
  Serial.println();
}

bool check_start_pause_cmd() {
  // Check if data has been sent to Arduino and respond accordingly
  if (Serial.available() > 0) {
    // Read in request
    int inByte = Serial.read();
    if (inByte == START_PAUSE) {
      continue_scan = !continue_scan;
    }
    if (inByte == STOP) {
      return false;
    }
    return true;
  }
  return true;
}

void sweep_voltage() {
  for (int scan_i = 1 ; scan_i <= numScan ; scan_i++) {
    // Run through the full 12-bit scale for a triangle wave
    uint32_t dac_vLow = uint32_t(round(vLow_comp / 5.0 * 4095.0));
    uint32_t dac_vHigh = uint32_t(round(vHigh_comp / 5.0 * 4095.0));
    for (uint32_t counter_up = dac_vLow; counter_up <  dac_vHigh; counter_up++)
    {
      
      if (continue_scan) {
        dac.setVoltage(counter_up, false);
        delay(sweeptime / 2 / (dac_vHigh - dac_vLow) * 1000);
        int16_t v_Sweep = ads.readADC_SingleEnded(0);
        int16_t v_TIA = ads.readADC_SingleEnded(1);
        unsigned long timeMilliseconds = millis();
        Serial.println(String(String(timeMilliseconds,DEC)+ "," + String(v_Sweep, DEC)+ "," + String(v_TIA, DEC)));
        if (check_start_pause_cmd() == false) {
          dac.setVoltage(uint32_t(819), false);
          return;
        }
      }
      else {
        while (continue_scan == false) {
          if (check_start_pause_cmd() == false) {
            dac.setVoltage(uint32_t(819), false);
            return;
          }
        }
      }
      
    }
 
    for (uint32_t counter_dn = dac_vHigh; counter_dn > dac_vLow; counter_dn--)
    {
      if (continue_scan) {
        dac.setVoltage(counter_dn, false);
        delay(sweeptime / 2 / (dac_vHigh - dac_vLow) * 1000);
        int16_t v_Sweep = ads.readADC_SingleEnded(0);
        int16_t v_TIA = ads.readADC_SingleEnded(1);
        unsigned long timeMilliseconds = millis();
        Serial.println(String(String(timeMilliseconds,DEC)+ "," + String(v_Sweep, DEC) + "," + String(v_TIA, DEC)));
        if (check_start_pause_cmd() == false) {
          dac.setVoltage(uint32_t(819), false);
          return;
        }
      }
      else {
        while (continue_scan == false) {
          if (check_start_pause_cmd() == false) {
            dac.setVoltage(uint32_t(819), false);
            return;
          }
        }
      }
    }
  }
  dac.setVoltage(uint32_t(819), false);
  Serial.println("DONE SWEEPING");
  Serial.println("DONE SWEEPING");
  Serial.println("DONE SWEEPING");
  Serial.println("DONE SWEEPING");
  Serial.println("DONE SWEEPING");
}

void loop() {
  // Check if data has been sent to Arduino and respond accordingly
  if (Serial.available() > 0) {
    // Read in request
    int inByte = Serial.read();
    // If data is requested, fetch it and write it, or handshake
    switch(inByte) {
      case START_PAUSE:
        continue_scan = true;
        sweep_voltage();
        break;
      case READ_SWEEPTIME:
        // Read in frequency
        sweeptime = Serial.readStringUntil('x').toFloat();
        break;
      case READ_VLOW:
        vLow = Serial.readStringUntil('x').toFloat();
        vLow_comp = vLow + 1;
        break;
      case READ_VHIGH:
        vHigh = Serial.readStringUntil('x').toFloat();
        vHigh_comp = vHigh + 1;
        break;
      case READ_NUM_SCAN:
        numScan = Serial.readStringUntil('x').toInt();
        break;
      case HANDSHAKE:
        if (Serial.availableForWrite()) {
          Serial.println("Message received.");
        }
        break;
    }
  }
}
