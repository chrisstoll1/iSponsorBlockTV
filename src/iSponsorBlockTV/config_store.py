"""Shared configuration validation and atomic persistence for all configurators."""

import copy
import json
import math
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .constants import SponsorBlock_api, skip_categories

DEFAULT_CONFIG = {
    "devices": [],
    "apikey": "",
    "skip_categories": ["sponsor"],
    "channel_whitelist": [],
    "skip_count_tracking": True,
    "mute_ads": False,
    "skip_ads": False,
    "minimum_skip_length": 1,
    "auto_play": True,
    "join_name": "iSponsorBlockTV",
    "use_proxy": False,
    "sponsorblock_api_url": SponsorBlock_api,
}


def _string(value, field, required=False):
    if not isinstance(value, str) or len(value) > 4096 or (required and not value.strip()):
        raise ValueError(f"{field} must be {'a non-empty' if required else 'a'} string")


def _number(value, field, minimum=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")


def normalize_config(document):
    if not isinstance(document, dict):
        raise TypeError("Configuration must be a JSON object")
    unknown = document.keys() - DEFAULT_CONFIG.keys()
    if unknown:
        raise ValueError("Configuration contains unsupported fields")
    config = copy.deepcopy(DEFAULT_CONFIG)
    config.update(copy.deepcopy(document))
    for field in ("skip_count_tracking", "mute_ads", "skip_ads", "auto_play", "use_proxy"):
        if type(config[field]) is not bool:
            raise ValueError(f"{field} must be true or false")
    for field in ("apikey", "join_name", "sponsorblock_api_url"):
        _string(config[field], field, required=field != "apikey")
    api_url = urlsplit(config["sponsorblock_api_url"])
    if api_url.scheme not in ("http", "https") or not api_url.hostname:
        raise ValueError("sponsorblock_api_url must be an HTTP or HTTPS URL")
    if api_url.username or api_url.password or api_url.query or api_url.fragment:
        raise ValueError("sponsorblock_api_url cannot contain credentials, query, or fragment")
    config["sponsorblock_api_url"] = config["sponsorblock_api_url"].rstrip("/") + "/"
    _number(config["minimum_skip_length"], "minimum_skip_length", minimum=0)
    for field in ("devices", "channel_whitelist", "skip_categories"):
        if not isinstance(config[field], list) or len(config[field]) > 1000:
            raise ValueError(f"{field} must be a list with at most 1000 entries")
    allowed_categories = {category for _, category in skip_categories}
    if any(
        not isinstance(category, str) or category not in allowed_categories
        for category in config["skip_categories"]
    ):
        raise ValueError("skip_categories contains an unsupported category")
    seen = set()
    for device in config["devices"]:
        if not isinstance(device, dict) or device.keys() - {"screen_id", "name", "offset"}:
            raise ValueError("Each device must contain only screen_id, name, and offset")
        _string(device.get("screen_id"), "device.screen_id", required=True)
        device.setdefault("name", "YouTube on TV")
        device.setdefault("offset", 0)
        _string(device["name"], "device.name")
        _number(device["offset"], "device.offset")
        if device["screen_id"] in seen:
            raise ValueError("A device screen_id cannot be added twice")
        seen.add(device["screen_id"])
    for channel in config["channel_whitelist"]:
        if not isinstance(channel, dict) or channel.keys() - {"id", "name"}:
            raise ValueError("Each whitelisted channel must contain only id and name")
        _string(channel.get("id"), "channel.id", required=True)
        channel.setdefault("name", "")
        _string(channel["name"], "channel.name")
    if config["channel_whitelist"] and not config["apikey"].strip():
        raise ValueError("An API key is required when the channel whitelist is not empty")
    return config


def read_config(path):
    try:
        with open(path, encoding="utf-8") as stream:
            return normalize_config(json.load(stream))
    except FileNotFoundError:
        return normalize_config({})


def write_config(path, document):
    config = normalize_config(document)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # Same-directory replacement is atomic, including on mounted datasets.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".config-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = stream.name
            json.dump(config, stream, indent=4, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return config
