<p align="center">
  <img src="https://raw.githubusercontent.com/kahel-soft/tuya-lamp-local/main/custom_components/tuya_lamp_local/brand/logo.png" width="160" alt="Tuya Local Lamp Logo">
</p>

# Tuya Local Lamp für Home Assistant (inkl. Home Assistant Green)

Eine leichtgewichtige, 100 % lokale Home Assistant Integration (`custom_component`) zur direkten Steuerung von Tuya Smart Wi-Fi Lampen im Heimnetzwerk – **ohne Cloud, ohne Latenz und ohne externe Server/Zweitmaschinen**. Entwickelt für und vollständig kompatibel mit **Home Assistant Green** (Home Assistant OS).

---

## 🌟 Highlights & Funktionen

* **100 % Lokale Steuerung:** Direkte Kommunikation via TCP Port 6668 im lokalen WLAN. Funktioniert auch bei vollständigem Internetausfall.
* **Automatische Erkennung von Steckdosen & Schaltern (Neu in v1.8.0):** Smarte Steckdosen, Zwischenstecker (`cz`) und Mehrfachsteckdosen (`pc`) werden jetzt automatisch als solche erkannt und nativ als **`switch`** (Geräteklasse `outlet` mit Steckdosen-Icon) angelegt – **nicht mehr fälschlicherweise als Lampe!** Bei Mehrfachsteckdosen wird jede Steckdose (`Steckdose 1`, `Steckdose 2`, `USB`) als eigener Schalter angelegt.
* **Multi-Lichtquellen Unterstützung (Dual-Channel):** Automatische Erkennung und Steuerung komplexer Lampen mit mehreren Lichtquellen (z. B. Stehlampen mit Hauptlicht & Sockel/Base-Beleuchtung, Deckenlampen mit Backlight). Beide Lichter werden als separate Entitäten unter demselben Gerät angelegt und individuell geschaltet, gedimmt oder eingefärbt!
* **Dynamische Erkennung & Live-Rescan:** Bestehende Geräte können jederzeit per Klick neu gescannt werden. Erkennt das Plugin eine Steckdose, eine zweite Lichtquelle oder neue DPs, werden diese vollautomatisch nachgetragen – ohne das Gerät neu anlegen zu müssen!
* **Gerätelisten-Cache & Mehrfachauswahl:** Einmal gefundene Geräte werden dauerhaft gespeichert. In der Auswahlliste wird direkt mit `[🔌 Steckdose]` oder `[💡 Lampe]` angezeigt, um welchen Typ es sich handelt. Du kannst mehrere Geräte per Checkbox auswählen und mit einem einzigen Klick gleichzeitig hinzufügen.
* **Automatische Geräteerkennung & Local Key Abruf:** Schnittstelle zur Tuya Cloud API und dem Tuya Local Key Add-on, die alle Geräte, Namen, IDs und Local Keys automatisch abruft und mit den lokalen WLAN-IPs abgleicht.
* **Übersichtliche Geräteauswahl:** Liste aller gefundenen Geräte im Home Assistant Webinterface – du wählst einfach per Mausklick aus, welche Lampe übernommen werden soll.
* **Optimiert für Home Assistant Green (HOAS):** Keine separate Maschine, kein Docker-Sidecar, kein Node-RED oder MQTT-Broker nötig. Läuft direkt nativ im Core-Container des Green.
* **Auto-Detection der Lampenfunktionen:** Erkennt beim ersten Verbindungsaufbau automatisch, ob es sich um eine reine Dimm-Lampe, Farbtemperatur-Lampe (CCT) oder RGB/RGBCW-Lampe handelt.
* **Single-Socket Lock & Schutz:** Verhindert das Einfrieren der Tuya-WLAN-Firmware durch thread-sichere Socket-Verwaltung.
* **Unterstützt Tuya Protokolle 3.1, 3.3, 3.4 und 3.5:** Inklusive AES-GCM und Session-Key Handshake.

---

## ⚙️ Lampe in Home Assistant einbinden (Webinterface)

Beim Klick auf **Einstellungen -> Geräte & Dienste -> Integration hinzufügen -> "Tuya Local Lamp"** wählst du deine bevorzugte Methode:

### 🌟 Neu: Gefundene Geräte hinzufügen (Geräte-Cache & Mehrfachauswahl)
Sobald du einmal Lampen über den Tuya Local Key Server, Raw JSON oder Cloud gescannt hast, merkt sich die Integration alle noch nicht eingerichteten Geräte im Speicher (`.storage`):
* Beim erneuten Hinzufügen der Integration steht direkt ganz oben:  
  **`Gefundene Geräte hinzufügen (X verfügbar)`** – komplett ohne erneute Serverabfrage oder JSON-Kopieren!
* **Mehrfachauswahl (Multi-Select):** Du kannst mehrere oder alle Lampen per Checkbox auswählen und mit einem Klick alle gleichzeitig importieren. Jede Lampe wird automatisch als eigenes Gerät in Home Assistant eingerichtet.
* Wenn du nur **eine einzelne Lampe** auswählst, gelangst du zum Bestätigungs- und Test-Dialog, in dem du Name, IP und Verbindung vor dem Speichern prüfen kannst.

