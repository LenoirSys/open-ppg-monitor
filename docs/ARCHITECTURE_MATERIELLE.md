# Architecture Matérielle & Instrumentation Biomédicale

## 1. Principe Physique de la Photopléthysmographie (PPG)

La **photopléthysmographie (PPG)** est une méthode optique non invasive permettant de détecter les variations volumétriques du sang dans le réseau microvasculaire périphérique (doigt ou lobe de l'oreille).

À chaque contraction ventriculaire (**systole**), l'onde de pression sanguine dilate localement les artérioles et capillaires cutanés, augmentant l'absorption lumineuse du tissu. Lors du relâchement cardiaque (**diastole**), le volume sanguin diminue et la transmission lumineuse augmente. Entre ces deux phases, la fermeture de la valve aortique produit une légère inflexion secondaire sur la pente descendante appelée **onde dicrote**.

---

## 2. Chaîne d'Acquisition Instrumentale

Le dispositif suit une architecture de chaîne d'acquisition industrielle découpée en 5 étages fonctionnels :

```mermaid
flowchart LR
    A["Phénomène Physiologique<br/>(Onde de pouls artériel)"] --> B["Transducteur Optique<br/>(LED Rouge + LDR)"]
    B --> C["Conditionnement<br/>(Amplificateur Opérationnel)"]
    C --> D["Numérisation CAN/ADC<br/>(Arduino 10-bit / ESP32 12-bit)"]
    D --> E["Transmission Série / BLE<br/>(UART 115200 bauds / NUS)"]
    E --> F["Supervision & DSP<br/>(Application Python / Web)"]
```

1. **Émission optique :** Une LED rouge ($\lambda \approx 660\text{ nm}$), polarisée en série avec une résistance de limitation de $220\,\Omega$, génère un flux lumineux constant à travers le tissu biologique.
2. **Transduction photosensible :** Une photorésistance (**LDR**) capte l'intensité lumineuse transmise ou réfléchie. Sa résistance électrique varie de manière inversement proportionnelle à l'éclairement reçu.
3. **Étage de conditionnement (AOP) :** Le pont diviseur associé à un amplificateur opérationnel convertit la variation d'impédance en une tension analogique exploitable et abaisse l'impédance de sortie avant l'entrée du convertisseur analogique-numérique.
4. **Numérisation (ADC) :** Le microcontrôleur échantillonne le signal à une fréquence stricte de $F_e = 50\text{ Hz}$ (une mesure toutes les $20\text{ ms}$), respectant largement le théorème de Shannon-Nyquist pour les composantes fondamentales du rythme cardiaque humain ($0{,}5\text{ Hz}$ à $4{,}0\text{ Hz}$).

---

## 3. Câblage et Affectation des Entrées/Sorties

| Composant source | Broche | Destination Arduino (Uno/Mega) | Destination ESP32 | Description / Rôle du signal |
| :--- | :---: | :---: | :---: | :--- |
| **Module LDR** | `VCC` | `5V` | `3.3V` | Alimentation positive du module et de l'AOP |
| **Module LDR** | `GND` | `GND` | `GND` | Masse commune du circuit ($0\text{ V}$ de référence) |
| **Module LDR** | `AO` (Analog Out) | `A0` | `GPIO 34` | Entrée du convertisseur analogique-numérique (ADC) |
| **LED d'éclairage** | `Anode (+)` | `5V` ou `3.3V` | `3.3V` | Source lumineuse continue de traversée tissulaire |
| **LED d'éclairage** | `Cathode (-)` | `GND` (via $220\,\Omega$) | `GND` (via $220\,\Omega$) | Retour de masse via une résistance de protection de $220\,\Omega$ |

---

## 4. Étude Comparative de Quantification : Arduino (10 bits) vs ESP32 (12 bits)

La finesse de restitution de l'onde pulsatile dépend directement du pas de quantification $q$ du convertisseur analogique-numérique (ADC), défini par :

$$q = \frac{V_{\text{ref}}}{2^N}$$

où $V_{\text{ref}}$ est la tension pleine échelle et $N$ la résolution en bits du convertisseur.

| Caractéristique | Arduino (Uno / Mega) | ESP32 | Gain technique |
| :--- | :---: | :---: | :--- |
| **Tension de référence ($V_{\text{ref}}$)** | $5{,}0\text{ V}$ | $3{,}3\text{ V}$ | Consommation énergétique réduite |
| **Résolution ADC ($N$)** | $10\text{ bits}$ ($1\,024\text{ niveaux}$) | $12\text{ bits}$ ($4\,096\text{ niveaux}$) | $4\times$ plus de niveaux logiques |
| **Pas de quantification ($q$)** | $\approx 4{,}88\text{ mV}$ | $\approx 0{,}81\text{ mV}$ | **Précision accrue d'un facteur $\approx 6\times$** |
| **Connectivité native** | UART sur USB uniquement | USB + Wi-Fi + Bluetooth Low Energy (BLE) | Télémédecine sans fil & Web App |
| **Fréquence CPU** | $16\text{ MHz}$ (8 bits) | $240\text{ MHz}$ Dual-Core (32 bits) | Capacité de filtrage embarqué (Edge DSP) |

Cette amélioration de la résolution sur ESP32 réduit fortement le bruit de quantification (« effet d'escalier ») lorsque la composante pulsatile utile (AC) est de faible amplitude face à la composante continue (DC) liée aux tissus et à la lumière ambiante.

---

## 5. Perspectives Mécaniques et Étanchéité Optique

La qualité du signal PPG acquis par une photorésistance (LDR) est sensible à deux perturbations physiques majeures :
1. **L'offset optique ambiant :** La lumière extérieure décale le point de fonctionnement de la LDR vers la saturation.
2. **Les artéfacts de mouvement :** Tout glissement ou variation de pression mécanique du doigt modifie brusquement le trajet optique.

Pour stabiliser la mesure en conditions cliniques :
- La cellule optique (LED + LDR) doit être logée dans une pince de doigt ou d'oreille opaque exerçant une pression constante mais non occlusive sur le réseau capillaire.
- Un revêtement intérieur sombre et antidérapant (mousse ou silicone noir) permet d'isoler la LDR de la lumière ambiante parasite et de limiter les artéfacts de mouvement.
