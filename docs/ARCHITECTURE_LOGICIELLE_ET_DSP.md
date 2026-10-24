# Architecture Logicielle & Traitement Numérique du Signal (DSP)

## 1. Architecture Multithread Asynchrone

Afin de traiter un flux continu de données biomédicales ($50\text{ Hz}$ à $100\text{ Hz}$) sans perte d'échantillons ni gel de l'Interface Homme-Machine (IHM), l'application de bureau ([`src/main.py`](../src/main.py)) repose sur une architecture **Multithread découplée** basée sur `PyQt6` et `PyQtGraph`.

```mermaid
flowchart TD
    subgraph Materiel["Couche Embarquée (50 Hz)"]
        MCU["Arduino (UART USB) / ESP32 (USB & BLE)"]
        SIM["Simulateur Physiologique Interne (50 Hz)"]
    end

    subgraph WorkerThread["Thread Secondaire (QThread)"]
        LSW["LecteurSerieWorker (src/lecteur_serie.py)"]
    end

    subgraph MainThread["Thread Principal (GUI PyQt6)"]
        CB["Tampon Circulaire NumPy (500 points)"]
        PLOT["Oscilloscope Temps Réel (PyQtGraph + AutoRange Y)"]
        TIMER["Fenêtre Chronométrée (QTimer 10s - 120s)"]
    end

    subgraph Traitement["Analyse & Persistance"]
        DSP["TraitementPPG (src/traitement_signal.py)<br/>Filtre Butterworth Ordre 3 + find_peaks"]
        XLS["EnregistreurExcel (src/enregistreur_excel.py)<br/>Archivage Pandas (.xlsx) & Purge"]
    end

    MCU -->|"Trames Série (115200 bauds)"| LSW
    SIM -->|"Onde Synthétique"| LSW
    LSW -->|"pyqtSignal(int)"| CB
    CB --> PLOT
    CB -->|"Enregistrement actif"| TIMER
    TIMER -->|"Fin de fenêtre"| DSP
    DSP -->|"BPM + SDNN (HRV)"| XLS
```

### Rôles des composants logiciels
- **Thread d'Acquisition (`LecteurSerieWorker`) :** S'exécute en arrière-plan dans un `QThread` isolé. Il scanne automatiquement les ports COM (puces Arduino, ESP32, CH340, CP210x, FTDI), lit et valide chaque trame numérique et émet la valeur via le mécanisme thread-safe `pyqtSignal(int)`.
- **Tampon Circulaire (`Circular Buffer`) :** Un tableau NumPy de taille fixe ($500\text{ échantillons}$, soit $10\text{ s}$ d'affichage glissant à $50\text{ Hz}$) est décalé en mémoire vive sans allocation dynamique coûteuse, garantissant une empreinte RAM constante.
- **Compensation automatique d'offset (`enableAutoRange(axis='y')`) :** La composante continue (DC) induite par la lumière ambiante est automatiquement compensée à l'écran par un cadrage vertical dynamique centré sur l'amplitude crête-à-crête de l'onde pulsatile (AC).

---

## 2. Pipeline de Traitement Numérique du Signal ([`src/traitement_signal.py`](../src/traitement_signal.py))

Lorsqu'une mesure chronométrée ($10\text{ s}$ à $120\text{ s}$) s'achève, le vecteur d'échantillons bruts est transmis au pipeline mathématique `TraitementPPG.analyser_signal()` :

### Étape 1 : Estimation dynamique de la fréquence d'échantillonnage ($F_e$)
Pour rendre l'algorithme insensible à la gigue (jitter) du port série ou du système d'exploitation, la fréquence d'échantillonnage réelle est recalculée sur chaque fenêtre capturée :

$$F_e = \frac{N_{\text{échantillons}}}{T_{\text{mesure}}} \quad \text{et} \quad F_{\text{Nyquist}} = \frac{F_e}{2}$$

### Étape 2 : Filtrage passe-bande de Butterworth à phase nulle
Le signal PPG brut est entaché de deux types de bruits :
- **Basses fréquences ($< 0{,}5\text{ Hz}$) :** Dérive thermique du capteur, mouvements lents et modulation respiratoire de la ligne de base.
- **Hautes fréquences ($> 4{,}0\text{ Hz}$) :** Bruit électromagnétique du secteur ($50\text{ Hz}$) et bruit de quantification ADC.

Un **filtre numérique passe-bande de Butterworth d'ordre 3** est synthétisé sur la bande passante physiologique $[0{,}5\text{ Hz} \,;\, 4{,}0\text{ Hz}]$, correspondant exactement à une plage cardiaque de **$30\text{ BPM}$ à $240\text{ BPM}$**.
L'application du filtre de manière bidirectionnelle via `scipy.signal.filtfilt` garantit un **déphasage nul (Zero-Phase Filtering)**, préservant la position temporelle exacte des pics systoliques.

### Étape 3 : Détection topologique adaptative des pics et calcul BPM / HRV
La fonction `scipy.signal.find_peaks` identifie les sommets systoliques selon deux critères physiologiques et statistiques :
1. **Période réfractaire minimale ($d_{\min}$) :**

$$d_{\min} = 0{,}3\text{ s} \times F_e$$

Empêche la double détection de l'onde dicrote située sur la pente diastolique (plafonne la détection parasite au-delà de $200\text{ BPM}$).
2. **Proéminence adaptative ($P_{\min}$) :**

$$P_{\min} = 0{,}5 \times \sigma_{\text{filtré}}$$

Où $\sigma_{\text{filtré}}$ est l'écart-type du signal filtré, permettant au détecteur de s'adapter automatiquement à l'amplitude optique propre à chaque patient.

Le rythme cardiaque moyen ($\text{BPM}$) et la variabilité de la fréquence cardiaque ($\text{SDNN}$ en millisecondes, calculée sur les intervalles inter-battements $\Delta t_i$) sont alors extraits :

$$\text{BPM} = N_{\text{pics}} \times \frac{60}{T_{\text{mesure}}} \quad ; \quad \text{SDNN} = \sigma(\Delta t_i) \times 1000$$

---

## 3. Analyse Fonctionnelle FAST (Extension BLE & Web App)

Pour la déclinaison sans fil sur ESP32 ([`firmware/esp32_ble_ppg/`](../firmware/esp32_ble_ppg/)) et son client Web ([`web_ble/index.html`](../web_ble/index.html)) :

| Fonction Technique (Pourquoi ?) | Solution Constructive Retenue (Comment ?) |
| :--- | :--- |
| **FT1 : Assurer une connectivité immédiate sans configuration réseau** | Protocole **Bluetooth Low Energy (BLE)** via le profil standard *Nordic UART Service (NUS)*. |
| **FT2 : Garantir une compatibilité multiplateforme (PC & Mobile)** | Interface **Web App HTML5/Canvas** exploitant l'API native `navigator.bluetooth` (Web Bluetooth). |
| **FT3 : Minimiser la consommation énergétique embarquée** | Découplage **Edge-Client** : l'ESP32 échantillonne à $12\text{ bits}$ ($50\text{ Hz}$) et notifie les trames brutes ; le terminal client assure l'affichage et le traitement. |
| **FT4 : Assurer la traçabilité clinique et l'intégrité des mesures** | Archivage tabulaire automatisé sous `pandas` / `openpyxl` avec interface modale de consultation et de purge des mesures aberrantes. |
