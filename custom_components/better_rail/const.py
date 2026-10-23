"""Constants for the Better Rail integration."""

from datetime import timedelta
from typing import Final

DOMAIN = "better_rail"

CONF_START: Final = "from"
CONF_DESTINATION: Final = "to"

DEPARTURES_COUNT = 3

# Polling adapts to how close the next departure is: the nearer (or the more
# delayed) the train, the more often live data is fetched.
SCAN_INTERVAL_IDLE = timedelta(minutes=15)  # next train is more than 3 hours away
SCAN_INTERVAL_FAR = timedelta(minutes=5)  # within 3 hours
SCAN_INTERVAL_SOON = timedelta(minutes=1)  # within 1 hour
SCAN_INTERVAL_IMMINENT = timedelta(seconds=30)  # within 15 minutes, or delayed
# Delays on trains further out than this do not force fast polling.
DELAY_WATCH_WINDOW = timedelta(hours=1)

API_URL: Final = (
    "https://api.better-rail.co.il/api/v1/rail-api/rjpa/api/v1/timetable/"
    "searchTrainLuzForDateTime"
)
API_TIMEOUT = 20

ATTRIBUTION = "Data provided by Better Rail."
