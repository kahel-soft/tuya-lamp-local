<p align="center">
  <img src="https://raw.githubusercontent.com/kahel-soft/tuya-lamp-local/main/custom_components/tuya_lamp_local/brand/logo.png" width="160" alt="Tuya Local Lamp Logo">
</p>

# Tuya Local Lamp für Home Assistant (inkl. Home Assistant Green)

Eine leichtgewichtige, 100 % lokale Home Assistant Integration (`custom_component`) zur direkten Steuerung von Tuya Smart Wi-Fi Lampen im Heimnetzwerk – **ohne Cloud, ohne Latenz und ohne externe Server/Zweitmaschinen**. Entwickelt für und vollständig kompatibel mit **Home Assistant Green** (Home Assistant OS).

---

## 🌟 Highlights & Funktionen

* **100 % Lokale Steuerung:** Direkte Kommunikation via TCP Port 6668 im lokalen WLAN. Funktioniert auch bei vollständigem Internetausfall.
* **Automatische Geräteerkennung & Local Key Abruf:** Schnittstelle zur Tuya Cloud API, die alle Geräte, Namen, IDs und Local Keys automatisch abruft und mit den lokalen WLAN-IPs abgleicht.
* **Übersichtliche Geräteauswahl:** Liste aller gefundenen Geräte im Home Assistant Webinterface – du wählst einfach per Mausklick aus, welche Lampe übernommen werden soll.
* **Optimiert für Home Assistant Green (HOAS):** Keine separate Maschine, kein Docker-Sidecar, kein Node-RED oder MQTT-Broker nötig. Läuft direkt nativ im Core-Container des Green.
* **Auto-Detection der Lampenfunktionen:** Erkennt beim ersten Verbindungsaufbau automatisch, ob es sich um eine reine Dimm-Lampe, Farbtemperatur-Lampe (CCT) oder RGB/RGBCW-Lampe handelt.
* **Single-Socket Lock & Schutz:** Verhindert das Einfrieren der Tuya-WLAN-Firmware durch thread-sichere Socket-Verwaltung.
* **Unterstützt Tuya Protokolle 3.1, 3.3, 3.4 und 3.5:** Inklusive AES-GCM und Session-Key Handshake.

---

## ⚙️ Lampe in Home Assistant einbinden (Webinterface)

Beim Klick auf **Einstellungen -> Geräte & Dienste -> Integration hinzufügen -> "Tuya Local Lamp"** wählst du deine bevorzugte Methode:

### 1. Methode: Tuya Local Key Add-on (Server-URL) – Am einfachsten!
Wenn das Add-on *Tuya Local Key* auf deinem Home Assistant Server läuft:
1. Wähle **Tuya Local Key Add-on (Automatisch über Server-URL)**.
2. Das Feld ist bereits mit `http://localhost:8000` vorausgefüllt.
3. Klicke einfach auf **Absenden** – die Integration ruft alle Lampen ab und zeigt dir die Auswahlliste!

### 2. Methode: Raw JSON einfügen (aus Tuya Local Key kopiert)
Falls du keinen lokalen Port nutzt:
1. Öffne das *Tuya Local Key* Add-on und klicke bei deiner Lampe auf **Raw JSON** -> **Copy**.
2. Wähle **Raw JSON einfügen** und füge den Text in das Textfeld ein.
3. Klicke auf **Absenden** – alle Lampen werden sofort erkannt und zur Auswahl aufgelistet!

### 3. Methode: Tuya IoT Developer Cloud (iot.tuya.com)
Direkte Abfrage über das Tuya Entwicklerkonto (Region, Client ID & Secret).

### 4. Methode: Manuelle Direkteingabe
Direkteingabe von IP, Device ID und Local Key für einzelne Lampen.

### 5. Nachträgliches Anpassen & DP-Konfiguration (Options Flow)
Über das Zahnrad / **Konfigurieren** im Dashboard kannst du jederzeit zwei Bereiche anpassen:
* **Netzwerk & Verbindung:** IP-Adresse, Local Key, Protokollversion oder Abfrageintervall ändern.
* **Datenpunkte & Grenzwerte (DPs):**
  * Zeigt die **aktuellen Live-Werte der Lampe** direkt an (z. B. `DP 20: True | DP 21: white | DP 22: 1000 | ...`).
  * **Power-DP:** Zuordnung des Ein/Aus-Schalters (z. B. 20 oder 1).
  * **Helligkeits-DP & Grenzwerte:** DP für Dimmer (z. B. 22 oder 3) sowie Mindest- und Maximalwert (z. B. 10 bis 1000 oder 255).
  * **Farbtemperatur-DP (CCT):** DP für Weißtöne (z. B. 23 oder 4), Grenzwerte (0 bis 1000), Kelvin-Bereich (2700K - 6500K) und Option zum **Invertieren** (Kalt/Warm umkehren).
  * **Farb-DP & Codierung:** DP für RGB/HSV (z. B. 24 oder 5) und Format (12-stelliges HSV-Hex oder 6-stelliges RGB-Hex).
  * **Modus-DP:** Betriebsmodus (z. B. 21 oder 2).

---

## 🧪 Vorab-Schnelltest direkt am PC (Optional)

Falls du deine Zugangsdaten und die Lampe vorab ohne Home Assistant testen möchtest, kannst du das beiliegende Python-Skript starten:
```bash
python test_lamp.py
```
Das Skript fragt IP, ID und Key ab, ermittelt automatisch die funktionierende Protokollversion (3.3/3.4/3.5) und schaltet die Lampe kurz testweise ein und aus.

---

## 📁 Dateistruktur

```
custom_components/tuya_lamp_local/
├── __init__.py           # Setup & Lifecycle Management
├── manifest.json         # Metadaten & PyPI-Abhängigkeit (tinytuya)
├── const.py              # DP-Mappings, Farbraum- & Werteumrechnungen
├── coordinator.py        # DataUpdateCoordinator mit Socket-Lock & Auto-Detection
├── light.py              # Home Assistant LightEntity Plattform
├── config_flow.py        # UI-Konfigurationsassistent & Verbindungstest
├── strings.json          # Basistexte
└── translations/
    ├── de.json           # Deutsche Übersetzung
    └── en.json           # Englische Übersetzung
```
