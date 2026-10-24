"""
Interface Homme-Machine (IHM) de monitoring cardiaque par Photopléthysmographie (PPG).

Application de bureau multithread sous PyQt6 et PyQtGraph permettant :
- L'acquisition temps réel sur port série USB (Arduino / ESP32) ou en Mode Simulation
- L'affichage fluide du tracé PPG sur tampon circulaire (Circular Buffer)
- Le filtrage numérique de Butterworth et le calcul du BPM / HRV (SDNN)
- La gestion et l'archivage de l'historique dans un classeur Excel
"""

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
    QComboBox,
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
    Fenêtre modale permettant de visualiser l'historique des mesures
    et de supprimer des enregistrements erronés du fichier Excel.
    """

    def __init__(self, gestionnaire_excel: EnregistreurExcel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historique des Mesures Cliniques")
        self.resize(700, 420)
        self.gestionnaire_excel = gestionnaire_excel

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.btn_supprimer = QPushButton("🗑️ Supprimer la mesure sélectionnée")
        self.btn_supprimer.setStyleSheet(
            "background-color: #d9534f; color: white; font-weight: bold; padding: 8px; border-radius: 4px;"
        )
        self.btn_supprimer.clicked.connect(self.supprimer_selection)
        layout.addWidget(self.btn_supprimer)

        self.charger_table()

    def charger_table(self) -> None:
        """Lit le fichier Excel et injecte les données dans le tableau PyQt6."""
        df = self.gestionnaire_excel.charger_donnees()

        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns) if not df.empty else 0)

        if not df.empty:
            self.table.setHorizontalHeaderLabels([str(c) for c in df.columns])
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

    def supprimer_selection(self) -> None:
        """Supprime la ligne sélectionnée après confirmation de l'opérateur."""
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
    Fenêtre principale de l'application de monitoring biomédical PPG.
    Gère l'IHM, le thread d'acquisition et les déclenchements de mesure.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Moniteur PPG Temps Réel - Instrumentation Biomédicale")
        self.resize(1050, 640)

        # Tampon circulaire pour l'affichage continu (500 points = 10 secondes à 50 Hz)
        self.taille_fenetre = 500
        self.donnees_y = np.zeros(self.taille_fenetre)

        # Variables d'état pour la capture de données
        self.en_enregistrement = False
        self.donnees_brutes_sauvegarde = []
        self.gestionnaire_excel = EnregistreurExcel()

        # Minuteur pour le compte à rebours visuel (1 seconde)
        self.temps_restant = 0
        self.duree_totale = 0
        self.timer_minuteur = QTimer()
        self.timer_minuteur.timeout.connect(self.tick_minuteur)

        self.init_interface()
        self.actualiser_liste_ports()
        self.init_materiel()

    def init_interface(self) -> None:
        """Définition et agencement des composants graphiques de l'application."""
        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QVBoxLayout()

        # --- Barre d'outils supérieure ---
        layout_haut = QHBoxLayout()

        self.combo_source = QComboBox()
        self.combo_source.setMinimumWidth(190)
        self.combo_source.setFont(QFont("Arial", 10))
        self.combo_source.currentIndexChanged.connect(self.relancer_connexion)

        self.bouton_reconnexion = QPushButton("🔄 Actualiser / Connecter")
        self.bouton_reconnexion.clicked.connect(self.rafraichir_et_reconnecter)

        self.bouton_historique = QPushButton("📂 Historique")
        self.bouton_historique.clicked.connect(self.ouvrir_historique)

        self.label_statut = QLabel("Statut : Démarrage...")
        self.label_statut.setFont(QFont("Arial", 10))

        self.label_temps = QLabel("Durée (s) :")
        self.label_temps.setFont(QFont("Arial", 11))

        self.spin_temps = QSpinBox()
        self.spin_temps.setRange(10, 120)
        self.spin_temps.setValue(30)
        self.spin_temps.setFont(QFont("Arial", 11))

        self.bouton_mesure = QPushButton("🔴 Lancer une mesure")
        self.bouton_mesure.setFont(QFont("Arial", 11))
        self.bouton_mesure.setMinimumHeight(38)
        self.bouton_mesure.setEnabled(False)
        self.bouton_mesure.clicked.connect(self.lancer_enregistrement)

        layout_haut.addWidget(QLabel("Source :"))
        layout_haut.addWidget(self.combo_source)
        layout_haut.addWidget(self.bouton_reconnexion)
        layout_haut.addWidget(self.bouton_historique)
        layout_haut.addWidget(self.label_statut)
        layout_haut.addStretch()
        layout_haut.addWidget(self.label_temps)
        layout_haut.addWidget(self.spin_temps)
        layout_haut.addWidget(self.bouton_mesure)

        # --- Graphique d'affichage PPG ---
        self.graphe_widget = pg.PlotWidget(title="Signal Photopléthysmographique (PPG) Temps Réel")
        self.graphe_widget.setLabel("left", "Amplitude (ADC)")
        self.graphe_widget.setLabel("bottom", "Échantillons (Tampon glissant de 500 points)")
        self.graphe_widget.showGrid(x=True, y=True, alpha=0.3)

        # Mise à l'échelle verticale automatique pour compenser l'offset de lumière ambiante
        self.graphe_widget.enableAutoRange(axis="y")
        self.graphe_widget.setAutoVisible(y=True)

        pen_medical = pg.mkPen(color=(0, 230, 118), width=2)
        self.courbe_ppg = self.graphe_widget.plot(self.donnees_y, pen=pen_medical)

        layout_principal.addLayout(layout_haut)
        layout_principal.addWidget(self.graphe_widget)
        widget_central.setLayout(layout_principal)

    def actualiser_liste_ports(self) -> None:
        """Met à jour la liste déroulante des sources d'acquisition (USB Auto, Ports COM, Simulation)."""
        self.combo_source.blockSignals(True)
        selection_actuelle = self.combo_source.currentData()
        self.combo_source.clear()

        self.combo_source.addItem("🔌 Auto-détection USB", None)
        for port in LecteurSerieWorker.lister_ports_disponibles():
            self.combo_source.addItem(f" Port {port}", port)
        self.combo_source.addItem("🧪 Mode Simulation (Démo 50 Hz)", "SIMULATION")

        if selection_actuelle is not None:
            index = self.combo_source.findData(selection_actuelle)
            if index >= 0:
                self.combo_source.setCurrentIndex(index)
        self.combo_source.blockSignals(False)

    def rafraichir_et_reconnecter(self) -> None:
        """Rafraîchit la liste des ports COM puis relance la connexion."""
        self.actualiser_liste_ports()
        self.relancer_connexion()

    def relancer_connexion(self) -> None:
        """Réinitialise proprement le thread d'acquisition et connecte la source choisie."""
        self.label_statut.setText("Recherche de l'appareil...")
        self.label_statut.setStyleSheet("color: #333333;")
        self.bouton_mesure.setEnabled(False)

        if hasattr(self, "thread_materiel") and self.thread_materiel.isRunning():
            self.worker_serie.arreter()
            self.thread_materiel.quit()
            self.thread_materiel.wait()

        self.donnees_y = np.zeros(self.taille_fenetre)
        self.courbe_ppg.setData(self.donnees_y)
        self.init_materiel()

    def init_materiel(self) -> None:
        """Instancie et démarre le QThread dédié à l'acquisition série ou simulée."""
        port_selectionne = self.combo_source.currentData()

        self.thread_materiel = QThread()
        self.worker_serie = LecteurSerieWorker(
            baud_rate=115200, port_force=port_selectionne
        )

        self.worker_serie.moveToThread(self.thread_materiel)
        self.thread_materiel.started.connect(self.worker_serie.run)
        self.worker_serie.donnee_recue.connect(self.mettre_a_jour_graphe)
        self.worker_serie.erreur_connexion.connect(self.afficher_erreur)

        self.thread_materiel.start()

        if port_selectionne == "SIMULATION":
            self.label_statut.setText("Statut : Mode Simulation actif (50 Hz)")
            self.label_statut.setStyleSheet("color: #0275d8; font-weight: bold;")
        else:
            self.label_statut.setText("Statut : Connecté et en écoute...")
            self.label_statut.setStyleSheet("color: #28a745; font-weight: bold;")
        self.bouton_mesure.setEnabled(True)

    def mettre_a_jour_graphe(self, nouvelle_valeur_adc: int) -> None:
        """Alimente le tampon circulaire et rafraîchit la courbe en temps réel."""
        self.donnees_y[:-1] = self.donnees_y[1:]
        self.donnees_y[-1] = nouvelle_valeur_adc
        self.courbe_ppg.setData(self.donnees_y)

        if self.en_enregistrement:
            self.donnees_brutes_sauvegarde.append(nouvelle_valeur_adc)

    def ouvrir_historique(self) -> None:
        """Ouvre la boîte de dialogue de consultation et de purge de l'historique."""
        fenetre_hist = FenetreHistorique(self.gestionnaire_excel, self)
        fenetre_hist.exec()

    def lancer_enregistrement(self) -> None:
        """Verrouille les contrôles et démarre l'acquisition chronométrée."""
        self.en_enregistrement = True
        self.donnees_brutes_sauvegarde = []

        self.duree_totale = self.spin_temps.value()
        self.temps_restant = self.duree_totale

        self.bouton_mesure.setEnabled(False)
        self.spin_temps.setEnabled(False)
        self.combo_source.setEnabled(False)
        self.bouton_mesure.setStyleSheet("background-color: #f0ad4e; color: black; font-weight: bold;")
        self.bouton_mesure.setText(f"⏳ Enregistrement... ({self.temps_restant}s)")

        self.timer_minuteur.start(1000)

    def tick_minuteur(self) -> None:
        """Décrémente le compte à rebours visuel chaque seconde."""
        self.temps_restant -= 1

        if self.temps_restant > 0:
            self.bouton_mesure.setText(f"⏳ Enregistrement... ({self.temps_restant}s)")
        else:
            self.timer_minuteur.stop()
            self.fin_enregistrement()

    def fin_enregistrement(self) -> None:
        """Clôture la mesure, exécute le filtrage de Butterworth et archive le résultat."""
        self.en_enregistrement = False

        self.bouton_mesure.setEnabled(True)
        self.spin_temps.setEnabled(True)
        self.combo_source.setEnabled(True)
        self.bouton_mesure.setText("🔴 Lancer une mesure")
        self.bouton_mesure.setStyleSheet("")

        resultat = TraitementPPG.analyser_signal(
            self.donnees_brutes_sauvegarde, duree_secondes=self.duree_totale
        )
        bpm_final = resultat["bpm"]
        sdnn_ms = resultat["sdnn_ms"]

        fichier_cree = self.gestionnaire_excel.sauvegarder_mesure(
            self.donnees_brutes_sauvegarde,
            bpm_final,
            self.duree_totale,
            sdnn_ms=sdnn_ms,
        )

        details_hrv = f"📊 Variabilité (SDNN) : {sdnn_ms} ms\n" if sdnn_ms is not None else ""
        QMessageBox.information(
            self,
            "Analyse Terminée",
            f"Mesure de {self.duree_totale} secondes terminée ({resultat['fs']} Hz).\n\n"
            f"♥ Rythme Cardiaque Moyen : {bpm_final} BPM\n"
            f"{details_hrv}\n"
            f"Données consignées dans :\n{fichier_cree}",
        )

    def afficher_erreur(self, message: str) -> None:
        """Affiche les anomalies de connexion série sur la barre d'état."""
        self.label_statut.setText(f"Erreur : {message}")
        self.label_statut.setStyleSheet("color: #d9534f; font-weight: bold;")
        self.bouton_mesure.setEnabled(False)

    def closeEvent(self, event) -> None:
        """Coupe proprement le thread d'acquisition à la fermeture de l'application."""
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
