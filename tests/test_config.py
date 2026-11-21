import dataclasses

import pytest

from elevator_sim.config import ConfigError, SimConfig

BUILDING = {"num_floors": 10, "num_elevators": 1, "capacity": 8, "start_floor": 1}


def config(**overrides):
    return SimConfig(**{**BUILDING, **overrides})


def test_fully_configured_is_valid_and_optional_fields_default():
    c = SimConfig(**BUILDING)
    assert (c.num_floors, c.num_elevators, c.capacity, c.start_floor) == (10, 1, 8, 1)
    assert c.scheduler == "nearest"
    assert c.output_dir == "output"
    assert c.max_ticks is None
    assert c.check_invariants is False


def test_nothing_configured_lists_every_missing_setting():
    with pytest.raises(
        ConfigError,
        match=r"missing required setting\(s\): num_floors, num_elevators, capacity, start_floor",
    ):
        SimConfig()


@pytest.mark.parametrize("name", list(BUILDING))
def test_each_building_setting_is_required(name):
    settings = {k: v for k, v in BUILDING.items() if k != name}
    with pytest.raises(ConfigError, match=rf"missing required setting\(s\): {name}$"):
        SimConfig(**settings)


def test_explicit_none_counts_as_missing():
    with pytest.raises(ConfigError, match="capacity"):
        config(capacity=None)


@pytest.mark.parametrize(
    "kwargs, field",
    [
        ({"num_floors": 1}, "num_floors"),
        ({"num_elevators": 0}, "num_elevators"),
        ({"capacity": 0}, "capacity"),
    ],
)
def test_settings_below_minimum_are_rejected(kwargs, field):
    with pytest.raises(ConfigError, match=field):
        config(**kwargs)


@pytest.mark.parametrize("start_floor", [0, 11])
def test_start_floor_out_of_range(start_floor):
    with pytest.raises(ConfigError, match="start_floor"):
        config(start_floor=start_floor)


def test_unknown_scheduler_lists_valid_names():
    with pytest.raises(ConfigError, match=r"unknown scheduler 'foo'; choose from: nearest"):
        config(scheduler="foo")


def test_config_is_read_only():
    c = config()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.num_floors = 20  # type: ignore[misc]


def test_max_ticks_must_be_positive():
    with pytest.raises(ConfigError, match="max_ticks"):
        config(max_ticks=0)
    assert config(max_ticks=1).max_ticks == 1


def test_bool_is_not_an_int():
    with pytest.raises(ConfigError, match="capacity"):
        config(capacity=True)


def test_reports_every_bad_field():
    with pytest.raises(ConfigError) as exc:
        config(num_floors=1, capacity=0, scheduler="foo")
    msg = str(exc.value)
    assert "num_floors" in msg and "capacity" in msg and "foo" in msg
