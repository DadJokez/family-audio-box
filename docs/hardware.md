# Hardware guide

FamilyBox V1 targets a Raspberry Pi 3 Model A+. A Raspberry Pi Zero 2 W remains
an optional compact variant using the same GPIO allocation, but it is not a
required purchase or the basis of the V1 enclosure.

Use only off-the-shelf modules, a protected USB power bank, and connectors or
soldered joints that can be inspected and replaced. Do not put a loose lithium
cell or an unprotected charge/boost board inside the V1 enclosure.

## V1 bill of materials

| Part | Minimum requirement | Notes |
| --- | --- | --- |
| Compute | Raspberry Pi 3 Model A+ | Raspberry Pi OS Lite, 64-bit. The board includes a 40-pin GPIO header. |
| Storage | Quality microSD card, 16 GB or larger | Audio capacity, not application code, determines the useful size. Keep a restorable image or configuration backup. |
| NFC | PN532 13.56 MHz breakout/module | The module must expose hardware SPI and support ISO/IEC 14443-A. Mode-select switches and labels vary by vendor. |
| Audio | MAX98357A I2S mono Class-D amplifier breakout | Use a breakout intended for 3.3 V logic and 5 V power. |
| Speaker | 3-inch, 4-ohm, approximately 3 W moving-coil speaker | Connect directly to the amplifier's `+` and `-` outputs. Neither speaker lead is ground. |
| Volume | Incremental rotary encoder with push switch | A detented mechanical encoder such as an EC11 is appropriate. |
| Transport | Three normally-open momentary buttons | Previous, play/pause, and next. |
| Power | Enclosed 5,000 mAh USB power bank | It must supply a stable 5 V rail at the Pi and amplifier's peak load. A final power controller must be tested with the selected bank. |
| Power control | Clean shutdown and true power cutoff | Deferred during bench validation. The currently supported final-build option is a Pimoroni OnOff SHIM, using BCM GPIO17 and BCM GPIO4. |

Add hookup wire, heat-shrink, a small ground/5 V distribution point, strain
relief, screw terminals or locking connectors, spacers, and screws. Label both
ends of every removable cable with its signal name.

## Current bench parts (August 2026)

This is the actual one-player procurement list. The Amazon entries were
verified against the August 27, 2026 order confirmation and order history;
unrelated household items were excluded. Multipacks leave spares, and their
quantity does not mean that the first player needs every item in the pack.

