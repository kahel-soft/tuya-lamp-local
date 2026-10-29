# Tuya Local Direct

**100 % lokale, latenzfreie Steuerung für Tuya Wi-Fi Lampen, Multi-Lichtquellen (z. B. Stehlampen mit Sockel) und smarte Steckdosen.**  
*Keine Cloud-Abhängigkeit, kein Bridge-Zwang, keine Latenz – optimiert für Home Assistant OS (HOAS) und Home Assistant Green.*

---

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
* **Single-Socket Lock & Schutz:**
  * Verhindert das Einfrieren der Tuya-WLAN-Chips durch thread-sichere Socket-Verwaltung.
* **Breite Protokoll-Unterstützung:**
  * Unterstützt die Tuya-Protokollversionen **3.1, 3.3, 3.4 und 3.5** (inkl. AES-GCM und Session-Key Handshake).

---

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
