"""Werkzeug zum Abrufen aller Tuya-Geraete und Local Keys ueber die Tuya Cloud API."""
import json
import sys

try:
    import tinytuya
except ImportError:
    print("\n[!] tinytuya ist noch nicht installiert.")
    print("    Bitte fuehre folgenden Befehl aus: pip install tinytuya cryptography\n")
    sys.exit(1)


def discover_cloud():
    print("=" * 65)
    print(" Tuya Cloud / Local Key Abruf & Geraete-Erkennung")
    print("=" * 65)

    print("Regionen: eu (Europa), us (Westamerika), us-e (Ostamerika), cn (China)")
    region = input("1. Rechenzentrum / Region [eu/us/us-e/cn] (Standard: eu): ").strip().lower() or "eu"
    api_key = input("2. Access ID / Client ID: ").strip()
    api_secret = input("3. Access Secret / Client Secret: ").strip()
    sample_id = input("4. Beliebige Geraete-ID aus der Smart Life App: ").strip()

    if not api_key or not api_secret or not sample_id:
        print("\n[Fehler] Client ID, Secret und eine Geraete-ID sind erforderlich!")
        return

    print("\n[+] Kontaktiere Tuya Cloud API ...")
    try:
        cloud = tinytuya.Cloud(
            apiRegion=region,
            apiKey=api_key,
            apiSecret=api_secret,
            apiDeviceID=sample_id,
        )
        devices = cloud.getdevices()
    except Exception as err:
        print(f"[-] Verbindungsfehler: {err}")
        return

    if isinstance(devices, dict) and ("Error" in devices or "Err" in devices):
        err = devices.get("Payload") or devices.get("Error")
        print(f"[-] Tuya Cloud Fehler: {err}")
        return

    if not isinstance(devices, list) or len(devices) == 0:
        print("[-] Keine Geraete im Account gefunden.")
        return

    print(f"[+] {len(devices)} Geraet(e) in der Cloud gefunden.")
    print("[+] Scanne lokales Netzwerk nach IP-Adressen (Port 6666/6667 UDP) ...")
    try:
        lan_scan = tinytuya.deviceScan(verbose=False, maxretry=2)
    except Exception:
        lan_scan = {}

    lan_map = {}
    if isinstance(lan_scan, dict):
        for ip, info in lan_map.items():
            dev_id = info.get("gwId") or info.get("id")
            if dev_id:
                lan_map[dev_id] = ip

    print("\n" + "=" * 65)
    print(f"{'Name':<24} | {'IP-Adresse':<15} | {'Device ID':<16} | Local Key")
    print("-" * 65)

    export_list = []
    for d in devices:
        d_id = str(d.get("id") or d.get("gwId") or "")
        key = str(d.get("local_key") or d.get("key") or "")
        name = str(d.get("name") or "Tuya Geraet")[:24]
        ip = lan_map.get(d_id) or d.get("ip") or "Unbekannt"

        print(f"{name:<24} | {ip:<15} | {d_id[:16]:<16} | {key}")
        export_list.append(
            {
                "name": d.get("name"),
                "id": d_id,
                "key": key,
                "ip": ip if ip != "Unbekannt" else "",
                "category": d.get("category", ""),
            }
        )

    print("=" * 65)
    save_it = input("\nMoechtest du diese Geraete als 'devices.json' abspeichern? (j/n): ").strip().lower()
    if save_it == "j":
        with open("devices.json", "w", encoding="utf-8") as f:
            json.dump(export_list, f, indent=2, ensure_ascii=False)
        print("[+] Datei 'devices.json' wurde erfolgreich gespeichert!")
        print("    Diese Datei kannst du direkt in Home Assistant im Webinterface importieren.")


if __name__ == "__main__":
    discover_cloud()
