import asyncio
import json

import pytest

from iSponsorBlockTV.config_store import normalize_config, read_config, write_config
from iSponsorBlockTV.helpers import Config
from iSponsorBlockTV.main import run_listeners, wait_for_config


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"devices": "broken"},
        {"devices": [{"screen_id": ""}]},
        {"devices": [{"screen_id": "tv", "offset": True}]},
        {"devices": [{"screen_id": "tv"}, {"screen_id": "tv"}]},
        {"minimum_skip_length": -1},
        {"minimum_skip_length": float("nan")},
        {"minimum_skip_length": True},
        {"mute_ads": "false"},
        {"skip_categories": ["bogus"]},
        {"channel_whitelist": [{"id": "channel"}]},
        {"config_file": "/etc/passwd"},
        {"validate": "broken"},
        {"sponsorblock_api_url": "file:///etc/passwd"},
    ],
)
def test_invalid_documents_never_replace_working_config(tmp_path, document):
    path = tmp_path / "config.json"
    write_config(path, {"join_name": "working"})
    before = path.read_bytes()
    with pytest.raises((ValueError, TypeError)):
        write_config(path, document)
    assert path.read_bytes() == before


def test_atomic_save_and_normalization(tmp_path, monkeypatch):
    path = tmp_path / "new" / "config.json"
    import os

    original_replace = os.replace
    calls = []

    def replace(source, destination):
        with open(source, encoding="utf-8") as stream:
            calls.append(json.load(stream))
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", replace)
    result = write_config(path, {"skip_categories": [], "devices": [{"screen_id": "tv"}]})
    assert calls == [result]
    assert read_config(path)["skip_categories"] == []
    assert list(path.parent.iterdir()) == [path]


def test_failed_replace_preserves_config_and_removes_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    write_config(path, {"join_name": "working"})
    import os

    monkeypatch.setattr(os, "replace", lambda *_: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        write_config(path, {"join_name": "new"})
    assert read_config(path)["join_name"] == "working"
    assert list(tmp_path.iterdir()) == [path]


def test_config_validation_is_repeatable_and_save_keeps_offsets(tmp_path):
    path = tmp_path / "config.json"
    write_config(path, {"devices": [{"screen_id": "tv", "offset": -250}]})
    config = Config(str(tmp_path))
    config.validate()
    config.validate()
    assert config.devices[0].offset == -0.25
    config.save()
    assert read_config(path)["devices"][0]["offset"] == -250
    assert config.config_file == str(path).replace("\\", "/") or config.config_file.endswith(
        "/config.json"
    )


@pytest.mark.asyncio
async def test_reload_survives_malformed_file_and_applies_rapid_atomic_saves(tmp_path):
    path = tmp_path / "config.json"
    write_config(path, {"join_name": "old", "mute_ads": True})
    config = Config(str(tmp_path))
    config.validate()
    waiter = asyncio.create_task(wait_for_config(config, interval=0.01))
    try:
        path.write_text('{"devices":', encoding="utf-8")
        await asyncio.sleep(0.03)
        assert not waiter.done()
        assert config.mute_ads is True
        write_config(path, {"join_name": "first"})
        candidate = await asyncio.wait_for(waiter, timeout=1)
        assert candidate.join_name == "first"
        assert candidate.mute_ads is False  # Removed fields revert to defaults.
        waiter = asyncio.create_task(wait_for_config(candidate, interval=0.01))
        write_config(path, {"join_name": "second"})
        assert (await asyncio.wait_for(waiter, timeout=1)).join_name == "second"
    finally:
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


@pytest.mark.asyncio
async def test_empty_worker_waits_for_first_configuration_and_stops(tmp_path):
    config = Config(str(tmp_path))
    config.validate()
    stop = asyncio.Event()
    running = asyncio.create_task(run_listeners(config, False, False, stop))
    await asyncio.sleep(0.03)
    assert not running.done()
    stop.set()
    assert await asyncio.wait_for(running, timeout=1) is None


@pytest.mark.asyncio
async def test_reload_cancels_device_tasks_and_closes_session(tmp_path, monkeypatch):
    from iSponsorBlockTV import main

    write_config(tmp_path / "config.json", {"devices": [{"screen_id": "tv"}]})
    config = Config(str(tmp_path))
    config.validate()
    sessions = []
    cancelled = []

    class FakeDevice:
        def __init__(self, api, config, entry, debug, session):
            sessions.append(session)

        async def initialize_web_session(self):
            pass

        async def loop(self):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        refresh_auth_loop = loop

        async def cancel(self):
            cancelled.append(True)

    monkeypatch.setattr(main, "DeviceListener", FakeDevice)
    running = asyncio.create_task(main.run_listeners(config, False, False, asyncio.Event()))
    await asyncio.sleep(0.03)
    write_config(tmp_path / "config.json", {"devices": []})
    candidate = await asyncio.wait_for(running, timeout=2)
    assert candidate.devices == []
    assert sessions[0].closed
    assert len(cancelled) == 3


def test_defaults_are_independent():
    config = normalize_config({})
    config["devices"].append({})
    assert normalize_config({})["devices"] == []
