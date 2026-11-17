# iSponsorBlockTV

## Web dashboard fork

This fork adds a browser configurator to
[upstream iSponsorBlockTV](https://github.com/dmunozv04/iSponsorBlockTV).
It follows upstream playback and pairing changes and publishes separate worker
and dashboard images. See [fork release notes](CHANGELOG.md).

### Docker Compose

1. Copy `.env.example` to `.env` and set a unique `DASHBOARD_PASSWORD`.
2. Create `data/` and grant the configured UID/GID (default `568:568`) read/write
   access. For a new empty directory on Linux:
   `mkdir -p data && sudo chown 568:568 data`.
   For an existing dataset, grant access through its ACL.
3. Start released images with `docker compose -f docker-compose.prod.yml up -d`,
   or build this checkout with `docker compose up -d --build`.
4. Open `http://127.0.0.1:8080` and sign in as `admin` using the configured password.
5. On the TV, open YouTube **Settings > Link with TV code**. Enter the code in
   the dashboard, then select **Save Changes**. The worker applies the configuration
   automatically. A YouTube API key is only needed for channel whitelisting.

For LAN access, set `DASHBOARD_BIND_IP` to the server's LAN address. HTTP Basic
credentials need HTTPS across untrusted networks; use an HTTPS reverse proxy
for remote access. Password files are supported through `DASHBOARD_PASSWORD_FILE`;
mount the file read-only and make it readable by the container user.
Change the username with `DASHBOARD_USERNAME`.

Both containers share `/app/data/config.json`. Import existing configurations
through the dashboard or place them in this directory before startup.
Keep a copy of the original before migrating. Empty installations wait for
pairing; offline TVs do not make the application unhealthy. TV-code pairing
requires no privileged mode, host networking, or Docker socket.

### TrueNAS

The community catalog contribution is being prepared against
[the existing app request](https://github.com/truenas/apps/issues/3749).
Until accepted, install `docker-compose.prod.yml` as a Custom App, replacing
`./data` with a dedicated writable dataset/folder and supplying dashboard
credentials. Use a unique Web UI port and your NAS LAN address. Avoid running
multiple workers against the same paired TVs while testing a replacement.

### Development checks

```sh
pip install -r requirements.txt -r dashboard/backend/requirements.txt -r requirements-dev.txt
pytest -q
cd dashboard/frontend
npm ci
npm run lint
npm run build
```

[![ghcr.io Pulls](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fipitio.github.io%2Fbackage%2Fdmunozv04%2FiSponsorBlockTV%2Fisponsorblocktv.json&query=downloads&logo=github&label=ghcr.io%20pulls&style=flat)](https://ghcr.io/dmunozv04/isponsorblocktv)
[![Docker Pulls](https://img.shields.io/docker/pulls/dmunozv04/isponsorblocktv?logo=docker&style=flat)](https://hub.docker.com/r/dmunozv04/isponsorblocktv/)
[![GitHub Release](https://img.shields.io/github/v/release/dmunozv04/isponsorblocktv?logo=GitHub&style=flat)](https://github.com/dmunozv04/iSponsorBlockTV/releases/latest)
[![GitHub Repo stars](https://img.shields.io/github/stars/dmunozv04/isponsorblocktv?style=flat)](https://github.com/dmunozv04/isponsorblocktv)

iSponsorBlockTV is a self-hosted application that connects to your YouTube for TV
app (see compatibility below) and automatically skips segments (like Sponsors
or intros) in YouTube videos using the [SponsorBlock](https://sponsor.ajay.app/)
API. It can also auto mute and press the "Skip Ad" button the moment it becomes
available on YouTube ads.

## Installation

Check the [wiki](https://github.com/dmunozv04/iSponsorBlockTV/wiki/Installation)

## Compatibility

Legend: ✅ = Working, ❌ = Not working, ❔ = Not tested

Open an issue/pull request if you have tested a device that isn't listed here.

| Device             | Status |
|:-------------------|:------:|
| Apple TV           |   ✅*   |
| Samsung TV (Tizen) |   ✅    |
| LG TV (WebOS)      |   ✅    |
| Android TV         |   ✅    |
| Chromecast         |   ✅    |
| Google TV          |   ✅    |
| Roku               |   ✅    |
| Fire TV            |   ✅    |
| CCwGTV             |   ✅    |
| Nintendo Switch    |   ✅    |
| Xbox One/Series    |   ✅    |
| Playstation 4/5    |   ✅    |

*Ad muting won't work when using AirPlay to send the audio to another speaker.

** Shorts aren't fully supported due to limitations on YouTube's side.
A single short can be seen by either selecting the "Disconnect" option in the
 warning shown
or by long pressing the thumbnail to open the menu and clicking play from there

## Usage

Run iSponsorBlockTV on a computer that has network access. It doesn't need to
be on the same network as the device, only access to youtube.com is required.

Auto discovery will require the computer to be on the same network as the device
during setup.
The device can also be manually added to iSponsorBlockTV with a YouTube TV code.
This code can be found in the settings page of your YouTube TV application.

## Libraries used

- [pyytlounge](https://github.com/FabioGNR/pyytlounge) Used to interact with the
  device
- asyncio and [aiohttp](https://github.com/aio-libs/aiohttp)
- [async-cache](https://github.com/iamsinghrajat/async-cache)
- [Textual](https://github.com/textualize/textual/) Used for the amazing new
  graphical configurator
- [ssdp](https://github.com/codingjoe/ssdp) Used for auto discovery

## Projects using this project

- [Home Assistant Addon](https://github.com/bertybuttface/addons/tree/main/isponsorblocktv)

## Contributing

1. Fork it (<https://github.com/dmunozv04/iSponsorBlockTV/fork>)
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create a new Pull Request

## Contributors

[![Contributors](https://contrib.rocks/image?repo=dmunozv04/iSponsorBlockTV)](https://github.com/dmunozv04/iSponsorBlockTV/graphs/contributors)

Made with [contrib.rocks](https://contrib.rocks).

## License

[![GNU GPLv3](https://www.gnu.org/graphics/gplv3-127x51.png)](https://www.gnu.org/licenses/gpl-3.0.en.html)
