/*
 * Système d'Acquisition Cardiaque par Photopléthysmographie (PPG) - Firmware Arduino
 *
 * Échantillonne le signal analogique issu de l'étage de conditionnement (LDR + AOP)
 * à une fréquence stricte de 50 Hz (période T = 20 ms) et transmet les valeurs ADC
 * brutes (10 bits : 0 - 1023) sur le bus UART/USB à 115200 bauds.
 */

const int PIN_CAPTEUR_PPG = A0;              // Entrée analogique connectée à la sortie AO du module LDR
const unsigned long PERIODE_US = 20000UL;    // 20 000 µs = 20 ms -> Fréquence d'échantillonnage de 50 Hz

unsigned long dernierEchantillonUs = 0;

void setup() {
  // Initialisation de la liaison série haute vitesse
  Serial.begin(115200);
  dernierEchantillonUs = micros();
}

void loop() {
  unsigned long maintenantUs = micros();

  // Cadencement non-bloquant précis à 50 Hz
  if (maintenantUs - dernierEchantillonUs >= PERIODE_US) {
    dernierEchantillonUs += PERIODE_US;

    int signalBrut = analogRead(PIN_CAPTEUR_PPG);
    Serial.println(signalBrut);
  }
}
