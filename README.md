# Better Rail for Home Assistant

A Home Assistant custom integration that works like the built-in
[Israel Rail](https://www.home-assistant.io/integrations/israel_rail/) integration, but gets its
data from the [Better Rail](https://github.com/better-rail/server) API. Better Rail overlays
live SIRI real-time data on the GTFS timetable, so delays, platform changes and cancellations are
more accurate than what the Israel Railways apps report.

This is an unofficial, community integration. It is not affiliated with Israel Railways or the
Better Rail project.

## Installation

### HACS (recommended)

1. In HACS, open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/ronshapiro/better-rail-home-assistant` with type **Integration**.
3. Download **Better Rail**, then restart Home Assistant.

### Manual

Copy `custom_components/better_rail` into your Home Assistant `config/custom_components/`
directory and restart.

## Setup

**Settings → Devices & services → Add integration → Better Rail**, then pick a start and an end
station. Add the integration once per route you want to track.

## Entities

For each of the next three departures (the first has no suffix, the others end in `+1` and `+2`):

| Entity | Description |
| --- | --- |
| Departure | Scheduled departure time (timestamp) |
| Expected departure | Scheduled departure plus the live delay (timestamp) |
| Arrival | Scheduled arrival time at the destination (timestamp) |
| Departure delay | Live delay in minutes at the start station |
| Platform | Live platform at the start station (unknown if not yet assigned) |
| Train number | Number of the first train of the journey |
| Trains | Number of trains in the journey (more than 1 means a transfer) |
| Cancelled | `on` if the train has been cancelled (binary sensor) |

A train stays in the list until its scheduled departure plus its delay has passed. Cancelled
trains remain listed so you can see the cancellation. 

### Refresh rate

Polling adapts to the next departure, so delays are caught quickly when it matters:

| Situation | Refresh every |
| --- | --- |
| Next train more than 3 hours away (or none listed) | 15 minutes |
| Within 3 hours | 5 minutes |
| Within 1 hour | 1 minute |
| Within 15 minutes of the scheduled departure | 30 seconds |
| Any of the next trains within the hour is delayed, or is waiting past its scheduled time | 30 seconds |

The interval never overshoots the point where the next tier begins, and delayed trains keep the fast
rate until they have actually left, so automations can react to delay changes within about 30 seconds.

## Example automation

```yaml
automation:
  - alias: "Train is late"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.tel_aviv_hashalom_mazkeret_batya_departure_delay
        above: 5
    actions:
      - action: notify.notify
        data:
          message: "The next train is {{ trigger.to_state.state }} minutes late."
```

## Differences from the built-in integration

- Uses the Better Rail API instead of the `israel-rail-api` library, so there are no extra
  Python requirements.
- Stations are chosen from a list that stores station IDs (e.g. `4600`) rather than Hebrew names.
- Adds *Expected departure*, *Arrival* and *Cancelled* entities.

## Development

```
pip install -r requirements_test.txt
pytest
```
