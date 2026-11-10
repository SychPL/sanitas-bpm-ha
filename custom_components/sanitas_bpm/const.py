"""Constants for the Sanitas SBM 67 integration."""
DOMAIN = "sanitas_bpm"

CONF_THRESHOLD = "threshold"
CONF_HIGH_NAME = "high_name"
CONF_LOW_NAME = "low_name"

BP_MEASUREMENT = "00002a35-0000-1000-8000-00805f9b34fb"


def signal(entry_id):
    """Dispatcher signal carrying (person, measurement) for one config entry."""
    return f"{DOMAIN}_{entry_id}"
