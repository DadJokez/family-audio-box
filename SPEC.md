# FamilyBox V1 specification

## Product intent

FamilyBox is a repairable, inexpensive, child-operated physical audio player.
An NFC object selects content; the object stores no FamilyBox configuration.
Every player remains useful without the internet, a phone, a provider API, or a
future family server.

V1 is designed with three independent players in mind. It does not yet include
a central server, synchronization, or commercial provider integration.

## Experience contract

1. A child places an ISO14443-A NFC object on the reader.
2. The NFC service emits one debounced presentation event with its normalized UID.
3. The resolver looks up that UID in the local database.
4. Known content loads through a provider-neutral descriptor and starts or resumes.
5. Removing the active object pauses and persists playback.
6. Replacing the object resumes the same device’s saved position.
7. The rotary encoder changes volume; its switch and the dedicated buttons are
   available to the player service.
8. Previous, play/pause, and next controls work physically and from the web UI.
9. Progress survives graceful restart and ordinary power cycles.
10. An unknown UID appears in the administration UI and can be assigned without
    restarting the process.

Normal playback must not require a phone or browser.

## V1 content

The local content provider accepts:

- `.mp3`
- `.m4a`
- `.m4b`
- one-file items
- ordered multi-file folders/books

The provider returns a generic content descriptor and ordered tracks. NFC and
playback code must not contain local-filesystem-specific branching.

The following providers are architectural examples only and are out of scope
for implementation: LibriVox, podcasts/RSS, Storynory, HTTP streams, Spotify,
Apple Music, Audible, NAS libraries, and family synchronization.

## Hardware target

- Raspberry Pi 3 Model A+ with Raspberry Pi OS Lite 64-bit
- PN532 13.56 MHz reader, ISO14443-A / MIFARE Classic UID reads
- MAX98357A mono I²S Class-D amplifier
- 3-inch, 4-ohm, approximately 3 W speaker
- enclosed 5,000 mAh USB power bank
- Clean-shutdown and power-cutoff controller for the final portable build;
  Pimoroni OnOff SHIM is the currently documented option

### Pin allocation

| Function | BCM GPIO |
|---|---:|
| I²S BCLK | 18 |
| I²S LRCLK | 19 |
| I²S DIN | 21 |
| Encoder A | 23 |
| Encoder B | 24 |
| Encoder push | 25 |
| Previous button | 5 |
| Play/pause button | 6 |
| Next button | 13 |
| PN532 SPI MOSI | 10 |
| PN532 SPI MISO | 9 |
| PN532 SPI SCLK | 11 |
| PN532 SPI CE0 | 8 |
| OnOff SHIM (reserved) | 4, 17 |

Buttons use internal pull-ups and connect to ground. GPIO4 and GPIO17 are never
claimed by application controls. PN532 SPI is the supported V1 mode because
current vendor documentation identifies Raspberry Pi I²C clock stretching as
unreliable for this reader.

## Software boundaries

### Hardware abstraction

`NfcReader`, `ButtonController`, `VolumeController`, `PowerMonitor`, and
`AudioOutput` define the application-facing hardware contract. Each has a fake
development implementation and a Raspberry Pi or mpv implementation. Optional
Pi modules are imported only when Raspberry Pi mode is selected.

### NFC service

The service continuously samples the reader, normalizes UIDs, debounces
duplicate readings, and emits:

- `tag_present(uid)`
- `tag_removed(uid)`
- `unknown_tag(uid)`

An unknown event is an observation, not a write to the tag. Removing a tag
pauses by default.

### Content resolver

The resolver maps `UID -> Tag -> Content -> provider descriptor`. Provider code
does not leak into NFC or playback services.

### Playback manager

A single long-running mpv process is controlled using its JSON IPC Unix socket.
The manager owns queue selection, play/pause, track navigation, seek, volume,
status, and resume. It never starts a separate mpv process per button press or
track.

Progress is persisted:

- approximately every 60 seconds while playing
- when pausing
- before changing content
- during graceful shutdown

Periodic UI reads do not write to SQLite.

### Web administration

FastAPI and Jinja render four responsive pages with a small local JavaScript
enhancement layer and no frontend build:

- **Now playing:** title, artwork, track, progress, volume, NFC UID, controls
- **Library:** upload/import, edit title/artwork, delete, inspect tracks
- **NFC tags:** known mappings, last unknown UID, immediate assignment
- **Device:** identity, hostname/address, disk, version, uptime, hardware state

The site is expected at `http://familybox-<device>.local` through Avahi. It has
no V1 authentication and is for a trusted home LAN.

Web failure must not stop the physical event loops.

## Persistence

SQLite is the only V1 datastore. Schema changes are ordered migrations.

Core records:

- `devices(id, name, child_id, created_at)`
- `children(id, name, settings, created_at)`
- `contents(id, title, content_type, provider, provider_reference, local_path,
  artwork_path, metadata, created_at)`
- `content_tracks(id, content_id, track_index, title, local_path, metadata)`
- `tags(uid, content_id, name, created_at)`
- `playback_states(device_id, content_id, track_index, position_seconds,
  completed, updated_at)`
- local NFC observation/app state needed for the most recent unknown tag

The playback-state primary key is `(device_id, content_id)`. One child or box
cannot move another player’s audiobook position.

Mutable data lives under `/srv/familybox`; application code lives under
`/opt/familybox`.

## Operational properties

- The system starts through systemd after local filesystems and sound are ready.
- Structured logs go to stdout/journald; local log directories remain available
  for future exports.
- SQLite uses WAL and bounded checkpoint writes suitable for one local process.
- SIGTERM triggers service shutdown and a final progress save.
- Hardware failures are logged and surfaced in device status without importing
  hardware modules on development computers.
- Content filenames and paths are validated before writes or deletion.
- Playback, database, and media lookup never require internet access.

## Explicitly deferred

- central accounts or remote administration
- distributed locks, queues, or service discovery beyond mDNS
- family catalog/synchronization implementation
- network-provider API clients
- downloading/caching free content
- enclosure CAD
- integrated lithium/UPS design
- DRM or commercial provider workarounds

## Acceptance criteria

A bench player is V1-complete when it can:

1. boot Raspberry Pi OS Lite and start FamilyBox automatically;
2. detect a supported NFC UID;
3. resolve it to a local audiobook;
4. start from the beginning or the saved device-specific position;
5. pause when the object leaves;
6. resume when it returns;
7. adjust volume with the encoder;
8. navigate and toggle playback with physical buttons;
9. preserve position through reboot;
10. assign a new tag from a phone browser;
11. expose useful device status over mDNS; and
12. repeat the entire playback flow with the internet disconnected.

Software acceptance additionally requires automated tests for fake hardware,
NFC debounce/events, migrations/repositories, local imports, player behavior,
mpv IPC framing, and primary web workflows.
