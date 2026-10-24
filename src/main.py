# main.py
import sys
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
    QSpinBox,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtGui import QFont

from lecteur_serie import LecteurSerieWorker
from enregistreur_excel import EnregistreurExcel
from traitement_signal import TraitementPPG


class FenetreHistorique(QDialog):
    """
    Fenêtre secondaire permettant de visualiser l'historique des mesures
    et de supprimer des enregistrements erronés du fichier Excel.
    """

    def __init__(self, gestionnaire_excel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historique des Mesures")
        self.resize(600, 400)
        self.gestionnaire_excel = gestionnaire_excel

        layout = QVBoxLayout(self)

        # Tableau d'affichage des données
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Bouton d'action pour la suppression
        self.btn_supprimer = QPushButton("🗑️ Supprimer la mesure sélectionnée")
        self.btn_supprimer.setStyleSheet(
            "background-color: #ff4c4c; color: white; font-weight: bold; padding: 8px; border-radius: 4px;"
        )
        self.btn_supprimer.clicked.connect(self.supprimer_selection)
        layout.addWidget(self.btn_supprimer)

        # Chargement initial des données
        self.charger_table()

    def charger_table(self):
        """Lit le fichier Excel et injecte les données dans le composant de tableau."""
        df = self.gestionnaire_excel.charger_donnees()

        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns) if not df.empty else 0)

        if not df.empty:
            self.table.setHorizontalHeaderLabels(df.columns)
            self.table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.Stretch
            )

            for row in range(len(df)):
                for col in range(len(df.columns)):
                    item = QTableWidgetItem(str(df.iloc[row, col]))
                    self.table.setItem(row, col, item)
        else:
            self.table.setColumnCount(0)
            self.table.setRowCount(0)

    def supprimer_selection(self):
        """Action de suppression de la ligne sélectionnée après confirmation."""
        ligne_selectionnee = self.table.currentRow()

        if ligne_selectionnee >= 0:
            reponse = QMessageBox.question(
                self,
                "Confirmation",
                "Voulez-vous vraiment supprimer cette mesure de l'historique ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reponse == QMessageBox.StandardButton.Yes:
                self.gestionnaire_excel.supprimer_ligne(ligne_selectionnee)
                self.charger_table()
        else:
            QMessageBox.warning(
                self,
                "Sélection requise",
                "Veuillez d'abord sélectionner une ligne à supprimer.",
            )


class MoniteurCardioApp(QMainWindow):
    """
    Fenêtre principale de l'application de monitoring biomédical (Version 1 - Arduino Uno).
    Gère l'IHM, le thread d'acquisition série et les déclenchements de mesure.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Moniteur PPG Temps Réel - Maintenance Biomédicale")
        self.resize(1000, 600)

        # Tampon circulaire pour le signal graphique (500 points affichés)
        self.taille_fenetre = 500
        self.donnees_y = np.zeros(self.taille_fenetre)

        # Variables d'état pour la capture de données
        self.en_enregistrement = False
        self.donnees_brutes_sauvegarde = []
        self.gestionnaire_excel = EnregistreurExcel()

        # Configuration du timer pour le compte à rebours visuel (1 tic par seconde)
        self.temps_restant = 0
        self.duree_totale = 0
        self.timer_minuteur = QTimer()
        self.timer_minuteur.timeout.connect(self.tick_minuteur)

        self.init_interface()
        self.init_materiel()

    def init_interface(self):
        """Définition des éléments graphiques de l'application."""
        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QVBoxLayout()

        # --- Barre d'outils supérieure ---
        layout_haut = QHBoxLayout()

        self.bouton_reconnexion = QPushButton("🔄 Rechercher l'appareil")
        self.bouton_reconnexion.clicked.connect(self.relancer_connexion)

        self.bouton_historique = QPushButton("📂 Voir l'Historique")
        self.bouton_historique.clicked.connect(self.ouvrir_historique)

        self.label_statut = QLabel("Statut : Démarrage...")
        self.label_statut.setFont(QFont("Arial", 11))

        self.label_temps = QLabel("Durée (s) :")
        self.label_temps.setFont(QFont("Arial", 11))

        self.spin_temps = QSpinBox()
        self.spin_temps.setRange(10, 120)  # Plage de mesure autorisée : 10s à 2 min
        self.spin_temps.setValue(30)       # Valeur nominale par défaut
        self.spin_temps.setFont(QFont("Arial", 11))

        self.bouton_mesure = QPushButton("🔴 Lancer une mesure")
        self.bouton_mesure.setFont(QFont("Arial", 12))
        self.bouton_mesure.setMinimumHeight(40)
        self.bouton_mesure.setEnabled(False)
        self.bouton_mesure.clicked.connect(self.lancer_enregistrement)

        # Assemblage de la barre d'outils
        layout_haut.addWidget(self.bouton_reconnexion)
        layout_haut.addWidget(self.bouton_historique)
        layout_haut.addWidget(self.label_statut)
        layout_haut.addStretch()
        layout_haut.addWidget(self.label_temps)
        layout_haut.addWidget(self.spin_temps)
        layout_haut.addWidget(self.bouton_mesure)

        # --- Graphique d'affichage PPG ---
        self.graphe_widget = pg.PlotWidget(title="Signal PPG Brut")
        self.graphe_widget.setLabel("left", "Amplitude (ADC)")
        self.graphe_widget.setLabel("bottom", "Échantillons")
        self.graphe_widget.showGrid(x=True, y=True, alpha=0.3)

        # Ajustement automatique de l'axe Y aux limites du signal (compense l'offset lumineux)
        self.graphe_widget.enableAutoRange(axis="y")
        self.graphe_widget.setAutoVisible(y=True)

        pen_medical = pg.mkPen(color=(0, 255, 0), width=2)  # Tracé vert de type scope médical
        self.courbe_ppg = self.graphe_widget.plot(self.donnees_y, pen=pen_medical)

        layout_principal.addLayout(layout_haut)
        layout_principal.addWidget(self.graphe_widget)
        widget_central.setLayout(layout_principal)

    def relancer_connexion(self):
        """Réinitialise proprement la communication USB."""
        self.label_statut.setText("Recherche de l'appareil...")
        self.label_statut.setStyleSheet("color: black;")
        self.bouton_mesure.setEnabled(False)

        if hasattr(self, "thread_materiel") and self.thread_materiel.isRunning():
            self.worker_serie.arreter()
            self.thread_materiel.quit()
            self.thread_materiel.wait()

        self.init_materiel()

    def init_materiel(self):
        """Instanciation du thread d'arrière-plan dédié à la liaison série."""
        self.thread_materiel = QThread()
        self.worker_serie = LecteurSerieWorker(baud_rate=115200)

        self.worker_serie.moveToThread(self.thread_materiel)
        self.thread_materiel.started.connect(self.worker_serie.run)
        self.worker_serie.donnee_recue.connect(self.mettre_a_jour_graphe)
        self.worker_serie.erreur_connexion.connect(self.afficher_erreur)

        self.thread_materiel.start()

        self.label_statut.setText("Connecté et en écoute...")
        self.label_statut.setStyleSheet("color: green;")
        self.bouton_mesure.setEnabled(True)

    def mettre_a_jour_graphe(self, nouvelle_valeur_adc):
        """Alimente le tampon de données et actualise la courbe en direct."""
        self.donnees_y[:-1] = self.donnees_y[1:]
        self.donnees_y[-1] = nouvelle_valeur_adc
        self.courbe_ppg.setData(self.donnees_y)

        if self.en_enregistrement:
            self.donnees_brutes_sauvegarde.append(nouvelle_valeur_adc)

    def ouvrir_historique(self):
        """Ouvre l'interface de gestion de l'historique de manière modale."""
        fenetre_hist = FenetreHistorique(self.gestionnaire_excel, self)
        fenetre_hist.exec()

    def lancer_enregistrement(self):
        """Verrouille l'IHM et lance la fenêtre d'observation chronométrée."""
        self.en_enregistrement = True
        self.donnees_brutes_sauvegarde = []

        self.duree_totale = self.spin_temps.value()
        self.temps_restant = self.duree_totale

        self.bouton_mesure.setEnabled(False)
        self.spin_temps.setEnabled(False)
        self.bouton_mesure.setStyleSheet("background-color: orange; color: black;")
        self.bouton_mesure.setText(f"⏳ Enregistrement... ({self.temps_restant}s)")

        self.timer_minuteur.start(1000)

    def tick_minuteur(self):
        """Décrémente le compte à rebours visuel à chaque tic de l'horloge."""
        self.temps_restant -= 1

        if self.temps_restant > 0:
            self.bouton_mesure.setText(f"⏳ Enregistrement... ({self.temps_restant}s)")
        else:
            self.timer_minuteur.stop()
            self.fin_enregistrement()

    def fin_enregistrement(self):
        """Clôture la mesure, lance le filtrage mathématique et enregistre le résultat."""
        self.en_enregistrement = False

        self.bouton_mesure.setEnabled(True)
        self.spin_temps.setEnabled(True)
        self.bouton_mesure.setText("🔴 Lancer une mesure")
        self.bouton_mesure.setStyleSheet("")

        bpm_final = TraitementPPG.calculer_bpm(
            self.donnees_brutes_sauvegarde, duree_secondes=self.duree_totale
        )

        fichier_cree = self.gestionnaire_excel.sauvegarder_mesure(
            self.donnees_brutes_sauvegarde, bpm_final, self.duree_totale
        )

        QMessageBox.information(
            self,
            "Analyse Terminée",
            f"Mesure de {self.duree_totale} secondes terminée.\n\n"
            f"♥ Rythme Cardiaque Moyen : {bpm_final} BPM\n\n"
            f"Les données ont été consignées dans le fichier :\n{fichier_cree}",
        )

    def afficher_erreur(self, message):
        """Affiche les anomalies de transmission série sur l'IHM."""
        self.label_statut.setText(f"Erreur : {message}")
        self.label_statut.setStyleSheet("color: red;")
        self.bouton_mesure.setEnabled(False)

    def closeEvent(self, event):
        """Sécurité d'arrêt : coupe les connexions d'arrière-plan à la fermeture."""
        if hasattr(self, "thread_materiel") and self.thread_materiel.isRunning():
            self.worker_serie.arreter()
            self.thread_materiel.quit()
            self.thread_materiel.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = MoniteurCardioApp()
    fenetre.show()
    sys.exit(app.exec())
