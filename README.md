# FamilyBox

FamilyBox is an open-source, local-first audio player for children. Place an
NFC-equipped card, toy, or figure on the box and a local story starts where
that specific player left off. Remove the object to pause; replace it to
resume.

The first release targets Raspberry Pi 3 Model A+, PN532 NFC, a MAX98357A I²S
amplifier, physical playback controls, and a small server-rendered FastAPI
administration site. It does not emulate or depend on Toniebox.

## What is implemented

- Local MP3, M4A, and M4B content, including ordered multi-file books
- Provider-neutral content and playback boundaries
- One long-lived mpv process controlled through JSON IPC
- NFC present, removed, and unknown-tag events with debounce
- Pause-on-removal and resume-on-replacement behavior
- Device-specific SQLite playback progress, saved at quiet checkpoints
- Fake NFC, buttons, encoder, power monitor, and audio for development/tests
- Raspberry Pi PN532, GPIO controls, and mpv adapters behind the same interfaces
- Responsive pages for now playing, library import/edit/delete, tag assignment,
  and device health
- systemd, Avahi/mDNS, and Raspberry Pi installation assets

Future internet providers and family synchronization are represented by stable
interfaces and IDs only. They are deliberately not implemented in V1.

## Development quick start

FamilyBox requires Python 3.11 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
./scripts/dev.sh
```

Open <http://127.0.0.1:8080>. The development server uses fake hardware and a
git-ignored `.familybox/` data directory. On the **Device** page, place and
remove a simulated NFC tag. Import a story in **Library**, place the simulated
tag, then assign the unknown UID in **NFC tags**.

To exercise actual audio on a development machine, install `mpv` and start with:

```sh
FAMILYBOX_AUDIO=mpv ./scripts/dev.sh
```

No phone, internet connection, hosted API, or JavaScript build is needed.

## Tests and checks

```sh
pytest
ruff check .
mypy src/familybox
python -m build
```

Unit and integration tests use temporary SQLite databases and fake hardware.
The mpv IPC tests use a fake Unix socket server, so CI does not need speakers.

## Raspberry Pi

Start with Raspberry Pi OS Lite 64-bit on a Pi 3 Model A+. The Zero 2 W remains
an optional compact variant using the same GPIO assignments. Review
[hardware](docs/hardware.md) and [wiring](docs/wiring.md) before applying power.
The current Adafruit PN532 guidance recommends **SPI on Raspberry Pi** because
the Pi I²C controller has clock-stretching limitations; SPI is therefore the
supported V1 connection despite I²C being the initial preference.

From a checkout on the Pi:

```sh
sudo ./scripts/install-pi.sh --hostname familybox-alice
sudo reboot
```

The installer creates an unprivileged `familybox` service account, installs the
application under `/opt/familybox`, creates media/data/cache/log directories
under `/srv/familybox`, enables required interfaces and Avahi, and installs the
systemd unit. Device-specific settings live in
`/etc/familybox/familybox.env`.

After the service starts, browse to `http://familybox-<device>.local` from a
device on the same network.

## Repository map

```text
src/familybox/
├── content/       provider contract and local media provider
├── domain/        hardware-free entities and events
├── hardware/      protocols, fake devices, and Raspberry Pi adapters
├── persistence/   SQLite repository and ordered migrations
├── playback/      persistent mpv IPC and playback orchestration
├── services/      NFC and player event loops
└── web/           FastAPI routes, Jinja templates, and static assets
```

The full component and event flow is described in
[architecture.md](docs/architecture.md). Product requirements and acceptance
criteria are in [SPEC.md](SPEC.md).

## Data and media

On a player, mutable files are separate from application code:

```text
/srv/familybox/
├── media/<content-id>/
├── data/familybox.db
├── cache/
└── logs/
```

SQLite uses foreign keys, WAL mode, and ordered migrations. Playback state is
keyed by `(device_id, content_id)`. Content and device IDs are UUID strings so a
future family catalog can synchronize records without changing V1 identities.

FamilyBox writes progress roughly once per minute while playing and also at
pause, content change, and graceful shutdown. It does not write every position
update to the microSD card.

## Security boundary

V1 is intended for a trusted home network and intentionally has no account
system. Anyone who can reach the admin page can control playback, import files,
change assignments, and delete local content. Put untrusted clients on a
separate network or firewall the device until authentication is added.

Physical playback does not depend on the administration site. If Wi-Fi, mDNS,
or the browser UI fails, the NFC and button event loops continue in the same
local process.

## Hardware and power safety

The current Pi 3A+ bench build uses an enclosed USB power bank without a power
controller: run `sudo poweroff`, wait for microSD activity to cease, and then
disconnect it. The final portable design requires a tested clean-shutdown and
power-cutoff solution; the Pimoroni OnOff SHIM remains the documented option.
The project does not use loose lithium cells. Disconnect power while wiring.
Confirm amplifier and speaker connections before enabling I²S, and never attach
a speaker output to a GPIO pin.

## License

MIT. See [LICENSE](LICENSE).
