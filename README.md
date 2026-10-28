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

Beim Klick auf **Einstellungen -> Geräte & Dienste -> Integration hinzufügen -> "Tuya Local Lamp"** kannst du zwischen 3 Methoden wählen:

### 1. Methode: Tuya Cloud / Local Key Schnittstelle (Empfohlen & Automatisch)
1. Gib deine Tuya IoT API-Zugangsdaten ein:
   * **Region:** z. B. `Central Europe (eu)`
   * **Client ID & Client Secret:** Aus dem Tuya IoT Developer Portal
   * **Beliebige Geräte-ID:** Eine beliebige ID aus deiner Smart Life App
2. Home Assistant ruft im Hintergrund alle Geräte, Namen und **Local Keys** ab und scannt zeitgleich das lokale WLAN nach deren IP-Adressen.
3. Du erhältst eine **Auswahlliste aller gefundenen Lampen** (bereits hinzugefügte Lampen werden automatisch herausgefiltert).
4. Wähle die gewünschte Lampe aus -> alle Felder (IP, ID, Key, Name) werden automatisch vorausgefüllt -> Klick auf **Absenden**. Fertig!

### 2. Methode: Import aus devices.json / JSON-Text
Falls du bereits eine `devices.json` besitzt (z. B. aus dem `tinytuya wizard` oder dem beiliegenden `tuya_cloud_discover.py`):
1. Füge den JSON-Inhalt ein oder gib den Dateipfad an (`/config/devices.json`).
2. Home Assistant gleicht die IDs mit dem lokalen Netzwerk ab und zeigt dir die Übersicht zur Auswahl an.

### 3. Methode: Manuelle Eingabe
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