| Purpose | Selected part | Source and status | Notes |
| --- | --- | --- | --- |
| Computer | Raspberry Pi 3 Model A+, SKU 850289 | Micro Center Marietta; buy in store | Standard V1 board. Use its dimensions for the first enclosure. |
| Storage | SanDisk Ultra 64 GB microSD card with adapter, ASIN B0G8KLQ64L | Amazon; ordered August 27, 2026 | More than enough capacity for the OS and a useful audio library. |
| NFC reader | HiLetgo PN532 13.56 MHz SPI/I2C/UART module, ASIN B0CDWZ7SM9 | Amazon; ordered August 27, 2026 | Configure and use it in SPI mode. |
| Audio amplifier | AITRIP MAX98357A, three-pack, ASIN B0GCM7QRP6 | Amazon; ordered August 27, 2026 | One board is needed; the other two are spares. |
| Speaker | GRS 3FR-4 3-inch 4-ohm full-range speaker, ASIN B00K2ESJZ2 | Amazon; ordered August 27, 2026 | One speaker. |
| Transport controls | 24-piece assorted-color 16 mm momentary button set, ASIN B08SKJ6V7Z | Amazon; ordered August 27, 2026 | Use three distinguishable colors for previous, play/pause, and next. |
| Volume control | Keyestudio KS0013 rotary encoder module, SKU 078758 | Micro Center order; hold for voltage verification | The [manufacturer lists a 5 V supply](https://wiki.keyestudio.com/Ks0013_keyestudio_Rotary_Encoder_Module), but Pi GPIO is 3.3 V-only. Do not wire it until the exact board is inspected; replace it with a bare EC11 or explicitly 3.3 V-safe module if needed. |
| Power | Miady 5,000 mAh USB power banks, two-pack, ASIN B08T8TDS8S | Amazon; ordered August 27, 2026 | One bank is needed; keep the second as a spare. |
| GPIO prototyping | Keyestudio Raspberry Pi GPIO breakout, ribbon cable, and 400-point breadboard, ASIN B072XBX3XX | Amazon; ordered August 27, 2026 | Use for bench wiring only; remove the breadboard from the final portable build. |
| Hookup wire | MECCANIXITY 26 AWG two-conductor red/black silicone wire, ASIN B0C6F7JRWM | Amazon; ordered August 27, 2026 | Best suited to paired power/speaker runs; the jumper bundle covers individual bench signals. |
| Jumper wire | Keyestudio KS0334 three-set 140-piece breadboard jumper bundle, SKU 301473 | Micro Center order | For temporary bench connections. |
| Mounting hardware | GeeekPi 220-piece M2.5 standoff kit, ASIN B07PHBTTGV | Amazon; ordered August 27, 2026 | Confirm screw length and clearance before tightening against any PCB. |
| Insulation | Assorted black heat-shrink tubing, 24-pack, SKU 797464 | Micro Center order | For permanent soldered joints, not loose breadboard connections. |
| Soldering tool | Weller 30 W soldering iron kit, SKU 491191 | Micro Center order | Confirm the kit includes suitable electronics solder before permanent assembly. |
| Diagnostics | AstroAI 2,000-count digital multimeter, ASIN B01ISAMUA6 | Amazon; ordered August 27, 2026 | Use continuity mode to identify encoder contacts and verify wiring with power disconnected. |
| Card reader | USB-A/USB-C SD and microSD reader, SKU 704346 | Micro Center order | For flashing and recovering the microSD card. |
| Pi power/data cable | USB-A to Micro-B cable, SKU 422618 | Micro Center order | Suitable for powering the Pi 3A+ during bench testing. |

## Supported computer plan

- **Primary V1: Raspberry Pi 3 Model A+.** It has the required ARM64 CPU,
  wireless networking, and 40-pin GPIO header. Raspberry Pi states that it will
  remain in production until at least January 2030.
- **Optional compact variant: Raspberry Pi Zero 2 W.** Keep software and GPIO
  compatibility, but do not depend on local retail availability. Raspberry Pi
  also lists its production lifetime through at least January 2030.
- **Future fallback: Raspberry Pi 4 Model B.** Consider it only if both smaller
  boards become impractical to source. Raspberry Pi lists production through at
  least January 2034, but it needs a larger mounting pattern, USB-C power, and a
  new power and thermal validation pass.

Use a replaceable internal mounting plate rather than making the outer
enclosure's structure depend directly on one board's mounting holes. This keeps
a later board migration mechanical instead of forcing a full enclosure redesign.

Official lifecycle and specification references:
[Pi 3 Model A+](https://www.raspberrypi.com/products/raspberry-pi-3-model-a-plus/),
[Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/), and
[Pi 4 Model B](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/).

## Deferred until the bench build passes

- Do not buy a Zero 2 W merely to match the original plan. Build and validate
  V1 on the Pi 3A+; revisit the Zero only for a genuinely size-constrained
  future build.
- Add a tested safe-power controller for the portable build. The Pimoroni
  OnOff SHIM remains supported, but do not buy the unusually marked-up Amazon
  listing. Source it near its normal low-cost price or evaluate a compatible
  alternative and update the GPIO, overlay, and wiring documentation together.
- Obtain electronics solder if the Weller kit does not include it. Do not make
  permanent joints without appropriate solder and basic strain relief.
- Design or buy the final enclosure only after the Pi 3A+, speaker, NFC range,
  battery load, and wiring layout pass testing. Use a replaceable board plate.
  The selected buttons require 16 mm mounting holes unless the controls change.
  The current CAD starting dimensions and fit-test plan are in the
  [radio enclosure V1 specification](radio-enclosure-v1.md).
- Buy additional NFC tags or objects only after confirming the included test
  card or fob reads reliably. Buy parts for additional players only after the
  first complete bench build passes.

## NFC interface decision: use SPI for V1

The original preference was I2C, but the documented exception applies. The
current Adafruit PN532 guide says that I2C and UART do not work reliably with
the PN532 on Raspberry Pi and directs Raspberry Pi users to SPI. Its example
also calls SPI the most reliable and universally supported interface. PN532
I2C uses clock stretching, while Raspberry Pi's Broadcom I2C controller has a
long-standing clock-stretching limitation. See the
[Adafruit PN532 Raspberry Pi wiring and Python guide](https://learn.adafruit.com/adafruit-pn532-rfid-nfc?view=all#python-computer-wiring-2986203)
and [Adafruit's clock-stretching explanation](https://learn.adafruit.com/working-with-i2c-devices/clock-stretching).

V1 therefore uses hardware SPI0:

- MOSI: GPIO10
- MISO: GPIO9
- SCLK: GPIO11
- chip select: CE0 / GPIO8

These are Raspberry Pi's documented SPI0 pins. See the
[Raspberry Pi GPIO and alternate-function reference](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header).
The application reads only the immutable UID; it never writes configuration to
a tag. Initial acceptance testing covers MIFARE Classic and other
ISO/IEC 14443-A tags that the selected module and library can identify.

I2C remains a possible hardware experiment, not a supported V1 configuration.
If it is revisited, it needs the PN532 `P32/H_Request` and reset wiring described
by Adafruit and reliability testing through removal, replacement, reboot, and
extended idle cycles. Do not merely slow the whole I2C bus and assume the
problem is solved. Raspberry Pi's documented non-interactive enablement command
is `sudo raspi-config nonint do_i2c 0`; FamilyBox deliberately does not run it
because no V1 component uses I2C. Any experiment also needs a new conflict-free
allocation for the request/reset GPIOs—the example GPIO numbers in a vendor
guide are not FamilyBox assignments. See the
[Raspberry Pi `raspi-config` interface options](https://www.raspberrypi.com/documentation/configuration/services/getting-started.html#non-interactive-raspi-config).

## Audio choices

The MAX98357A is powered from 5 V but accepts the Pi's 3.3 V I2S logic. It needs
BCLK, LRCLK/LRC, and DIN; it does not need MCLK. The specified connection is:

- BCLK: GPIO18
- LRCLK/LRC: GPIO19
- DIN: GPIO21

The current Raspberry Pi firmware supplies a `max98357a` Device Tree overlay.
Its default configuration claims GPIO4 for the amplifier's `SD_MODE` input.
GPIO4 belongs to the OnOff SHIM in this build, so FamilyBox must load
`dtoverlay=max98357a,no-sdmode`. The official overlay reference defines
`no-sdmode` as leaving the amplifier always on and documents GPIO4 as the
otherwise-default SD pin. See the
[Raspberry Pi overlay reference](https://github.com/raspberrypi/firmware/blob/master/boot/overlays/README#L3126-L3132).

That overlay registers the ALSA card as `MAX98357A`. The installer adds a
managed `/etc/asound.conf` block that makes `hw:CARD=MAX98357A,DEV=0` the
plug-converted default, so attaching an HDMI display cannot silently redirect
mpv. The card name comes from the
[official Raspberry Pi overlay source](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/arch/arm/boot/dts/overlays/max98357a-overlay.dts#L58-L72).

On the Adafruit-style breakout, leaving its SD/MODE pad alone selects the
board's default mono mix and leaving GAIN alone selects its default gain. Check
the documentation for the exact breakout in hand before assuming clone-board
resistor values. The MAX98357A output is bridge-tied: connect the speaker only
between `SPK+` and `SPK-`, never from either output to ground. Adafruit rates
its breakout at up to roughly 3 W into 4 ohms from 5 V and recommends allowing
at least 800 mA for the amplifier supply. See the
[MAX98357A pinout and electrical notes](https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp/pinouts)
and the [manufacturer product page](https://www.analog.com/en/products/max98357a.html).

Start with software volume low. A 3 W transducer at close range can be
uncomfortably loud, and clipping is hard on both the amplifier and speaker.
FamilyBox volume is digital in mpv; the encoder does not carry audio current.

## Controls

All application controls are active-low. Wire each button between its GPIO and
ground and use the Pi's internal pull-up. GPIO Zero documents this as the
default `Button` arrangement and provides software debounce through
`bounce_time`. The rotary encoder's A and B terminals go to their assigned
GPIOs and its common terminal goes to ground. Its push switch is wired like the
other buttons. See the
[GPIO Zero Button and RotaryEncoder reference](https://gpiozero.readthedocs.io/en/stable/api_input.html).

That direct-to-ground description applies to a bare mechanical encoder. The
purchased Keyestudio KS0013 is a module with support components, not a bare
encoder, and its manufacturer specifies a 5 V supply. Do not connect its `+`
pin to the Pi's 5 V rail: that could expose 3.3 V-only GPIO inputs to 5 V.
Inspect the exact board and verify 3.3 V operation before using it, or substitute
a bare EC11 encoder.

Use these BCM assignments exactly:

| Control | BCM GPIO |
| --- | ---: |
| Previous | 5 |
| Play/pause | 6 |
| Next | 13 |
| Encoder A | 23 |
| Encoder B | 24 |
| Encoder push | 25 |

Mechanical parts differ in pin order. Identify the encoder's common and switch
contacts with its datasheet or a continuity meter before applying power. If
turning clockwise lowers volume, swap A and B at the connector (or change the
direction setting), not unrelated GPIO assignments.

## Power and safe shutdown

The current Pi 3A+ bench build does not include an OnOff SHIM. Shut it down with
`sudo poweroff`, wait until Linux has stopped and microSD activity has ceased,
and only then disconnect the power bank. Do not enable the OnOff SHIM overlays
on this bench configuration.

For a later build that includes the OnOff SHIM, power the Pi through the SHIM's
input, following Pimoroni's product instructions; do not simultaneously feed
the Pi through another 5 V input.
Pimoroni identifies GPIO17 as the shutdown trigger and GPIO4 as the final
power-off signal in its
[clean-shutdown repository](https://github.com/pimoroni/clean-shutdown#supported-products).
Those pins are reserved exclusively for the SHIM.

FamilyBox uses the Raspberry Pi kernel's `gpio-shutdown` and `gpio-poweroff`
overlays when the installer is run with `--with-onoff-shim`. This avoids the
upstream Pimoroni userspace installer, which still has an open Raspberry Pi OS
Bookworm compatibility report. The kernel overlay behavior and warnings are
documented in the
[official Raspberry Pi overlay reference](https://github.com/raspberrypi/firmware/blob/master/boot/overlays/README#L1590-L1675),
and the exact OnOff SHIM `gpio-poweroff` parameters were published by Pimoroni
support in its
[OnOff SHIM guidance](https://forums.pimoroni.com/t/using-onoff-shim-with-recalbox/7981/2).

Only enable `gpio-poweroff` after the SHIM is installed and actually controls
the 5 V source. Raspberry Pi warns that using the overlay without external
hardware that removes power can leave the kernel in an undefined power-off
state. Bench-test all four cases before enclosing the electronics:

1. Button press requests an orderly shutdown.
2. Power is removed only after Linux has stopped.
3. A second press starts the Pi.
4. Record what `sudo systemctl reboot` does with the selected Pi/SHIM revision.

The kernel shutdown overlay reacts to a debounced press; it does not implement
Pimoroni's userspace one-second hold gesture. Protect the power control from
accidental child presses in the enclosure. Do not disconnect the power bank or
pull the SHIM's input while the activity LED shows microSD writes. Raspberry
Pi's overlay reference also warns that an active-low power signal can go low on
reboot. Until the actual build passes the reboot test, assume a remote reboot
may become a clean power-off that needs a physical button press to start again.

## Assembly order

1. Flash current Raspberry Pi OS Lite 64-bit with Raspberry Pi Imager. The
   [official OS download page](https://www.raspberrypi.com/software/operating-systems/)
   provides the current 64-bit Lite image. Set a unique
   hostname such as `familybox-alice`, configure Wi-Fi, and enable SSH in
   Imager.
2. With power disconnected, install the header and wire only the PN532. Select
   SPI mode using the exact module's silkscreen/manual; switch truth tables are
   not universal across PN532 boards.
3. Run `scripts/install-pi.sh`, reboot, and verify `/dev/spidev0.0` exists.
4. Read UIDs repeatedly, including rapid place/remove cycles and a ten-minute
   idle test.
5. Add the MAX98357A and speaker. Confirm the overlay appears in `aplay -l`,
   then test at low volume.
6. Add the encoder and transport buttons one at a time and verify no input is
   stuck active at boot.
7. For the current bench build, run `sudo poweroff`, wait for all microSD
   activity to stop, and then disconnect the power bank. Do not pass
   `--with-onoff-shim`.
8. After the core hardware passes, install the chosen safe-power controller.
   If it is an OnOff SHIM, rerun the installer with `--with-onoff-shim` and
   perform the shutdown test above.
9. Add strain relief and insulating mounts before any portable use.

## Bench diagnostics

After the installer-requested reboot, run the read-only readiness summary:

```sh
familybox-diagnostics --stage base
familybox-diagnostics --stage nfc
familybox-diagnostics --stage audio
```

The stages are cumulative and match the
[first hardware bring-up checklist](bring-up.md). Use only the stage physically
reached so unopened parts do not produce misleading failures. Omitting
`--stage` runs all checks.

It exits unsuccessfully if the Pi model, SPI0 device, GPIO character device,
MAX98357A ALSA card, or required boot configuration is missing. SPI device-node
presence does not prove that the PN532 itself is wired or configured correctly.

For additional detail:

```sh
cat /proc/device-tree/model; echo
ls -l /dev/spidev0.0 /dev/gpiochip* /dev/snd/
aplay -l
mpv --audio-device=help
mpv --no-video --audio-device=alsa/default --volume=10 /path/to/test-audio.mp3
systemctl status familybox.service avahi-daemon.service
journalctl -u familybox.service -b --no-pager
```

`i2cdetect` is not a PN532 diagnostic in the supported SPI build. For SPI, the
presence of `/dev/spidev0.0` verifies the controller and device node, not the
PN532 wiring or mode switches. A successful PN532 firmware-version query and
repeated UID reads are the meaningful end-to-end checks.

## Repairability rules

- Keep `/opt/familybox` (code) separate from `/srv/familybox` (media and state),
  and back up `/etc/familybox/familybox.env` with the database because it holds
  the device's stable ID.
- Use screws, threaded inserts, or captive nuts; do not glue serviceable boards.
- Keep the microSD card, power-bank connector, and enclosure fasteners
  accessible without disturbing the speaker cone.
- Put connectors between the lid controls and main electronics so the box can
  be opened without desoldering.
- Record the actual Pi model, PN532 board revision, mode-switch position,
  power-bank model, speaker part, and wire colors for each completed player.
- Never substitute a 2-ohm speaker or tie either class-D output to ground.
- Treat frayed wires, hot cells, swelling, odor, intermittent resets, or a hot
  amplifier as a stop-use condition.
