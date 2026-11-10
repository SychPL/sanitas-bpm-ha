"""Connect to a BLE device, dump its GATT table, subscribe to everything and log frames.

Usage: .venv\\Scripts\\python gatt.py AA:BB:CC:DD:EE:FF [seconds]   (default 120)
Start it right after the monitor begins advertising (usually just after a measurement).
Frames go to console and gatt.jsonl. Standard Blood Pressure Measurement (0x2A35)
frames are decoded on the fly.
"""
import asyncio
import json
import struct
import sys
import time

from bleak import BleakClient, BleakScanner

BP_MEASUREMENT = "00002a35-0000-1000-8000-00805f9b34fb"


def sfloat(raw):
    """IEEE 11073 16-bit SFLOAT: 4-bit signed exponent, 12-bit signed mantissa."""
    mantissa = raw & 0x0FFF
    exponent = raw >> 12
    if mantissa >= 0x0800:
        mantissa -= 0x1000
    if exponent >= 0x8:
        exponent -= 0x10
    return mantissa * 10.0**exponent


def decode_bp(data):
    """Decode Bluetooth SIG Blood Pressure Measurement characteristic."""
    flags = data[0]
    sys_, dia, mean = (sfloat(v) for v in struct.unpack_from("<HHH", data, 1))
    out = {"unit": "kPa" if flags & 0x01 else "mmHg", "sys": sys_, "dia": dia, "map": mean}
    pos = 7
    if flags & 0x02:  # timestamp
        year, month, day, hour, minute, second = struct.unpack_from("<HBBBBB", data, pos)
        out["time"] = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
        pos += 7
    if flags & 0x04:  # pulse rate
        out["pulse"] = sfloat(struct.unpack_from("<H", data, pos)[0])
        pos += 2
    if flags & 0x08:  # user id - lets us tell household members apart
        out["user"] = data[pos]
        pos += 1
    return out


def log_frame(kind, uuid, data):
    record = {"t": round(time.time(), 2), "kind": kind, "uuid": uuid, "hex": bytes(data).hex()}
    if uuid == BP_MEASUREMENT:
        record["bp"] = decode_bp(bytes(data))
    print(json.dumps(record), flush=True)
    log.write(json.dumps(record) + "\n")
    log.flush()


async def main(address, seconds):
    print(f"waiting for {address} to advertise...")
    device = await BleakScanner.find_device_by_address(address, timeout=300)
    if device is None:
        sys.exit("device not seen - take a measurement so it starts advertising")
    async with BleakClient(device) as client:
        for service in client.services:
            print(f"service {service.uuid} ({service.description})")
            for char in service.characteristics:
                print(f"  char {char.uuid} {char.properties} ({char.description})")
                if "read" in char.properties:
                    try:
                        log_frame("read", char.uuid, await client.read_gatt_char(char))
                    except Exception as error:  # some chars need pairing - keep going
                        print(f"    read failed: {error}")
                if "notify" in char.properties or "indicate" in char.properties:
                    try:
                        await client.start_notify(
                            char, lambda c, d: log_frame("notify", c.uuid, d)
                        )
                    except Exception as error:
                        print(f"    subscribe failed: {error}")
        print(f"listening {seconds}s...")
        await asyncio.sleep(seconds)


if __name__ == "__main__":
    # self-check: SIG example frame - mmHg, timestamp + pulse + user id
    frame = bytes.fromhex("1e" "8700" "5500" "6400" "ea070b0a081e00" "4800" "01" "0000")
    assert decode_bp(frame) == {
        "unit": "mmHg", "sys": 135.0, "dia": 85.0, "map": 100.0,
        "time": "2026-11-10 08:30:00", "pulse": 72.0, "user": 1,
    }, decode_bp(frame)
    assert sfloat(0xF4B0) == 120.0  # mantissa 1200, exponent -1
    if len(sys.argv) < 2:
        sys.exit("self-check ok. usage: gatt.py ADDRESS [seconds]")
    log = open("gatt.jsonl", "a", encoding="utf-8")
    asyncio.run(main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 120))
