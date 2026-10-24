# traitement_signal.py
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks


class TraitementPPG:
    """
    Module de traitement numérique du signal PPG.
    Applique un filtre passe-bande de Butterworth d'ordre 3 et détecte les pics systoliques.
    """

    @staticmethod
    def calculer_bpm(donnees_brutes, duree_secondes=30):
        # Sécurité : vérifier qu'un nombre suffisant d'échantillons a été capté
        if len(donnees_brutes) < 100:
            return "Erreur Capteur"

        # 1. Calcul de la fréquence d'échantillonnage dynamique (Fe)
        # S'adapte automatiquement à la cadence réelle du port série
        fs = len(donnees_brutes) / duree_secondes

        # 2. Filtre de Butterworth Passe-Bande (0.5 Hz à 4.0 Hz -> 30 BPM à 240 BPM)
        nyq = 0.5 * fs
        low = 0.5 / nyq
        high = 4.0 / nyq
        b, a = butter(3, [low, high], btype="band")

        # 3. Filtrage numérique sans déphasage (Zero-phase filtering)
        signal_filtre = filtfilt(b, a, donnees_brutes)

        # 4. Détection topologique des pics systoliques
        # Distance minimale : 0.3 seconde (autorise jusqu'à 200 BPM max)
        distance_min = fs * 0.3
        # Proéminence adaptative basée sur l'écart-type du signal filtré
        seuil_proeminence = np.std(signal_filtre) * 0.5

        pics, _ = find_peaks(
            signal_filtre, distance=distance_min, prominence=seuil_proeminence
        )

        # 5. Calcul final du BPM moyen
        if len(pics) < 3:
            return "Signal trop faible"

        bpm = len(pics) * (60 / duree_secondes)

        return round(bpm, 1)
