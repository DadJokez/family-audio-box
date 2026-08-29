# Wiring reference

All GPIO numbers in the application and this document use Broadcom (BCM)
numbering. Header pin numbers are physical positions on the 40-pin connector;
they are not interchangeable. Raspberry Pi documents BCM numbering, SPI0, and
the 40-pin header in its
[GPIO reference](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header).

Disconnect the power bank before adding or moving a wire. The Pi's GPIO inputs
are 3.3 V only. Never connect a 5 V signal to a GPIO pin.

## Complete pin allocation

| Function | Module signal | BCM GPIO | Physical pin | Electrical note |
| --- | --- | ---: | ---: | --- |
| PN532 power | 3.3V / VCC | — | 17 (3V3) | Use 3.3 V unless the exact module explicitly documents a regulated 5 V input. |
| PN532 ground | GND | — | 20 (GND) | Common ground. |
| PN532 SPI data out | MOSI | 10 | 19 | Pi SPI0 MOSI to PN532 MOSI. |
| PN532 SPI data in | MISO | 9 | 21 | Pi SPI0 MISO to PN532 MISO. |
| PN532 SPI clock | SCK / SCLK | 11 | 23 | Pi SPI0 SCLK. |
| PN532 chip select | SSEL / SS / CS | 8 | 24 | Pi SPI0 CE0, active low. |
| Amplifier power | VIN | — | 4 (5V) | Pi 5 V rail for the current bench build; use the controller's switched 5 V rail only in a future SHIM build. Budget for amplifier peaks. |
| Amplifier ground | GND | — | 14 (GND) | Common ground; keep the run short. |
| Amplifier bit clock | BCLK | 18 | 12 | I2S PCM clock. |
| Amplifier word clock | LRC / LRCLK / WS | 19 | 35 | I2S frame clock. |
| Amplifier data | DIN | 21 | 40 | I2S data from Pi to amplifier. |
| Previous button | contact | 5 | 29 | Other contact to ground; internal pull-up. |
| Play/pause button | contact | 6 | 31 | Other contact to ground; internal pull-up. |
| Next button | contact | 13 | 33 | Other contact to ground; internal pull-up. |
| Encoder channel A | A / CLK | 23 | 16 | Encoder common to ground; internal pull-up. |
| Encoder channel B | B / DT | 24 | 18 | Encoder common to ground; internal pull-up. |
| Encoder push | SW | 25 | 22 | Other switch contact to ground; internal pull-up. |
| OnOff SHIM logic power | 3.3V | — | 1 (3V3) | Native SHIM footprint; supplies its low-voltage logic. |
| OnOff SHIM power | 5V | — | 2 (5V) | Delivered by the SHIM from its USB input. Do not back-power the Pi. |
| OnOff SHIM ground | GND | — | 6 and 9 (GND) | Native SHIM footprint. |
| OnOff SHIM power-off | power-off | 4 | 7 | Reserved; driven low only at completed shutdown. |
| OnOff SHIM trigger | button / LED | 17 | 11 | Reserved shutdown input. |

Use a small distribution rail or properly spliced harness for additional 5 V
and ground connections instead of trying to force multiple loose wires under a
header contact. The listed power and ground pins are a suggested unambiguous
layout; all Pi ground pins share the same ground, and both 5 V header pins share
the switched 5 V rail when powered through the SHIM.

