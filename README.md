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

Beim Klick auf **Einstellungen -> Geräte & Dienste -> Integration hinzufügen -> "Tuya Local Lamp"** kannst du zwischen folgenden Methoden wählen:

### 1. Methode: Aus 'Tuya Local Key' Add-on (Empfohlen bei Nutzung des Add-ons)
Wenn du das beliebte Home Assistant Add-on **Tuya Local Key** (von Vineet Choudhary / QR-Code Login) nutzt:
* **Option A (Automatisch per Server-URL):** Gib die lokale URL des Add-ons ein (Standard ist `http://localhost:8000`). Die Integration ruft die Geräteliste direkt per API ab.
* **Option B (Copy & Paste):** Öffne dein *Tuya Local Key* Add-on, klicke beim gewünschten Gerät (oder in der Detailansicht) auf **Raw JSON** / **Copy**, und füge den Text direkt in das Feld *Raw JSON* ein.
* **Ergebnis:** Home Assistant erkennt sofort alle Lampen samt Name, Device ID und 16-stelligem **Local Key** und gleicht zeitgleich die WLAN-IPs ab. Du wählst die Lampe einfach aus der Liste aus!

### 2. Methode: Tuya IoT Developer Cloud (iot.tuya.com)
Falls du ein Entwicklerkonto auf `iot.tuya.com` nutzt:
* Trage Region (`Central Europe`), Client ID, Client Secret und eine Geräte-ID ein.
* Home Assistant holt die Schlüssel direkt über die Tuya Cloud API ab.

### 3. Methode: Manuelle Direkteingabe
Direkte Eingabe von Name, IP, Device ID und Local Key für einzelne Lampen.

### 4. Nachträgliches Anpassen (Options Flow)
Über das Zahnrad / **Konfigurieren** im Dashboard kannst du jederzeit IP-Adressen, Local Keys, Abfrageintervalle oder Farbtemperatur-Grenzwerte im laufenden Betrieb verändern.

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
