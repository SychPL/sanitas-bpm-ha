"""Passive BLE scan: log every advertisement (new or changed) to console and scan.jsonl.

Usage: .venv\\Scripts\\python scan.py [seconds]   (default 60)
Run it, then take a measurement on the blood pressure monitor.
"""
import asyncio
import json
import sys
import time

from bleak import BleakScanner

BP_SERVICE = "00001810-0000-1000-8000-00805f9b34fb"  # standard Blood Pressure Service
seen = {}


def on_adv(device, adv):
    record = {
        "addr": device.address,
        "name": adv.local_name or device.name,
        "rssi": adv.rssi,
        "uuids": adv.service_uuids,
        "mfr": {f"0x{k:04x}": v.hex() for k, v in adv.manufacturer_data.items()},
        "svc": {k: v.hex() for k, v in adv.service_data.items()},
    }
    key = json.dumps({k: v for k, v in record.items() if k != "rssi"}, sort_keys=True)
    if seen.get(device.address) == key:
        return  # same payload as last time, skip
    seen[device.address] = key
    record["t"] = round(time.time(), 2)
    flag = "  <== BLOOD PRESSURE SERVICE" if BP_SERVICE in adv.service_uuids else ""
    print(json.dumps(record, ensure_ascii=False) + flag, flush=True)
    log.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.flush()


async def main(seconds):
    async with BleakScanner(on_adv):
        await asyncio.sleep(seconds)
    print(f"-- {len(seen)} devices, log in scan.jsonl")


log = open("scan.jsonl", "a", encoding="utf-8")
asyncio.run(main(float(sys.argv[1]) if len(sys.argv) > 1 else 60))
