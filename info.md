# Tuya Local Direct

<p align="center">
  <a href="#-english"><strong>🇬🇧 English</strong></a> &nbsp;|&nbsp; 
  <a href="#-deutsch"><strong>🇩🇪 Deutsch</strong></a>
</p>

---

# 🇬🇧 English

**100% local, latency-free control for Tuya Wi-Fi lights, multi-channel floor lamps (main light + base), and smart sockets/power strips.**  
*Zero cloud dependency, no bridge required, zero latency – optimized for Home Assistant Green & Home Assistant OS (HOAS).*

## 🌟 Key Features & Highlights

* **100% Local LAN Control:** Direct communication via TCP port 6668 in your local Wi-Fi. Operates completely independently from the Tuya Cloud — works even during full internet outages.
* **Multi-Fixture Floor Lamps & Dual-Channel Lights:**
  * Automatic detection and independent control for multi-light fixtures (e.g. floor lamps with **Main Uplight** and **Base/Sockel Ambient Light**).
  * Main light and Base/Auxiliary light are created as **separate Home Assistant entities** (`Main Light` and `Base Light`).
  * Dedicated **White Mode** (`ColorMode.WHITE`) and Color Mode (`ColorMode.HS` / `ColorMode.RGB`) without data point collisions.
* **Smart Sockets & Multi-Outlet Power Strips (`switch`):**
  * Sockets and smart plugs (categories `cz`, `pc`) are automatically recognized and registered as **`switch` with device class `outlet`** — not misidentified as lights!
  * **Multi-Outlet Power Strips (`pc`):** Each outlet (`Socket 1`, `Socket 2`, `USB`) is registered as a separate switch entity under a unified device.
  * **Relay Protection for Energy Monitoring:** Prevents relay malfunction on power-metering sockets (voltage measurement on DP 20 is ignored; the relay operates safely via DP 1).
* **Dynamic Entity Registration & Live Rescan:**
  * When new light channels or socket outlets are detected at runtime, they are **automatically registered without requiring a Home Assistant restart**.
  * Via **Configure $\rightarrow$ Rescan Device Type, Outlets & Live DPs**, any device can be live-probed and re-synchronized directly over Wi-Fi with one click.
* **Persistent Local Device Cache & Multi-Select Setup:**
  * Discovered devices from the *Tuya Local Key* add-on or cloud query are persistently stored in local Home Assistant storage (`.storage`).
  * On subsequent setups, the **`Add Discovered Devices (Cache)`** option appears at the top.
  * Multi-select support: Add multiple or all discovered lights and sockets simultaneously via checkboxes with 1 click.
* **Single-Socket Concurrency Lock:** Thread-safe socket management prevents Tuya Wi-Fi microcontrollers from locking up.
* **Broad Protocol Support:** Tuya protocols **3.1, 3.3, 3.4, and 3.5** (including modern AES-GCM and session key handshakes).

## 🔌 Supported Device Types

| Device Type | Detection | Home Assistant Platform | Features |
| :--- | :---: | :---: | :--- |
| **Smart Socket / Plug** | `cz`, Socket DPs | `switch` (`outlet`) | On/Off, Relay protection with power monitoring |
| **Multi-Outlet Power Strip** | `pc`, Multi DPs (1..7) | `switch` (`outlet`) | Independent switches (`Socket 1`, `Socket 2`, `USB`) |
| **Wall Switch / In-Wall Relay** | `kg`, `wk`, `dlq` | `switch` (`switch`) | Relay On/Off control |
| **Simple Dimmer Light** | DP 20/22 or 1/3 | `light` | On/Off, Brightness (1–255) |
| **CCT Color Temperature Light** | DP 20/22/23 or 1/3/4 | `light` | Brightness, Kelvin temperature (Warm White to Cool White) |
| **RGB / RGBCW Light** | DP 20/22/23/24 or 1/3/4/5 | `light` | Brightness, Kelvin, Color picker (HS / RGB colors) |
| **Multi-Channel Floor Lamp** | DP 101 / 102 / 103 / 105 | `light` (2 entities) | Independent control of **Main Light** and **Base/Sockel** |

---

# 🇩🇪 Deutsch

**100 % lokale, latenzfreie Steuerung für Tuya Wi-Fi Lampen, Multi-Lichtquellen (z. B. Stehlampen mit Sockel) und smarte Steckdosen.**  
*Keine Cloud-Abhängigkeit, kein Bridge-Zwang, keine Latenz – optimiert für Home Assistant OS (HOAS) und Home Assistant Green.*

