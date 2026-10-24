"""
Module de persistance et de gestion de l'historique des mesures biomédicales.

Permet d'archiver, consulter et purger les examens cardiaques au format Excel (.xlsx).
"""

from datetime import datetime
import os
from typing import Sequence, Union, Optional
import pandas as pd


class EnregistreurExcel:
    """Gestionnaire d'archivage des sessions d'acquisition PPG dans un classeur Excel."""

    def __init__(self, nom_fichier: str = "Suivi_Patients_BPM.xlsx"):
        self.nom_fichier = nom_fichier

    def charger_donnees(self) -> pd.DataFrame:
        """Lit le fichier Excel d'historique et renvoie un DataFrame Pandas."""
        if os.path.exists(self.nom_fichier):
            try:
                return pd.read_excel(self.nom_fichier)
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

    def supprimer_ligne(self, index_ligne: int) -> bool:
        """
        Supprime une mesure spécifique du tableau Excel à partir de son index de ligne.

        Args:
            index_ligne: Index (0-based) de la ligne à supprimer.

        Returns:
            True si la suppression a réussi, False sinon.
        """
        if os.path.exists(self.nom_fichier):
            df = pd.read_excel(self.nom_fichier)
            if 0 <= index_ligne < len(df):
                df = df.drop(index_ligne).reset_index(drop=True)
                df.to_excel(self.nom_fichier, index=False)
                return True
        return False

    def sauvegarder_mesure(
        self,
        donnees_brutes: Sequence[float],
        bpm_calcule: Union[float, str],
        duree_choisie: int,
        sdnn_ms: Optional[float] = None,
    ) -> str:
        """
        Ajoute une nouvelle entrée d'examen à la fin du classeur Excel sans écraser l'historique.

        Args:
            donnees_brutes: Échantillons ADC capturés durant la fenêtre.
            bpm_calcule: Valeur de fréquence cardiaque calculée (BPM) ou statut d'erreur.
            duree_choisie: Durée de la mesure en secondes.
            sdnn_ms: Variabilité de la fréquence cardiaque (SDNN en ms), optionnelle.

        Returns:
            Chemin du fichier Excel mis à jour.
        """
        horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        nouvelle_ligne = {
            "Date et Heure": horodatage,
            "Durée (s)": duree_choisie,
            "BPM Moyen": bpm_calcule,
            "Variabilité SDNN (ms)": sdnn_ms if sdnn_ms is not None else "N/A",
            "Échantillons capturés": len(donnees_brutes),
        }

        df_nouvelle = pd.DataFrame([nouvelle_ligne])

        if os.path.exists(self.nom_fichier):
            df_existant = self.charger_donnees()
            if not df_existant.empty:
                df_final = pd.concat([df_existant, df_nouvelle], ignore_index=True)
            else:
                df_final = df_nouvelle
        else:
            df_final = df_nouvelle

        df_final.to_excel(self.nom_fichier, index=False)
        return self.nom_fichier
