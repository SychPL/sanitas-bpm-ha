"""Sanitas SBM 67 blood pressure monitor.

The monitor advertises for a moment after each measurement. When we see it we
connect (through any connectable Bluetooth proxy), subscribe to the standard
Blood Pressure Measurement characteristic and receive a dump of the whole device
memory. Frames we have not seen before are new measurements.
"""
import asyncio
import logging
import time

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .bp_frame import decode_bp, who
from .const import BP_MEASUREMENT, CONF_THRESHOLD, DOMAIN, signal

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
IDLE_SECONDS = 5  # dump is over when no frame arrives for this long (frames come ~0.2 s apart)
COOLDOWN_SECONDS = 60  # do not reconnect while the monitor is still advertising
MAX_SEEN = 1000  # device memory holds ~120 frames; keep plenty of headroom


class Monitor:
    """Fetches memory dumps and publishes measurements not seen before."""

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.address = entry.data[CONF_ADDRESS]
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.seen = None  # dict used as an ordered set of frame hex; None = never synced
        self.lock = asyncio.Lock()
        self.last_fetch = 0.0

    async def async_load(self):
        saved = await self.store.async_load()
        if saved is not None:
            self.seen = dict.fromkeys(saved)

    @callback
    def on_advertisement(self, service_info, change):
        if self.lock.locked() or time.monotonic() - self.last_fetch < COOLDOWN_SECONDS:
            return
        self.entry.async_create_background_task(self.hass, self.fetch(), f"{DOMAIN} fetch")

    async def fetch(self):
        async with self.lock:
            frames = await self._read_dump()
            self.last_fetch = time.monotonic()
        if not frames:
            return
        first_sync = self.seen is None
        if first_sync:
            self.seen = {}
        new = [frame for frame in frames if frame.hex() not in self.seen]
        self.seen.update(dict.fromkeys(frame.hex() for frame in new))
        await self.store.async_save(list(self.seen)[-MAX_SEEN:])
        if first_sync:
            # everything in memory is history of unknown age - remember it, publish nothing
            _LOGGER.info("First sync: stored %d historical frames", len(new))
            return
        for frame in new:
            measurement = decode_bp(frame)
            if measurement is None:
                _LOGGER.warning("Ignoring unusable frame %s", frame.hex())
                continue
            person = who(measurement["sys"], self.entry.data[CONF_THRESHOLD])
            _LOGGER.info("New measurement for %s: %s", person, measurement)
            async_dispatcher_send(self.hass, signal(self.entry.entry_id), person, measurement)

    async def _read_dump(self):
        device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        if device is None:
            _LOGGER.debug("%s not reachable through a connectable adapter", self.address)
            return []
        frames = []
        got_frame = asyncio.Event()

        def on_frame(_char, data):
            frames.append(bytes(data))
            got_frame.set()

        try:
            client = await establish_connection(
                BleakClientWithServiceCache, device, "Sanitas SBM 67"
            )
            try:
                await client.start_notify(BP_MEASUREMENT, on_frame)
                while True:
                    got_frame.clear()
                    try:
                        await asyncio.wait_for(got_frame.wait(), IDLE_SECONDS)
                    except asyncio.TimeoutError:
                        break
            finally:
                await client.disconnect()
        except (BleakError, asyncio.TimeoutError) as error:
            # frames received before the failure are still valid measurements
            _LOGGER.warning("Reading %s failed after %d frames: %s", self.address, len(frames), error)
        return frames


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    monitor = Monitor(hass, entry)
    await monitor.async_load()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            monitor.on_advertisement,
            {"address": monitor.address, "connectable": True},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
