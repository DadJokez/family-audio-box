# Software architecture

FamilyBox is a local application, not a thin client. One Python process owns
device orchestration, persistence, and the parent web UI; one long-lived mpv
child process owns decoding and audio output. SQLite and media remain on the
device. Internet, a future family service, and the web UI are never in the
physical playback path.

## Dependency direction

```text
GPIO / PN532 adapters                    FastAPI + Jinja
          |                                     |
          v                                     v
     hardware events ----> PlayerService ----> PlaybackManager
                                |                      |
                                v                      v
                    repositories / SQLite      PlaybackEngine
                                |                      |
                       ContentProvider              mpv IPC
                                |
                    LocalContentProvider

AudioOutput HAL prepares/reports the system audio device at the composition root.
```

Dependencies point inward toward domain types and service interfaces.
Raspberry Pi imports stay under `hardware/raspberry_pi`; fake implementations
stay under `hardware/fake`. Domain models do not import GPIO Zero, Blinka,
FastAPI, SQLite, or mpv. Provider-specific code does not enter NFC or playback
services.

## Runtime components

### Domain

The domain package defines identifiers, entity-shaped values, playback status,
and events such as `tag_present(uid)`, `tag_removed(uid)`, and
`unknown_tag(uid)`. UIDs are normalized once at the hardware boundary to a
stable uppercase hexadecimal representation without provider meaning. A UID
is an opaque convenience key, not an authentication secret: duplicate or
emulated UIDs must resolve predictably but do not prove an object's identity.

The domain does not decide how a UID was read or how an audio file is decoded.
That separation keeps the same event and player tests runnable on macOS and
Linux without GPIO hardware.

### Hardware abstraction layer

The five hardware interfaces are `NfcReader`, `ButtonController`,
`VolumeController`, `PowerMonitor`, and `AudioOutput`. Every interface has a
Raspberry Pi implementation and a fake implementation. Construction happens at
the composition root according to `FAMILYBOX_HARDWARE=fake|raspberry_pi`; audio
selection is independently explicit through `FAMILYBOX_AUDIO=fake|mpv`.
Services never perform platform detection themselves, and a physical
configuration never silently falls back to fakes.

