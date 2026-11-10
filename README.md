# Sanitas SBM 67 for Home Assistant

Home Assistant custom integration that reads blood pressure measurements from a
Sanitas SBM 67 monitor (advertises as `BPM Smart`; a Beurer BM 67 sibling) over
Bluetooth LE and assigns each one to a household member. No phone app needed:
take a measurement within range of a Bluetooth proxy and it shows up in HA.

Status: the decoder is verified against 96 frames captured from a real device.
The Home Assistant side has not been run in a live instance yet.

## How it works

1. The monitor advertises for a short while after each measurement.
2. HA sees the advertisement and connects through any Bluetooth adapter or
   ESPHome proxy that supports active connections.
3. On subscribing to the Blood Pressure Measurement characteristic the monitor
   sends its whole memory (all user profiles, about 100 frames).
4. Frames not seen before are new measurements. Systolic at or above the
   configured threshold goes to the "high" person, below it to the "low" person.

The very first sync only records what is already in the device memory and
publishes nothing, so the second measurement is the first one you will see.

Entities: two devices (one per person), each with `Systolic`, `Diastolic`
(mmHg) and `Pulse` (bpm) sensors.

## Why assign by value

The monitor has user profiles, but in this household nobody switches them. One
person runs high and the other low, with a clear gap between the two groups, so
a single systolic threshold (default 110 mmHg) is enough. If your household
does not split that cleanly, this heuristic is not for you.

## Install

Copy `custom_components/sanitas_bpm` into `/config/custom_components/` (or add
this repository to HACS as a custom repository of type Integration), restart
Home Assistant, then add the "Sanitas SBM 67" integration and enter:

- the Bluetooth address of the monitor (find it with `scan.py`),
- the systolic threshold,
- the names of the two people.

## Protocol notes

Nothing proprietary - the device speaks the standard Bluetooth SIG Blood
Pressure Profile and needs no pairing.

- Service `0x1810`, characteristic `0x2A35` (indicate).
- Frame: flags, systolic, diastolic, MAP (always 0) as IEEE 11073 SFLOAT, then
  timestamp, pulse, user id, measurement status. Flags observed: `0x1e`.
- The device clock is unreliable (it falls back to 2015 after a battery
  change), so the integration ignores frame timestamps and uses arrival time.

## Capture tools

Standalone scripts used for the reverse engineering, need `pip install bleak`:

- `scan.py [seconds]` - passive scan, logs every advertisement to `scan.jsonl`
  and flags devices exposing the Blood Pressure Service.
- `gatt.py ADDRESS [seconds]` - connects, dumps the GATT table, subscribes to
  everything and logs frames to `gatt.jsonl`, decoding `0x2A35` on the fly.

Self-check of the decoder: `python custom_components/sanitas_bpm/bp_frame.py`.
