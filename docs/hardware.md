# Hardware guide

FamilyBox V1 is a bench-build around a Raspberry Pi Zero 2 W. It uses only
off-the-shelf modules, a protected USB power bank, and connectors or soldered
joints that can be inspected and replaced. Do not put a loose lithium cell or
an unprotected charge/boost board inside the V1 enclosure.

## V1 bill of materials

| Part | Minimum requirement | Notes |
| --- | --- | --- |
| Compute | Raspberry Pi Zero 2 W | Raspberry Pi OS Lite, 64-bit; solder a 40-pin header if the board does not have one. |
| Storage | Quality microSD card, 16 GB or larger | Audio capacity, not application code, determines the useful size. Keep a restorable image or configuration backup. |
| NFC | PN532 13.56 MHz breakout/module | The module must expose hardware SPI and support ISO/IEC 14443-A. Mode-select switches and labels vary by vendor. |
| Audio | MAX98357A I2S mono Class-D amplifier breakout | Use a breakout intended for 3.3 V logic and 5 V power. |
| Speaker | 3-inch, 4-ohm, approximately 3 W moving-coil speaker | Connect directly to the amplifier's `+` and `-` outputs. Neither speaker lead is ground. |
| Volume | Incremental rotary encoder with push switch | A detented mechanical encoder such as an EC11 is appropriate. |
| Transport | Three normally-open momentary buttons | Previous, play/pause, and next. |
| Power | Enclosed 5,000 mAh USB power bank | It must supply a stable 5 V rail at the Pi and amplifier's peak load and must tolerate the OnOff SHIM's switching behavior. |
| Power control | Pimoroni OnOff SHIM | Uses BCM GPIO17 as the shutdown trigger and BCM GPIO4 as the power-off signal. |

Add hookup wire, heat-shrink, a small ground/5 V distribution point, strain
relief, screw terminals or locking connectors, spacers, and screws. Label both
ends of every removable cable with its signal name.

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

Power the Pi through the OnOff SHIM's input, following Pimoroni's product
instructions; do not simultaneously feed the Pi through another 5 V input.
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
   lists the current 64-bit Lite image and Zero 2 W compatibility. Set a unique
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
7. Install and power through the OnOff SHIM, rerun the installer with
   `--with-onoff-shim`, then perform the shutdown test above.
8. Add strain relief and insulating mounts before any portable use.

## Bench diagnostics

After the installer-requested reboot:

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
- Record the actual PN532 board revision, mode-switch position, power-bank
  model, speaker part, and wire colors for each of the three players.
- Never substitute a 2-ohm speaker or tie either class-D output to ground.
- Treat frayed wires, hot cells, swelling, odor, intermittent resets, or a hot
  amplifier as a stop-use condition.
