"""Tests for the Better Rail integration."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.better_rail.api import ISRAEL_TZ, parse_journeys
from custom_components.better_rail.const import API_URL, DOMAIN


def _train(number, dep, arr, delay=None, platform=2, cancelled=False, extra=None):
    train = {
        "trainNumber": number,
        "originPlatform": platform,
        "departureTime": dep,
        "arrivalTime": arr,
        "trainPosition": None if delay is None else {"calcDiffMinutes": delay},
    }
    if cancelled:
        train["isCancelled"] = True
    return {"departureTime": dep, "arrivalTime": arr, "trains": [train, *(extra or [])]}


PAYLOAD = {
    "result": {
        "travels": [
            _train(6019, "2026-10-23T05:20:00", "2026-10-23T05:57:00"),
            _train(6021, "2026-10-23T12:20:00", "2026-10-23T12:57:00", delay=7, platform=3),
            _train(6023, "2026-10-23T13:20:00", "2026-10-23T13:57:00", cancelled=True),
            _train(6025, "2026-10-23T14:20:00", "2026-10-23T14:57:00", delay=0),
        ]
    }
}
EMPTY = {"result": {"travels": []}}


def test_parse_journeys() -> None:
    journeys = parse_journeys(PAYLOAD)
    assert [j.train_number for j in journeys] == ["6019", "6021", "6023", "6025"]
    late = journeys[1]
    assert late.delay == 7
    assert late.platform == "3"
    assert late.departure == datetime(2026, 10, 23, 12, 20, tzinfo=ISRAEL_TZ)
    assert late.expected_departure == datetime(2026, 10, 23, 12, 27, tzinfo=ISRAEL_TZ)
    assert journeys[2].cancelled
    assert journeys[0].delay == 0


def test_parse_ignores_garbage() -> None:
    assert parse_journeys({}) == []
    assert parse_journeys({"result": {"travels": [{"trains": []}, {"trains": [{"departureTime": "x"}]}]}}) == []


async def _setup(hass, aioclient_mock, freezer, payload=PAYLOAD):
    freezer.move_to("2026-10-23 09:10:00+00:00")  # 12:10 Israel time
    aioclient_mock.get(f"{API_URL}?date=2026-10-24", json=EMPTY)
    aioclient_mock.get(API_URL, json=payload)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4600 6900",
        title="Tel Aviv - HaShalom → Mazkeret Batya",
        data={"from": "4600", "to": "6900"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass, aioclient_mock, freezer)
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    prefix = "sensor.tel_aviv_hashalom_mazkeret_batya"

    # The 05:20 train has left; the delayed 12:20 train is first.
    assert hass.states.get(f"{prefix}_train_number").state == "6021"
    assert hass.states.get(f"{prefix}_train_number_1").state == "6023"
    assert hass.states.get(f"{prefix}_train_number_2").state == "6025"
    assert hass.states.get(f"{prefix}_departure_delay").state == "7"
    assert hass.states.get(f"{prefix}_platform").state == "3"
    assert hass.states.get(f"{prefix}_departure").state == "2026-10-23T09:20:00+00:00"
    assert hass.states.get(f"{prefix}_expected_departure").state == "2026-10-23T09:27:00+00:00"
    assert hass.states.get(f"{prefix}_trains").state == "1"
    assert (
        hass.states.get("binary_sensor.tel_aviv_hashalom_mazkeret_batya_cancelled_1").state
        == "on"
    )
    assert hass.states.get("binary_sensor.tel_aviv_hashalom_mazkeret_batya_cancelled").state == "off"
    assert registry.async_get(f"{prefix}_departure_delay").unique_id == "4600 6900_departure_delay"


async def test_delayed_train_stays_upcoming(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    """At 12:25 the 12:20 train is 7 min late, so it has not left yet."""
    entry = await _setup(hass, aioclient_mock, freezer)
    freezer.move_to("2026-10-23 09:25:00+00:00")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tel_aviv_hashalom_mazkeret_batya_train_number").state == "6021"
    freezer.move_to("2026-10-23 09:28:00+00:00")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tel_aviv_hashalom_mazkeret_batya_train_number").state == "6023"


async def test_api_failure_sets_retry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-10-23 09:10:00+00:00")
    aioclient_mock.get(API_URL, status=500)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="a b", data={"from": "4600", "to": "6900"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_rolls_over_to_tomorrow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-10-23 20:50:00+00:00")  # 23:50 Israel time
    tomorrow = {"result": {"travels": [_train(7001, "2026-10-24T05:20:00", "2026-10-24T05:57:00")]}}
    aioclient_mock.get(f"{API_URL}?date=2026-10-24", json=tomorrow)
    aioclient_mock.get(API_URL, json=PAYLOAD)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="4600 6900", title="x → y", data={"from": "4600", "to": "6900"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert [j.train_number for j in entry.runtime_data.data] == ["7001"]


async def test_config_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(API_URL, json=EMPTY)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM

    same = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"from": "4600", "to": "4600"}
    )
    assert same["errors"] == {"base": "same_station"}

    done = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"from": "4600", "to": "6900"}
    )
    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert done["title"] == "Tel Aviv - HaShalom → Mazkeret Batya"
    assert done["data"] == {"from": "4600", "to": "6900"}

    dup = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    dup = await hass.config_entries.flow.async_configure(
        dup["flow_id"], {"from": "4600", "to": "6900"}
    )
    assert dup["type"] is FlowResultType.ABORT


async def test_config_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(API_URL, status=503)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"from": "4600", "to": "6900"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


def _j(minutes_from_now, delay=0):
    from datetime import timedelta

    from custom_components.better_rail.api import Journey

    return Journey(NOW + timedelta(minutes=minutes_from_now), None, delay, "1", "1", 1, False)


NOW = datetime(2026, 10, 23, 12, 0, tzinfo=ISRAEL_TZ)


@pytest.mark.parametrize(
    ("journeys", "expected_seconds"),
    [
        ([], 900),
        ([_j(600)], 900),
        ([_j(190)], 600),  # 10 min until the 3h tier begins
        ([_j(120)], 300),
        ([_j(90)], 300),
        ([_j(65)], 300),  # 5 min until the 1h tier begins
        ([_j(40)], 60),
        ([_j(20)], 60),
        ([_j(10)], 30),
        ([_j(-3, delay=7)], 30),  # delayed, still waiting
        ([_j(30), _j(45, delay=4)], 30),  # delay on a later train within the hour
        ([_j(150), _j(200, delay=4)], 300),  # delay too far out to matter yet
        ([_j(-2)], 30),  # past scheduled time without a delay report
    ],
)
def test_next_update_interval(journeys, expected_seconds) -> None:
    from custom_components.better_rail.coordinator import next_update_interval

    assert next_update_interval(journeys, NOW).total_seconds() == expected_seconds


async def test_coordinator_applies_interval(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    """At 12:10 the delayed 12:20 train keeps polling at 30 seconds."""
    entry = await _setup(hass, aioclient_mock, freezer)
    assert entry.runtime_data.update_interval.total_seconds() == 30
