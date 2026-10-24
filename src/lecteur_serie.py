# lecteur_serie.py
import time
from PyQt6.QtCore import QObject, pyqtSignal
import serial
import serial.tools.list_ports


class LecteurSerieWorker(QObject):
    """
    Worker exécuté dans un thread secondaire pour lire en continu
    les données brutes envoyées par l'Arduino sur le port série USB.
    """

    # Les signaux permettent d'envoyer des données de ce Thread vers l'interface graphique en toute sécurité
    donnee_recue = pyqtSignal(int)      # Envoie la valeur ADC brute (0-1023)
    erreur_connexion = pyqtSignal(str)  # Envoie un message en cas de déconnexion

    def __init__(self, baud_rate=115200):
        super().__init__()
        self.baud_rate = baud_rate
        self.running = False
        self.ser = None

    def trouver_port_moniteur(self):
        """Scanne les ports COM pour trouver automatiquement le microcontrôleur."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Recherche des mots-clés typiques des puces USB-Série (Arduino, CH340, CP210x...)
            description = port.description.lower()
            if (
                "arduino" in description
                or "usb-serial" in description
                or "ch340" in description
                or "cp210x" in description
            ):
                return port.device
        return None

    def run(self):
        """Boucle principale d'écoute du port série."""
        port_com = self.trouver_port_moniteur()

        if not port_com:
            self.erreur_connexion.emit(
                "Aucun moniteur cardiaque détecté.\nVérifiez le branchement USB."
            )
            return

        try:
            # Ouverture du port avec un timeout de 1s
            self.ser = serial.Serial(port_com, self.baud_rate, timeout=1)
            # Pause de sécurité pour absorber le reset matériel de l'Arduino lors de la connexion série
            time.sleep(2)
            self.running = True

            while self.running:
                if self.ser.in_waiting > 0:
                    try:
                        # Lecture d'une ligne, décodage et nettoyage des espaces/sauts de ligne
                        ligne = self.ser.readline().decode("utf-8").strip()

                        if ligne.isdigit():  # Vérifie que la trame reçue est bien un entier valide
                            valeur_adc = int(ligne)
                            self.donnee_recue.emit(valeur_adc)

                    except (UnicodeDecodeError, ValueError):
                        # Ignore les trames incomplètes pouvant survenir à l'ouverture du port
                        continue

        except serial.SerialException as e:
            self.erreur_connexion.emit(f"Erreur de communication : {e}")

        finally:
            self.arreter()

    def arreter(self):
        """Ferme proprement la connexion série."""
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