GPIO4 and GPIO17 are not general-purpose spare pins. They are reserved for the
OnOff SHIM. In particular, the MAX98357A overlay must include `no-sdmode`, or
its default configuration also claims GPIO4. The official overlay documents
that conflict in the
[Raspberry Pi firmware reference](https://github.com/raspberrypi/firmware/blob/master/boot/overlays/README#L3126-L3132).

## PN532 connections

Set the module to hardware SPI before applying power. On Adafruit's PN532
breakout, SPI is `SEL0=OFF`, `SEL1=ON`; other modules, including common PN532
V3 clones, can use different switch orientation or labels. Follow the manual
for the board actually purchased. Adafruit's Raspberry Pi wiring is documented
in its [PN532 guide](https://learn.adafruit.com/adafruit-pn532-rfid-nfc?view=all#python-computer-wiring-2986203).

```text
Raspberry Pi 3 Model A+               PN532 (SPI mode)
physical 17 / 3V3   ----------------  3.3V / VCC
physical 20 / GND   ----------------  GND
physical 19 / GPIO10 ---------------  MOSI
physical 21 / GPIO9  ----------------  MISO
physical 23 / GPIO11 ---------------  SCK / SCLK
physical 24 / GPIO8  ----------------  SSEL / SS / CS
```

Leave PN532 IRQ, RSTPD_N/RESET, and P32/H_Request disconnected for the supported
SPI adapter unless the exact module's documentation requires otherwise. Do not
add the I2C SDA/SCL wiring in parallel. SPI and I2C mode are alternatives, not
two simultaneous connections.

Keep the antenna away from the speaker magnet, amplifier, power converter, and
large loops of current-carrying wire. Test read range with the intended plastic
wall and recessed placement area before committing enclosure dimensions.

## MAX98357A and speaker

```text
Raspberry Pi 3 Model A+               MAX98357A
physical 4  / 5V    ----------------  VIN
physical 14 / GND   ----------------  GND
physical 12 / GPIO18 ---------------  BCLK
physical 35 / GPIO19 ---------------  LRC / LRCLK
physical 40 / GPIO21 ---------------  DIN

MAX98357A SPK+       ----------------  speaker +
MAX98357A SPK-       ----------------  speaker -
```

Do not connect either speaker output to Pi ground. The output is bridge-tied,
as documented in the
[Adafruit MAX98357A pinout](https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp/pinouts).
Twist the two speaker wires together and keep I2S wiring short. Route the NFC
antenna cable away from the speaker output pair and the power bank's converter.

Leave SD/MODE and GAIN at the breakout's documented defaults for the first
bench test. The FamilyBox Device Tree configuration does not connect SD/MODE
to a GPIO. Clone boards can populate different bias resistors, so verify mono
mix and gain behavior against that board's schematic.

## Buttons and encoder

Wire all button inputs active-low:

```text
GPIO input ---- normally-open switch ---- GND
```

The software enables an internal pull-up. GPIO Zero's current documentation
specifies this exact arrangement for `Button`; it also specifies encoder A and
B to GPIO with encoder common to ground. See the
[GPIO Zero input-device API](https://gpiozero.readthedocs.io/en/stable/api_input.html).

For a five-pin encoder, the three-pin side is normally A, common, and B, while
the two-pin side is normally the push switch, but confirm with a continuity
meter. Do not connect the encoder common to 3.3 V in this active-low design.

That wiring applies to a bare mechanical encoder. The purchased Keyestudio
KS0013 is an active module whose
[manufacturer specifies a 5 V supply](https://wiki.keyestudio.com/Ks0013_keyestudio_Rotary_Encoder_Module).
Do not connect its `+` pin to 5 V while its outputs are connected to the Pi.
Hold it for inspection and 3.3 V verification, or replace it with a bare EC11
encoder; Raspberry Pi GPIO inputs are not 5 V-tolerant.

Use a shared ground rail for the four push switches and encoder common. A
disconnected ground makes inputs float or appear unresponsive; a GPIO shorted
to ground appears permanently pressed.

## OnOff SHIM

This section describes the supported final-build option. The current Pi 3A+
V1 build omits the SHIM: do not enable its overlays, and use the manual safe
shutdown procedure in the hardware guide. GPIO4 and GPIO17 remain reserved so
adding a tested power controller later does not require rewiring other parts.

Mount or wire the SHIM exactly as Pimoroni intends so its USB input is the only
5 V source. Its logical connections are:

```text
GPIO17 / physical 11  <--- SHIM button trigger (active low)
GPIO4  / physical 7   ---> SHIM power-off signal (active low)
```

Pimoroni's own clean-shutdown documentation assigns GPIO17 and GPIO4 to these
roles: [clean-shutdown supported products](https://github.com/pimoroni/clean-shutdown#supported-products).
The [OnOff SHIM product documentation](https://shop.pimoroni.com/products/onoff-shim)
describes its switched-power path and required soldered 2x6 connection. Do not
enable 1-Wire on GPIO4 or connect the amplifier SD/MODE signal there.

The small SHIM occupies the early physical-header area even though it uses only
a subset of signals. Plan the stacking header or solder order before attaching
the BCLK wire at physical pin 12. Insulate the SHIM from adjacent connectors.

## Raspberry Pi boot configuration

`scripts/install-pi.sh` enables SPI using non-interactive `raspi-config` and
adds this managed block to `/boot/firmware/config.txt` on current Raspberry Pi
OS:

```ini
# BEGIN FAMILYBOX
[all]
dtparam=audio=off
dtparam=i2s=on
dtoverlay=max98357a,no-sdmode
# END FAMILYBOX
```

When `--with-onoff-shim` is explicitly supplied and the SHIM is physically
installed, the block also contains:

```ini
dtoverlay=gpio-shutdown,gpio_pin=17,active_low=1,gpio_pull=up,debounce=100
dtoverlay=gpio-poweroff,gpiopin=4,active_low=1,input=1
```

Raspberry Pi documents `raspi-config nonint do_spi 0` as enabling SPI and
explains that current OS configuration normally lives in
`/boot/firmware/config.txt`; see the
[Raspberry Pi configuration guide](https://www.raspberrypi.com/documentation/configuration/).
A reboot is required before boot-time overlays take effect.

The installer also makes the overlay's stable `MAX98357A` ALSA card name the
default while preserving unrelated `/etc/asound.conf` content:

```text
# BEGIN FAMILYBOX AUDIO
pcm.!default {
  type plug
  slave.pcm "hw:CARD=MAX98357A,DEV=0"
}
# END FAMILYBOX AUDIO
```

The `plug` layer converts formats that the hardware PCM cannot accept directly;
mpv still owns child-facing software volume.

## First-power checklist

- PN532 is set to SPI, is powered from 3.3 V, and has no 5 V GPIO signal.
- Amplifier VIN and GND are not reversed.
- Speaker is at least 4 ohms and is connected only across `SPK+`/`SPK-`.
- No continuity exists between 5 V and ground.
- No signal is assigned twice; GPIO4 and GPIO17 go only to the OnOff SHIM.
- Buttons and a verified bare encoder short inputs only to ground, never to
  5 V. Do not install the KS0013 module until its logic voltage is verified.
- Bare joints are insulated and the Pi is on nonconductive spacers.
- The power bank can be disconnected quickly during the first test.

After boot, verify the kernel-visible interfaces before starting the app:

```sh
test -e /dev/spidev0.0 && echo "SPI0 CE0 ready"
aplay -l
sudo dtoverlay -h max98357a
```

For the first sound, use mpv with a known local file and an explicitly low
digital volume, for example
`mpv --no-video --audio-device=alsa/default --volume=10 test-audio.mp3`.
`speaker-test` can emit a full-scale signal and is a poor first test beside a
child-facing 3 W speaker.

The `dtoverlay -h` command documents available overlay parameters; boot-loaded
overlays are already baked into the Device Tree and may not appear in
`dtoverlay -l`.
