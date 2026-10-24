/*
 * Système d'Acquisition Cardiaque par Photopléthysmographie (PPG) - Firmware ESP32 (BLE + USB)
 *
 * Échantillonne le signal PPG sur un convertisseur ADC 12 bits (0 - 4095) à 50 Hz
 * et diffuse les mesures simultanément :
 * - En Bluetooth Low Energy (BLE) via le service Nordic UART (NUS) pour l'application Web
 * - Sur le port série USB (115200 bauds) pour l'application de bureau PyQt6
 *
 * Prérequis bibliothèque : NimBLE-Arduino (v2.x)
 */

#include <NimBLEDevice.h>

// UUIDs standards pour le service UART BLE (Nordic UART Service - NUS)
#define SERVICE_UUID           "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define TX_CHARACTERISTIC_UUID "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

const int PIN_CAPTEUR_PPG = 34;              // GPIO 34 (ADC1_CH6 sur ESP32)
const unsigned long PERIODE_US = 20000UL;    // Période de 20 ms (50 Hz)

NimBLEServer* pServer = nullptr;
NimBLECharacteristic* pTxCharacteristic = nullptr;
bool deviceConnected = false;
unsigned long dernierEchantillonUs = 0;

class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo) override {
    deviceConnected = true;
  }

  void onDisconnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo, int reason) override {
    deviceConnected = false;
    NimBLEDevice::startAdvertising();
  }
};

void setup() {
  Serial.begin(115200);

  // Configuration de la résolution ADC à 12 bits (0 - 4095, pas de ~0.81 mV @ 3.3V)
  analogReadResolution(12);

  // Initialisation du serveur BLE
  NimBLEDevice::init("Biomedical_PPG_ESP32");
  pServer = NimBLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  NimBLEService* pService = pServer->createService(SERVICE_UUID);
  pTxCharacteristic = pService->createCharacteristic(
    TX_CHARACTERISTIC_UUID,
    NIMBLE_PROPERTY::NOTIFY
  );

  pService->start();

  NimBLEAdvertising* pAdvertising = NimBLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->start();

  dernierEchantillonUs = micros();
}

void loop() {
  unsigned long maintenantUs = micros();

  if (maintenantUs - dernierEchantillonUs >= PERIODE_US) {
    dernierEchantillonUs += PERIODE_US;

    int signalBrut = analogRead(PIN_CAPTEUR_PPG);

    // Transmission USB Série (compatible avec l'IHM Desktop Python)
    Serial.println(signalBrut);

    // Notification BLE (compatible avec l'interface Web Bluetooth)
    if (deviceConnected && pTxCharacteristic != nullptr) {
      String dataStr = String(signalBrut) + "\n";
      pTxCharacteristic->setValue((uint8_t*)dataStr.c_str(), dataStr.length());
      pTxCharacteristic->notify();
    }
  }
}
