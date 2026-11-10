"""Blood pressure sensors, one set per household member."""
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPressure
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_HIGH_NAME, CONF_LOW_NAME, DOMAIN, signal

# measurement key, entity name, unit, device class
SENSORS = (
    ("sys", "Systolic", UnitOfPressure.MMHG, SensorDeviceClass.PRESSURE),
    ("dia", "Diastolic", UnitOfPressure.MMHG, SensorDeviceClass.PRESSURE),
    ("pulse", "Pulse", "bpm", None),
)


async def async_setup_entry(hass, entry, async_add_entities):
    people = (("high", entry.data[CONF_HIGH_NAME]), ("low", entry.data[CONF_LOW_NAME]))
    async_add_entities(
        BloodPressureSensor(entry, person, person_name, *sensor)
        for person, person_name in people
        for sensor in SENSORS
    )


class BloodPressureSensor(RestoreSensor):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_force_update = True  # two identical readings in a row are still two measurements

    def __init__(self, entry, person, person_name, key, name, unit, device_class):
        self._entry_id = entry.entry_id
        self._person = person
        self._key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_unique_id = f"{entry.entry_id}_{person}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{person}")},
            name=f"Blood pressure {person_name}",
            manufacturer="Sanitas",
            model="SBM 67",
        )

    async def async_added_to_hass(self):
        if (last := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last.native_value
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal(self._entry_id), self._on_measurement)
        )

    @callback
    def _on_measurement(self, person, measurement):
        if person == self._person and measurement[self._key] is not None:
            self._attr_native_value = measurement[self._key]
            self.async_write_ha_state()