## 🌟 Highlights & Funktionen

* **100 % Lokale Steuerung:** Direkte Kommunikation über TCP Port 6668 im lokalen WLAN. Funktioniert dauerhaft autark – auch bei komplettem Internetausfall.
* **Multi-Lichtquellen (Dual-Channel):**
  * Automatische Erkennung und unabhängige Steuerung von Stehlampen mit **Hauptlicht** und **Sockel/Base-Beleuchtung**.
  * Beide Lichtquellen werden als separate Entitäten (`Hauptlicht` und `Sockel`) angelegt.
  * Echter Weißmodus (`ColorMode.WHITE`) und Farbmodus (`ColorMode.HS` / `ColorMode.RGB`) ohne Datenpunkt-Kollisionen.
* **Smarte Steckdosen & Mehrfachleisten (`switch`):**
  * Sockets und Zwischenstecker (Kategorie `cz`, `pc`) werden automatisch als **`switch` mit Geräteklasse `outlet`** angelegt – nicht fälschlicherweise als Lampe!
  * **Mehrfachsteckdosen (`pc`):** Jede Steckdose (`Steckdose 1`, `Steckdose 2`, `USB`) wird als separater Schalter unter einem gemeinsamen Gerät bereitgestellt.
  * **Relais-Schutz bei Strommessung:** Verhindert Fehlsteuerungen bei Steckdosen mit Energy Monitoring (Spannungswert auf DP 20 wird ignoriert, Relais sauber über DP 1 geschaltet).
* **Dynamische Erkennung & Live-Rescan:**
  * Erkennt das Plugin beim Polling oder nach dem Einschalten neue Lichtkanäle oder Schalter, werden diese **zur Laufzeit ohne Home Assistant Neustart automatisch nachgetragen**.
  * Über **Konfigurieren $\rightarrow$ Gerätetyp, Steckdosen & Live-DPs neu scannen** kann jedes Gerät jederzeit per Mausklick live im Netzwerk abgefragt und synchronisiert werden.
* **Gerätelisten-Cache & Mehrfachauswahl (Multi-Select):**
  * Einmal gefundene Geräte werden dauerhaft lokal im Speicher gemerkt.
  * Beim Hinzufügen können mehrere oder alle Geräte per Checkbox auf einmal eingerichtet werden.
* **Single-Socket Lock & Schutz:** Verhindert das Einfrieren der Tuya-WLAN-Chips durch thread-sichere Socket-Verwaltung.
* **Breite Protokoll-Unterstützung:** Unterstützt die Tuya-Protokollversionen **3.1, 3.3, 3.4 und 3.5** (inkl. AES-GCM und Session-Key Handshake).

## 🔌 Unterstützte Gerätetypen

| Gerätetyp | Erkennung | Home Assistant Plattform | Unterstützte Funktionen |
| :--- | :---: | :---: | :--- |
| **Smarte Steckdose / Zwischenstecker** | `cz`, Socket-DPs | `switch` (`outlet`) | Schalten (Ein/Aus), Spannungsschutz bei Strommessung |
| **Mehrfachsteckdosenleiste** | `pc`, Multi-DPs (1..7) | `switch` (`outlet`) | Unabhängige Schalter (`Steckdose 1`, `Steckdose 2`, `USB`) |
| **Smarte Wand- & Relaisschalter** | `kg`, `wk`, `dlq` | `switch` (`switch`) | Ein/Aus Relais-Steuerung |
| **Einfache Dimm-Lampe** | DP 20/22 bzw. 1/3 | `light` | Ein/Aus, Helligkeit (1–255) |
| **Farbtemperatur-Lampe (CCT)** | DP 20/22/23 bzw. 1/3/4 | `light` | Dimmen, Kelvin-Einstellung (Warmweiß bis Kaltweiß) |
| **RGB / RGBCW Farb-Lampe** | DP 20/22/23/24 bzw. 1/3/4/5 | `light` | Dimmen, Kelvin, Farbkreis (HS / RGB-Farben) |
| **Multi-Licht Stehleuchten (Dual-Channel)** | DP 101 / 102 / 103 / 105 | `light` (2 Entitäten) | Unabhängige Steuerung von **Hauptlicht** und **Sockel/Base** |
