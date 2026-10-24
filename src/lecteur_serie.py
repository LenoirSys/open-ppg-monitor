"""
Module d'acquisition asynchrone du flux PPG (Port Série USB & Simulateur Biomédical).

Exécuté dans un QThread dédié afin de garantir l'absence de blocage de l'interface graphique.
Prend en charge :
- La détection automatique Plug & Play des microcontrôleurs (Arduino, ESP32, CH340, CP210x, FTDI)
- La sélection manuelle d'un port COM spécifique
- Un mode Simulation physiologique réaliste (onde systolique + onde dicrote + bruit) à 50 Hz
"""

import math
import random
import time
from typing import Optional, List
from PyQt6.QtCore import QObject, pyqtSignal
import serial
import serial.tools.list_ports


class LecteurSerieWorker(QObject):
    """Worker asynchrone d'écoute du port série ou du générateur physiologique de démonstration."""

    donnee_recue = pyqtSignal(int)      # Valeur ADC brute (ex: 0-1023 ou 0-4095)
    erreur_connexion = pyqtSignal(str)  # Message d'anomalie de communication

    MOTS_CLES_USB = ("arduino", "usb-serial", "ch340", "cp210", "ftdi", "esp32", "usb serial")

    def __init__(self, baud_rate: int = 115200, port_force: Optional[str] = None):
        """
        Initialise le worker d'acquisition.

        Args:
            baud_rate: Vitesse de transmission série en bauds (défaut : 115200).
            port_force: Nom du port COM ('COM3', '/dev/ttyUSB0'), 'SIMULATION' pour le mode démo,
                        ou None pour la détection automatique.
        """
        super().__init__()
        self.baud_rate = baud_rate
        self.port_force = port_force
        self.running = False
        self.ser: Optional[serial.Serial] = None

    @classmethod
    def lister_ports_disponibles(cls) -> List[str]:
        """Retourne la liste des ports COM actifs sur la machine."""
        return [p.device for p in serial.tools.list_ports.comports()]

    def trouver_port_moniteur(self) -> Optional[str]:
        """Scanne les ports COM pour identifier automatiquement le microcontrôleur."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            description = (port.description or "").lower()
            fabricant = (port.manufacturer or "").lower()
            if any(mot in description or mot in fabricant for mot in self.MOTS_CLES_USB):
                return port.device
        return None

    def _executer_simulation(self) -> None:
        """
        Génère un signal PPG synthétique réaliste à 50 Hz (72 BPM nominal)
        comprenant le pic systolique, l'incisure/onde dicrote et une légère dérive respiratoire.
        """
        self.running = True
        fs = 50.0
        periode_echantillon = 1.0 / fs
        frequence_cardiaque_hz = 1.2  # 72 BPM
        t = 0.0

        while self.running:
            phase = (t * frequence_cardiaque_hz) % 1.0

            # Modélisation morphologique d'une onde PPG (systole + onde dicrote)
            onde_systolique = math.exp(-((phase - 0.22) ** 2) / (2 * (0.065 ** 2)))
            onde_dicrote = 0.35 * math.exp(-((phase - 0.52) ** 2) / (2 * (0.09 ** 2)))
            derive_respiratoire = 0.12 * math.sin(2.0 * math.pi * 0.25 * t)
            bruit_capteur = random.gauss(0.0, 0.025)

            # Conversion sur l'échelle ADC 10 bits avec offset lumineux réaliste (~600-640 ADC)
            valeur_adc = int(
                610 + 28.0 * (onde_systolique + onde_dicrote + derive_respiratoire + bruit_capteur)
            )
            valeur_adc = max(0, min(1023, valeur_adc))

            self.donnee_recue.emit(valeur_adc)
            t += periode_echantillon
            time.sleep(periode_echantillon)

    def run(self) -> None:
        """Boucle principale d'acquisition exécutée dans le thread secondaire."""
        if self.port_force == "SIMULATION":
            self._executer_simulation()
            return

        port_com = self.port_force or self.trouver_port_moniteur()

        if not port_com:
            self.erreur_connexion.emit(
                "Aucun moniteur cardiaque détecté sur les ports USB (vous pouvez activer le Mode Simulation)."
            )
            return

        try:
            self.ser = serial.Serial(port_com, self.baud_rate, timeout=1)
            # Pause de sécurité pour absorber le reset matériel de la carte à l'ouverture du port
            time.sleep(2.0)
            self.running = True

            while self.running:
                if self.ser and self.ser.in_waiting > 0:
                    try:
                        ligne = self.ser.readline().decode("utf-8", errors="ignore").strip()
                        if ligne.isdigit():
                            self.donnee_recue.emit(int(ligne))
                    except (UnicodeDecodeError, ValueError):
                        continue
                else:
                    time.sleep(0.002)

        except serial.SerialException as exc:
            self.erreur_connexion.emit(f"Erreur de communication ({port_com}) : {exc}")

        finally:
            self.arreter()

    def arreter(self) -> None:
        """Interrompt la boucle d'écoute et libère proprement la ressource série."""
        self.running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
