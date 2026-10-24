"""
Module de traitement numérique du signal (DSP) pour la photopléthysmographie (PPG).

Implémente :
- Le calcul dynamique de la fréquence d'échantillonnage (Fe)
- Un filtre passe-bande de Butterworth d'ordre 3 sans déphasage (filtfilt) sur [0.5 Hz - 4.0 Hz]
- Une détection topologique adaptative des pics systoliques
- Le calcul du rythme cardiaque (BPM) et de la variabilité cardiaque (HRV / SDNN)
"""

from typing import Union, Dict, Any, Sequence
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks


class TraitementPPG:
    """Classe utilitaire regroupant les algorithmes d'analyse du signal PPG."""

    FREQ_MIN_HZ = 0.5  # 30 BPM
    FREQ_MAX_HZ = 4.0  # 240 BPM
    ORDRE_FILTRE = 3
    DISTANCE_MIN_SEC = 0.3  # Période réfractaire minimale (~200 BPM max)
    FACTEUR_PROEMINENCE = 0.5

    @classmethod
    def analyser_signal(
        cls, donnees_brutes: Sequence[float], duree_secondes: float = 30.0
    ) -> Dict[str, Any]:
        """
        Analyse complète d'une fenêtre d'acquisition PPG brute.

        Args:
            donnees_brutes: Séquence des valeurs ADC mesurées.
            duree_secondes: Durée de la fenêtre d'enregistrement en secondes.

        Returns:
            Dictionnaire contenant le statut, le BPM moyen, la variabilité (SDNN en ms),
            la fréquence d'échantillonnage estimée, le signal filtré et les index des pics.
        """
        n_points = len(donnees_brutes)
        if n_points < 100 or duree_secondes <= 0:
            return {
                "valide": False,
                "statut": "Erreur Capteur",
                "bpm": "Erreur Capteur",
                "sdnn_ms": None,
                "fs": 0.0,
                "signal_filtre": np.array([]),
                "pics": np.array([], dtype=int),
            }

        signal_brut = np.asarray(donnees_brutes, dtype=float)

        # 1. Fréquence d'échantillonnage dynamique (s'adapte à la cadence réelle du bus série)
        fs = n_points / float(duree_secondes)
        nyq = 0.5 * fs

        # Sécurité fréquentielle : la fréquence de Nyquist doit dépasser la coupure haute
        if nyq <= cls.FREQ_MAX_HZ:
            return {
                "valide": False,
                "statut": "Fréquence d'échantillonnage insuffisante",
                "bpm": "Erreur Capteur",
                "sdnn_ms": None,
                "fs": round(fs, 2),
                "signal_filtre": np.array([]),
                "pics": np.array([], dtype=int),
            }

        # 2. Filtre passe-bande de Butterworth (0.5 Hz à 4.0 Hz -> 30 à 240 BPM)
        low = max(0.001, min(cls.FREQ_MIN_HZ / nyq, 0.99))
        high = max(low + 0.001, min(cls.FREQ_MAX_HZ / nyq, 0.99))
        b, a = butter(cls.ORDRE_FILTRE, [low, high], btype="band")

        # 3. Filtrage numérique à phase nulle (évite tout déphasage temporel des ondes systoliques)
        signal_filtre = filtfilt(b, a, signal_brut)

        # 4. Détection topologique adaptative des pics systoliques
        distance_min = max(1, int(fs * cls.DISTANCE_MIN_SEC))
        ecart_type = float(np.std(signal_filtre))
        if ecart_type < 1e-6:
            return {
                "valide": False,
                "statut": "Signal trop faible",
                "bpm": "Signal trop faible",
                "sdnn_ms": None,
                "fs": round(fs, 2),
                "signal_filtre": signal_filtre,
                "pics": np.array([], dtype=int),
            }

        seuil_proeminence = ecart_type * cls.FACTEUR_PROEMINENCE
        pics, _ = find_peaks(
            signal_filtre, distance=distance_min, prominence=seuil_proeminence
        )

        # 5. Calcul du BPM et de la variabilité cardiaque (HRV - SDNN)
        if len(pics) < 3:
            return {
                "valide": False,
                "statut": "Signal trop faible",
                "bpm": "Signal trop faible",
                "sdnn_ms": None,
                "fs": round(fs, 2),
                "signal_filtre": signal_filtre,
                "pics": pics,
            }

        # Calcul via les intervalles inter-battements (IBI / R-R) et sur la fenêtre globale
        intervalles_sec = np.diff(pics) / fs
        bpm_global = round(len(pics) * (60.0 / float(duree_secondes)), 1)
        sdnn_ms = round(float(np.std(intervalles_sec) * 1000.0), 1)

        return {
            "valide": True,
            "statut": "OK",
            "bpm": bpm_global,
            "sdnn_ms": sdnn_ms,
            "fs": round(fs, 2),
            "signal_filtre": signal_filtre,
            "pics": pics,
        }

    @classmethod
    def calculer_bpm(
        cls, donnees_brutes: Sequence[float], duree_secondes: float = 30.0
    ) -> Union[float, str]:
        """
        Calcule uniquement le BPM moyen sur la fenêtre capturée (rétrocompatible).

        Args:
            donnees_brutes: Liste des échantillons ADC bruts.
            duree_secondes: Durée de l'acquisition en secondes.

        Returns:
            BPM arrondi à 1 décimale (float) ou message d'erreur (str).
        """
        resultat = cls.analyser_signal(donnees_brutes, duree_secondes=duree_secondes)
        return resultat["bpm"]
