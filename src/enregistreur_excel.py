# enregistreur_excel.py
from datetime import datetime
import os
import pandas as pd


class EnregistreurExcel:
    """
    Gère la sauvegarde, le chargement et la suppression des mesures
    cardiaques dans un fichier Excel (.xlsx).
    """

    def __init__(self, nom_fichier="Suivi_Patients_BPM.xlsx"):
        self.nom_fichier = nom_fichier

    def charger_donnees(self):
        """Lit le fichier Excel et renvoie un DataFrame Pandas."""
        if os.path.exists(self.nom_fichier):
            return pd.read_excel(self.nom_fichier)
        return pd.DataFrame()

    def supprimer_ligne(self, index_ligne):
        """Supprime une ligne spécifique du tableau Excel."""
        if os.path.exists(self.nom_fichier):
            df = pd.read_excel(self.nom_fichier)

            if 0 <= index_ligne < len(df):
                df = df.drop(index_ligne)
                df.to_excel(self.nom_fichier, index=False)
                return True
        return False

    def sauvegarder_mesure(self, donnees_brutes, bpm_calcule, duree_choisie):
        """Ajoute une nouvelle mesure à la fin du fichier Excel sans écraser l'historique."""
        horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        nouvelle_ligne = {
            "Date et Heure": horodatage,
            "Durée (s)": duree_choisie,
            "BPM Moyen": bpm_calcule,
            "Échantillons capturés": len(donnees_brutes),
        }

        if os.path.exists(self.nom_fichier):
            df = pd.read_excel(self.nom_fichier)
            df_nouvelle = pd.DataFrame([nouvelle_ligne])
            df_final = pd.concat([df, df_nouvelle], ignore_index=True)
        else:
            df_final = pd.DataFrame([nouvelle_ligne])

        df_final.to_excel(self.nom_fichier, index=False)
        return self.nom_fichier
