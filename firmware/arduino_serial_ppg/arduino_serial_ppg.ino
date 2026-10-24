/*
 * Système d'Acquisition de Données Brutes (PPG) - Arduino Uno / Mega
 *
 * Lit la tension analogique issue du module capteur optique (LDR + AOP)
 * sur la broche A0 et transmet la mesure brute (0 - 1023) par liaison série
 * à une fréquence d'échantillonnage de 50 Hz (période de 20 ms).
 */

const int pulsePin = A0; // Broche AO du module LDR

void setup() {
  // Initialisation de la liaison série à haute vitesse (115200 bauds)
  Serial.begin(115200);
}

void loop() {
  // Lecture du convertisseur analogique-numérique (résolution 10 bits : 0 à 1023)
  int rawSignal = analogRead(pulsePin);

  // Envoi de la valeur brute vers le PC
  Serial.println(rawSignal);

  // Pause de 20 ms pour un échantillonnage à 50 Hz
  delay(20);
}
