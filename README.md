# Tuya Local Lamp für Home Assistant (inkl. Home Assistant Green)

Eine leichtgewichtige, 100 % lokale Home Assistant Integration (`custom_component`) zur direkten Steuerung von Tuya Smart Wi-Fi Lampen im Heimnetzwerk – **ohne Cloud, ohne Latenz und ohne externe Server/Zweitmaschinen**. Entwickelt für und vollständig kompatibel mit **Home Assistant Green** (Home Assistant OS).

---

## 🌟 Highlights & Funktionen

* **100 % Lokale Steuerung:** Direkte Kommunikation via TCP Port 6668 im lokalen WLAN. Funktioniert auch bei vollständigem Internetausfall.
* **Optimiert für Home Assistant Green (HOAS):** Keine separate Maschine, kein Docker-Sidecar, kein Node-RED oder MQTT-Broker nötig. Läuft direkt nativ im Core-Container des Green.
* **Auto-Detection der Lampenfunktionen:** Erkennt beim ersten Verbindungsaufbau automatisch, ob es sich um eine reine Dimm-Lampe, Farbtemperatur-Lampe (CCT) oder RGB/RGBCW-Lampe handelt.
* **Single-Socket Lock & Schutz:** Verhindert das Einfrieren der Tuya-WLAN-Firmware durch thread-sichere Socket-Verwaltung.
* **Unterstützt Tuya Protokolle 3.1, 3.3, 3.4 und 3.5:** Inklusive AES-GCM und Session-Key Handshake.
* **Einfache UI-Konfiguration:** Nur IP-Adresse, Device ID und Local Key eingeben – kein manuelles Datapoint-Raten.

---

## 🚀 Installation auf Home Assistant Green

### Methode 1: Über HACS (Home Assistant Community Store) – Empfohlen
1. Öffne **HACS** in deinem Home Assistant Webinterface.
2. Klicke oben rechts auf das Dreipunkt-Menü und wähle **Benutzerdefinierte Repositories (Custom repositories)**.
3. Trage als Repository-URL ein:
   ```
   https://github.com/kahel-soft/tuya-lamp-local
   ```
4. Wähle als Kategorie: **Integration**.
5. Klicke auf **Hinzufügen**, suche nach **Tuya Local Lamp** und klicke auf **Herunterladen**.
6. Starte Home Assistant neu (*Entwicklerwerkzeuge -> YAML -> Neu starten*).

### Methode 2: Manuell über das "Samba Share" Add-on
1. Installiere auf deinem HA Green das Add-on **Samba share** (*Einstellungen -> Add-ons -> Add-on Store -> Samba share*).
2. Öffne den Netzwerkordner deines HA Green im Windows Explorer (z. B. `\\homeassistant.local\config`).
3. Erstelle im Ordner `config` den Unterordner `custom_components`, falls er noch nicht existiert.
4. Kopiere den Ordner `tuya_lamp_local` aus diesem Projekt vollständig nach:
   ```
   config/custom_components/tuya_lamp_local/
   ```
5. Starte Home Assistant neu (*Entwicklerwerkzeuge -> YAML -> Neu starten*).

### Methode 3: Über das "Terminal & SSH" Add-on
1. Öffne das Terminal in Home Assistant.
2. Wechsle in den Konfigurationsordner:
   ```bash
   cd /config/custom_components
   ```
3. Kopiere den Ordner `tuya_lamp_local` hierhin.
4. Starte Home Assistant neu.

---

## 🔑 Woher bekomme ich den `local_key`?

Jede Tuya-Lampe benötigt für die lokale AES-Verschlüsselung einen 16-stelligen `local_key`. Dieser ändert sich nur, wenn die Lampe aus der App entfernt oder zurückgesetzt wird.

### Option A: Über TinyTuya Wizard (Schnell & Zuverlässig)
Auf deinem Windows-PC (in einem PowerShell-Terminal):
```bash
pip install tinytuya
python -m tinytuya wizard
```
Der interaktive Assistent führt dich durch das Einbinden deiner Tuya-App-Zugangsdaten und gibt dir eine Tabelle aller Geräte mit **Name**, **IP-Adresse**, **Device ID** und **Local Key** aus.

### Option B: Über die Tuya IoT Plattform
1. Erstelle ein kostenloses Entwicklerkonto auf [iot.tuya.com](https://iot.tuya.com/).
2. Verknüpfe deine *Smart Life* oder *Tuya Smart* App unter **Cloud -> Development -> Link Tuya App Account**.
3. Unter **Cloud -> API Explorer -> Smart Home Device System -> Device Control -> Get Device Details** kannst du mit der Geräte-ID den zugehörigen `local_key` direkt abrufen.

---

## ⚙️ Lampe in Home Assistant einbinden (Webinterface)

### 1. Ersteinrichtung (Config Flow)
1. Gehe in Home Assistant auf **Einstellungen -> Geräte & Dienste**.
2. Klicke unten rechts auf **Integration hinzufügen**.
3. Suche nach **Tuya Local Lamp**.
4. Es öffnet sich das Web-Formular mit folgenden Eingabefeldern:
   * **Eigener Name (Optional):** z. B. `Wohnzimmer Stehlampe`
   * **IP-Adresse:** Lokale IP der Lampe (z. B. `192.168.1.120`)
   * **Geräte-ID (Device ID):** z. B. `bf1234567890abcdef`
   * **Lokaler Schlüssel (Local Key):** 16-stelliger Schlüssel
   * **Protokollversion:** Dropdown mit Auswahl `auto` (empfohlen), `3.3`, `3.4`, `3.5` oder `3.1`
   * **Abfrageintervall:** Standard 15 Sekunden (einstellbar von 5 bis 120 Sekunden)
5. Klicke auf **Absenden**. Die Integration führt direkt im Hintergrund einen Verbindungstest durch. War dieser erfolgreich, wird die Lampe sofort als Entität angelegt.

### 2. Nachträgliches Anpassen (Options Flow)
Wenn sich die IP-Adresse ändert, der Local Key nach einem Re-Pairing erneuert wurde oder du Farbtemperatur-Grenzwerte anpassen möchtest:
1. Gehe auf **Einstellungen -> Geräte & Dienste -> Tuya Local Lamp**.
2. Klicke auf das Zahnrad / **Konfigurieren**.
3. Hier kannst du im Webinterface:
   * IP-Adresse und Local Key aktualisieren
   * Das Abfrageintervall verändern
   * Minimale und maximale Farbtemperatur (Kelvin) feinjustieren
   * Optionale Datapoint-Overrides eintragen, falls eine Lampe vom Tuya-Standard abweicht

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