### 1. Methode: Tuya Local Key Add-on (Server-URL) – Am einfachsten!
Wenn das Add-on *Tuya Local Key* auf deinem Home Assistant Server läuft:
1. Wähle **Tuya Local Key Add-on (Automatisch über Server-URL)**.
2. Das Feld ist bereits mit `http://localhost:8000` vorausgefüllt.
3. Klicke einfach auf **Absenden** – die Integration ruft alle Lampen ab und zeigt dir die Auswahlliste!

### 2. Methode: Raw JSON einfügen (aus Tuya Local Key kopiert)
Falls du keinen lokalen Port nutzt:
1. Öffne das *Tuya Local Key* Add-on und klicke bei deiner Lampe auf **Raw JSON** -> **Copy**.
2. Wähle **Raw JSON einfügen** und füge den Text in das Textfeld ein.
3. *(Optional)* Falls im Raw JSON nur die öffentliche Cloud-IP steht, kannst du deine lokale IP direkt im optionalen Feld eingeben. Lässt du es frei, scannt die Integration dein WLAN automatisch in unter einer Sekunde nach der passenden Lampe!
4. Klicke auf **Absenden** – die Lampe wird mit ihrer lokalen IP vorausgefüllt!

### 3. Methode: Tuya IoT Developer Cloud (iot.tuya.com)
Direkte Abfrage über das Tuya Entwicklerkonto (Region, Client ID & Secret).

### 4. Methode: Manuelle Direkteingabe
Direkteingabe von IP, Device ID und Local Key für einzelne Lampen.

### 5. Nachträgliches Anpassen, Rescan & DP-Konfiguration (Options Flow)
Über das Zahnrad / **Konfigurieren** im Dashboard kannst du jederzeit folgende Bereiche nutzen:
* **Lichtquellen & Live-DPs neu scannen (Neu in v1.7.0):** Fragt den Live-Status der Lampe ab und gleicht alle DPs ab. Wird dabei eine zweite Lichtquelle (wie der Sockel/Base) erkannt, wird diese sofort als neue Entität in Home Assistant hinzugefügt!
* **Netzwerk & Verbindung:** IP-Adresse, Local Key, Protokollversion oder Abfrageintervall ändern.
* **Gerätetyp & DP-Konfiguration:**
  * **Gerätetyp:** `auto` (automatisch erkennen), `light` (als Lampe erzwingen) oder `switch` (als Steckdose/Schalter erzwingen).
  * Zeigt die **aktuellen Live-Werte des Geräts** direkt an (z. B. `DP 1: True | DP 2: False | DP 9: 0` oder `DP 20: True | DP 21: colour | ...`).
  * **Power-DP:** Zuordnung des Ein/Aus-Schalters (z. B. 1 oder 20).
  * **Helligkeits-DP & Grenzwerte:** DP für Dimmer (z. B. 22 oder 3) sowie Mindest- und Maximalwert (z. B. 10 bis 1000 oder 255).
  * **Farbtemperatur-DP (CCT):** DP für Weißtöne (z. B. 23 oder 4), Grenzwerte (0 bis 1000), Kelvin-Bereich (2700K - 6500K) und Option zum **Invertieren** (Kalt/Warm umkehren).
  * **Farb-DP & Codierung:** DP für RGB/HSV (z. B. 24 oder 5) und Format (12-stelliges HSV-Hex oder 6-stelliges RGB-Hex).
  * **Modus-DP:** Betriebsmodus (z. B. 21 oder 2).
  * **Zusatzlicht / Sockel-DPs (Multi-Light):** DPs für Power (102), Helligkeit (103), Farbe (105) und Modus (106).

---

## 🧪 Vorab-Schnelltest direkt am PC (Optional)

Falls du deine Zugangsdaten und das Gerät vorab ohne Home Assistant testen möchtest, kannst du das beiliegende Python-Skript starten:
```bash
python test_lamp.py
```
Das Skript fragt IP, ID und Key ab, ermittelt automatisch die funktionierende Protokollversion (3.3/3.4/3.5) und schaltet das Gerät kurz testweise ein und aus.

---

## 📁 Dateistruktur

```
custom_components/tuya_lamp_local/
├── __init__.py           # Setup & Lifecycle Management (Multi-Platform: Light & Switch)
├── manifest.json         # Metadaten & PyPI-Abhängigkeit (tinytuya)
├── const.py              # DP-Mappings, Kategorien (Steckdosen vs. Lampen), Defaults
├── coordinator.py        # DataUpdateCoordinator mit Socket-Lock & Geräteklassifikation
├── light.py              # Home Assistant LightEntity Plattform (Haupt- & Sockellicht)
├── switch.py             # Home Assistant SwitchEntity Plattform (Steckdosen & Mehrfachleisten)
├── icons.json            # MDI Icon-Zuordnungen
├── config_flow.py        # UI-Konfigurationsassistent & Verbindungstest
├── strings.json          # Basistexte
└── translations/
    ├── de.json           # Deutsche Übersetzung
    └── en.json           # Englische Übersetzung
```
