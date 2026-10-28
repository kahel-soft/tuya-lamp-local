"""Hilfsskript zum schnellen Testen der Tuya-Lampenverbindung direkt vom PC aus."""
import sys
import time

try:
    import tinytuya
except ImportError:
    print("\n[!] tinytuya ist noch nicht installiert.")
    print("    Bitte fuehre folgenden Befehl aus: pip install tinytuya cryptography\n")
    sys.exit(1)


def test_lamp():
    print("=" * 60)
    print(" Tuya Local Lamp - Schnelltest-Werkzeug")
    print("=" * 60)

    host = input("1. IP-Adresse der Lampe eingeben (z. B. 192.168.1.50): ").strip()
    device_id = input("2. Device ID eingeben (z. B. bf1234567890abcdef): ").strip()
    local_key = input("3. Local Key eingeben (16 Zeichen): ").strip()
    proto_input = input("4. Protokollversion [auto / 3.3 / 3.4 / 3.5] (Standard: auto): ").strip().lower()

    if not host or not device_id or not local_key:
        print("\n[Fehler] IP-Adresse, Device ID und Local Key sind erforderlich!")
        return

    versions_to_test = [3.3, 3.4, 3.5, 3.1] if proto_input in ("", "auto") else [float(proto_input)]

    print(f"\n[+] Starte Verbindungstest zu {host} ...")
    connected = False
    bulb = None
    working_version = None

    for ver in versions_to_test:
        print(f"    Teste Protokoll {ver} ...", end=" ", flush=True)
        try:
            bulb = tinytuya.BulbDevice(dev_id=device_id, address=host, local_key=local_key, version=ver)
            bulb.set_socketTimeout(3)
            status = bulb.status()

            if isinstance(status, dict) and "dps" in status:
                print("ERFOLGREICH!")
                working_version = ver
                connected = True
                break
            else:
                err = status.get("Error", "Keine Antwort") if isinstance(status, dict) else str(status)
                print(f"Fehlgeschlagen ({err})")
        except Exception as e:
            print(f"Fehler ({e})")

    if not connected or bulb is None:
        print("\n[-] Verbindung konnte nicht hergestellt werden.")
        print("    Tipps:")
        print("    - Pruefe, ob die Lampe eingeschaltet ist (Stromversorgung).")
        print("    - Pruefe, ob der Local Key exakt stimmt (16 Zeichen).")
        print("    - Pruefe, ob PC und Lampe im selben Subnetz sind.")
        return

    print("\n" + "=" * 60)
    print(f" Status der Lampe (Erkannte Protokollversion: {working_version}):")
    print("=" * 60)
    dps = bulb.status().get("dps", {})
    for dp_id, val in sorted(dps.items(), key=lambda x: int(x[0]) if x[0].isdigit() else str(x[0])):
        print(f"  DP {dp_id:>2}: {val}")

    # Check layout
    if "20" in dps:
        print("\n[Erkennung] Moderner Tuya-Lampenstandard (DP 20-24) erkannt.")
    elif "1" in dps:
        print("\n[Erkennung] Aelterer Tuya-Lampenstandard (DP 1-5) erkannt.")
    else:
        print("\n[Info] Spezifische Datapoints vorhanden.")

    do_action = input("\nMoechtest du einen kurzen Ein-/Ausschalt-Test durchfuehren? (j/n): ").strip().lower()
    if do_action == "j":
        power_dp = "20" if "20" in dps else "1"
        is_on = dps.get(power_dp, False)
        print(f"Schalte Lampe {'AUS' if is_on else 'EIN'} ...")
        bulb.set_value(power_dp, not is_on)
        time.sleep(2)
        print(f"Schalte Lampe wieder {'EIN' if is_on else 'AUS'} ...")
        bulb.set_value(power_dp, is_on)
        print("Test erfolgreich abgeschlossen!")


if __name__ == "__main__":
    test_lamp()
