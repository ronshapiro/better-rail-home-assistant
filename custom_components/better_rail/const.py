"""Constants for the Better Rail integration."""

from datetime import timedelta
from typing import Final

DOMAIN = "better_rail"

CONF_START: Final = "from"
CONF_DESTINATION: Final = "to"

DEPARTURES_COUNT = 3

DEFAULT_SCAN_INTERVAL = timedelta(seconds=90)

API_URL: Final = (
    "https://api.better-rail.co.il/api/v1/rail-api/rjpa/api/v1/timetable/"
    "searchTrainLuzForDateTime"
)
API_TIMEOUT = 20

ATTRIBUTION = "Data provided by Better Rail."
