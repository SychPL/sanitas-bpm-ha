"""Decode Bluetooth SIG Blood Pressure Measurement (0x2A35) frames. No HA imports.

Run this file directly for a self-check.
"""
import struct

KPA_TO_MMHG = 7.50062


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
    """Return {"sys", "dia", "pulse"} in mmHg / bpm, or None for a frame we cannot use.

    The device timestamp and user id are ignored on purpose: the SBM 67 clock is
    unreliable (resets to 2015 on battery change) and nobody switches user profiles.
    """
    if len(data) < 7:
        return None
    flags = data[0]
    scale = KPA_TO_MMHG if flags & 0x01 else 1.0
    systolic, diastolic = (sfloat(v) * scale for v in struct.unpack_from("<HH", data, 1))
    pos = 7 + (7 if flags & 0x02 else 0)  # skip MAP and optional timestamp
    pulse = None
    if flags & 0x04 and len(data) >= pos + 2:
        pulse = sfloat(struct.unpack_from("<H", data, pos)[0])
    # trust boundary: drop SFLOAT specials (NaN/NRes decode to ~2047) and garbage
    if not (30 <= diastolic < systolic <= 300) or (pulse is not None and not 20 <= pulse <= 250):
        return None
    return {"sys": round(systolic), "dia": round(diastolic), "pulse": pulse and round(pulse)}


def who(systolic, threshold):
    """Household heuristic: one person runs high, the other low."""
    return "high" if systolic >= threshold else "low"


if __name__ == "__main__":
    # synthetic frames in the exact layout the SBM 67 sends (flags 0x1e):
    # flags, sys, dia, MAP, timestamp, pulse, user id, measurement status
    assert decode_bp(bytes.fromhex("1e" "7800" "5000" "0000" "e8070102030400" "3c00" "00" "0000")) == {
        "sys": 120, "dia": 80, "pulse": 60}
    assert decode_bp(bytes.fromhex("1e" "5f00" "3c00" "0000" "e8070102030500" "4b00" "01" "0000")) == {
        "sys": 95, "dia": 60, "pulse": 75}
    assert sfloat(0xF4B0) == 120.0  # mantissa 1200, exponent -1
    assert decode_bp(bytes.fromhex("01" "1000" "0b00" "0000"))["sys"] == 120  # 16 kPa
    assert decode_bp(bytes.fromhex("00" "ff07" "ff07" "ff07")) is None  # NaN frame
    assert decode_bp(b"\x00\x01") is None  # truncated
    assert who(137, 110) == "high" and who(103, 110) == "low"
    print("self-check ok")