The Raspberry Pi NFC adapter uses PN532 over SPI0. This is an intentional
exception to the original I2C preference because the current
[Adafruit PN532 guide](https://learn.adafruit.com/adafruit-pn532-rfid-nfc?view=all#python-computer-wiring-2986203)
states that PN532 I2C is unreliable on Raspberry Pi. Controls use GPIO Zero with
BCM numbering and active-low internal pull-ups, following the
[GPIO Zero input API](https://gpiozero.readthedocs.io/en/stable/api_input.html).

Fake hardware is behavioral, not a second application mode: it emits the same
events and accepts the same output commands. Development-only HTTP triggers may
drive fakes when `FAMILYBOX_DEV_ENDPOINTS=true`, but must be disabled on a
physical box.

### NFC service

The NFC service polls continuously without blocking the rest of the player. It
turns repeated reader samples into edge events:

```text
absent --stable same UID--> present(uid) --stable no-read--> absent
   ^                              |
   +---------- removed(uid) ------+
```

`FAMILYBOX_NFC_PRESENT_SAMPLES` and `FAMILYBOX_NFC_REMOVED_SAMPLES` debounce
noisy readings.
Repeated samples of an already-present UID produce no duplicate event. A new
UID replaces the current presence only after it is stable. Resolution is a
service concern: a stable UID with no `Tag` row emits `unknown_tag(uid)` and is
made visible to the web UI without mutating the physical tag.

Removing the active object pauses by default. Replacing the same object resumes
from in-memory state or the device-specific persisted position. Assigning an
unknown UID in the UI commits the tag mapping first; the next service
resolution uses it immediately without restart.

### Content resolution and providers

The resolver maps a known tag to `Content`, then asks the named provider to
materialize a playable item/queue. The provider contract returns provider-
neutral track references and metadata; it does not issue playback commands.

V1 implements only `LocalContentProvider` for a single mpv-supported file or an
ordered local folder/playlist. Ordering must be deterministic and stored or
derived once during import, not depend on filesystem enumeration order.

Future LibriVox, podcast, Storynory, HTTP stream, commercial-service, NAS, and
family-sync adapters remain outside V1. Their names may appear in architecture
notes or provider values, but V1 must not make network requests, import their
SDKs, or add provider branches to the player.

### Playback manager and mpv adapter

The playback manager owns one logical queue, current track index, state, and
volume. The mpv adapter starts a single idle mpv process and controls it through
a permission-restricted Unix-domain JSON IPC socket. It does not spawn one mpv
process per button press or track. The stable mpv manual specifically
recommends `--input-ipc-server` for programmatic control and warns that the IPC
protocol is not secure; keep the socket local and out of the web surface. See
the [mpv JSON IPC manual](https://mpv.io/manual/stable/#json-ipc).

Physical commands pass through the player service and web commands call the
same playback manager. Its lock serializes both paths. Only the playback layer
translates neutral operations such as play, pause, next, seek, and volume into
mpv commands/properties.

Before changing content, the manager captures and persists the old queue's
track and position. It also persists on pause, approximately every
`FAMILYBOX_PROGRESS_SAVE_INTERVAL` seconds while playing long-form content,
and during graceful shutdown. It does not write on every position observation
or encoder step.

### Persistence

SQLite is the only database. Ordered migrations create and evolve `Device`,
`Child`, `Content`, `Tag`, and `PlaybackState`. Application code uses
repositories/transactions rather than SQL in GPIO, provider, playback, or web
modules.

Playback state identity is `(device_id, content_id)`. It must never be keyed by
child or content alone. Stable UUID-shaped IDs and provider references leave
room for a future family catalog without changing offline ownership: each box
continues to own its playback position and cached files. The Pi installer
generates `FAMILYBOX_DEVICE_ID` once and preserves the environment file on
updates; include `/etc/familybox/familybox.env` in a device backup so renaming
the hostname cannot accidentally create a new playback identity.

Keep the database on the local microSD filesystem, not a network mount. Writes
are short and serialized. V1 uses WAL with exactly one application connection
guarded by a lock; this permits UI reads around short progress writes without
multiple writers or competing checkpoints. Keep the WAL and shared-memory files
with the database during backup and test power-loss recovery. SQLite's current
[WAL documentation](https://www.sqlite.org/wal.html) describes checkpoint
behavior and a WAL-reset race fixed in SQLite 3.51.3 and designated backports.
That race requires separate concurrent connections, which this process model
avoids; nevertheless, install current Raspberry Pi OS updates and require a
patched/backported SQLite before introducing another writing connection or
process.

### Web adapter

FastAPI routes render Jinja2 templates; a small framework-free script polls
status and submits controls. The web layer queries services and repositories
and submits commands, but it does not own playback state.
Closing a browser or crashing a route must not cancel the NFC loop or mpv.

V1 has no elaborate account system. Bind to the configured LAN address, do not
port-forward the admin UI, and treat anyone on the trusted local network as an
administrator. State-changing endpoints use POST (or another non-GET method)
and validate content/tag IDs. Uploaded or imported paths must remain beneath
the configured media root.

Avahi publishes the host's `.local` name independently of the application.
Avahi implements mDNS/DNS-SD on the local network; see the
[Avahi project description](https://avahi.org/). Each player needs a unique
hostname such as `familybox-alice`, `familybox-ben`, and `familybox-cara`.

## Service ownership and concurrency

At startup, the composition root performs these steps in order:

1. Load and validate configuration and create the mutable data directories.
2. Construct the explicitly selected Pi or fake adapters.
3. Open SQLite and apply pending migrations transactionally.
4. Resolve or create this device's stable identity.
5. Prepare the system audio output and start the selected playback engine.
6. Subscribe the player service and start hardware polling/event tasks.
7. Complete the application lifespan so the web server begins accepting requests.

Hardware callbacks enqueue small events; they do not perform database work or
wait for mpv. The player service consumes commands in order. Database writes
and mpv request/response pairs are serialized so a web click cannot interleave
half a transition with an NFC removal. Slow artwork or library work runs away
from the latency-sensitive command path.

Shutdown reverses ownership: stop accepting new events, pause/query mpv, save
progress in one short transaction, close hardware adapters, terminate mpv, and
close SQLite. systemd sends SIGTERM and allows a bounded grace period before
forcing the process group down.

## Playback transition rules

| Input | Current state | Required result |
| --- | --- | --- |
| Known tag appears | Idle | Resolve queue, restore this device's state, play. |
| Same tag repeats | Playing or paused | No duplicate load or seek. |
| Active tag is removed | Playing | Capture position, persist, pause. |
| Same tag returns | Paused by removal | Resume without rebuilding unrelated state. |
| Different known tag appears | Any content active | Persist old content, load and restore new content, play. |
| Unknown tag appears | Any | Record last unknown UID for UI; do not destroy current mapping or write the tag. |
| Play/pause button | Content loaded | Toggle pause/resume. |
| Next/previous | Queue loaded | Persist the old track transition and load the adjacent track with defined boundary behavior. |
| Encoder step | Any | Clamp volume to the configured safe range and update mpv; coalesce persistence if volume is stored. |
| Shutdown | Any | Persist active position once, then release resources. |

## Failure boundaries

- No network: physical playback and all local media continue; `.local` and the
  web UI may be unreachable.
- Web error: return an error response and log it; do not tear down the player.
- Unknown or malformed tag read: normalize/validate at the adapter boundary and
  ignore unsafe data without stopping the poll loop.
- Missing local track: report the content as unavailable, preserve its database
  record and progress, and remain ready for another tag.
- mpv exits: mark playback unavailable, retain the last known state, and allow
  bounded adapter restart/reconnection rather than starting competing players.
- SQLite write failure or full disk: keep control handling safe, surface a
  degraded status, and avoid claiming that progress was saved.
- GPIO/NFC initialization failure: expose hardware status and keep the web
  process diagnosable when possible; never silently switch a physical device to
  fake hardware.

Structured logs include component, event/action, device ID, content ID where
applicable, and an error category. Do not log credentials or entire uploaded
metadata blobs. UID logging is acceptable for administration but should remain
local to the box.

## Files and permissions

```text
/opt/familybox/             root-owned application and virtual environment
/srv/familybox/media/       familybox-owned imported media
/srv/familybox/data/        SQLite database and migration state
/srv/familybox/cache/       regenerable application cache
/srv/familybox/logs/        optional local log files; journald is primary
/run/familybox/             ephemeral mpv IPC socket
/etc/familybox/             root-managed service environment
```

The systemd service runs as the unprivileged `familybox` user with supplemental
`gpio`, `spi`, and `audio` groups. Code and service configuration are read-only
to that user; only `/srv/familybox` and `/run/familybox` are writable. On the Pi,
the service receives only `CAP_NET_BIND_SERVICE` so the web UI can bind port 80
without running as root. The web server and mpv do not run as root.

## Testing strategy

Unit tests use fake NFC, buttons, encoder, power monitor, and audio output to
cover debounce and the transition table deterministically. A fake clock avoids
one-minute waits in progress tests. Integration tests use a temporary SQLite
database and temporary media tree, exercise migrations, provider ordering, tag
assignment, and device-specific progress, and replace mpv IPC when audio is not
under test.

Hardware smoke tests are a separate Pi test layer: PN532 firmware query and UID
cycles, ALSA device discovery and a low-volume tone, every control edge, systemd
restart, power-cycle progress recovery, network-disconnected playback, and
OnOff SHIM shutdown. A passing fake-hardware suite is necessary but cannot
validate wiring, antenna placement, power stability, or audio noise.

## Future family synchronization boundary

A future family service may own a master catalog, tag assignments, artwork,
media manifests, and device inventory. Synchronization is an adapter at the
edge: it imports versioned catalog facts and downloads complete files into the
local cache. It cannot become a synchronous dependency of UID resolution or
playback.

Conflicts resolve by entity/version rules, while `PlaybackState` remains
device-scoped. A box always boots from its last valid local catalog and media.
No commercial provider becomes mandatory, and provider credentials never need
to exist on boxes that do not use that provider.
