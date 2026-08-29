# First hardware bring-up

Use this checklist for the first FamilyBox. Open and test one subsystem at a
time. Do not assemble an enclosure or make permanent solder joints until every
bench stage passes.

## The connection model

The Mac mini and Raspberry Pi do not need a physical data connection.

```text
Mac mini --writes--> microSD card --boots--> Raspberry Pi
Mac mini <--SSH/browser over the same Wi-Fi--> Raspberry Pi
power bank --USB power only--> Raspberry Pi
```

The Mac writes the card with Raspberry Pi Imager. After that, the Pi is powered
separately and the Mac controls it over the home network. Do not try to power
the Pi from the Mac while also powering it from the power bank.

## Before opening boxes

- Work on a clean, dry, nonconductive table with good light.
- Keep the multimeter and phone camera nearby.
- Never add, remove, or move a wire while the Pi is powered.
- Use physical header pin numbers only where this guide explicitly says
  `physical`; the application configuration uses BCM GPIO numbers.
- Stop immediately for heat, odor, smoke, repeated resets, a low-voltage
  warning, or a suspected short.

## Stage 1: prepare the microSD card on the Mac

Open only the microSD card and USB card reader.

1. Install and open
   [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Select **Raspberry Pi 3 Model A+** as the device.
3. Select **Raspberry Pi OS Lite (64-bit)** as the operating system.
4. Select the SanDisk 64 GB card. Check the capacity and device name twice;
   writing the image erases the selected drive.
5. In OS customisation, set:
   - hostname: `familybox-player`
   - your time zone and keyboard layout
   - an admin username and a password you will remember
   - the same Wi-Fi network used by the Mac mini
   - **Enable SSH**, initially using password authentication
6. Write and verify the image, then eject the card normally.

Do not send the Wi-Fi or Pi password in chat or commit it to this repository.

**Checkpoint:** the image verifies successfully and the card ejects without an
error. Stop here if Imager reports a write or verification failure.

## Stage 2: first boot with the Pi alone

Open the Raspberry Pi 3A+, the Micro-B USB cable, and one power bank. Leave the
NFC reader, amplifier, speaker, buttons, and encoder boxed.

1. Inspect the Pi for bent header pins, loose parts, or shipping damage.
2. Put the Pi on a nonconductive surface.
3. Insert the microSD card while power is disconnected.
4. Connect the cable to the Pi's Micro-B power port, then to the power bank.
5. Allow up to five minutes for the first boot and Wi-Fi connection.
6. On the Mac, open Terminal and run, replacing `<username>` with the account
   created in Imager:

   ```sh
   ping -c 3 familybox-player.local
   ssh <username>@familybox-player.local
   ```

7. At the Pi's SSH prompt, verify the board and operating system:

   ```sh
   tr -d '\0' </proc/device-tree/model; echo
   uname -m
   ```

   Expect a Raspberry Pi 3 Model A+ description and `aarch64`.

**Checkpoint:** SSH works and the model is correct. Stop here if the host cannot
be found, the model is wrong, or the Pi repeatedly disconnects.

## Stage 3: install and test FamilyBox with no accessories

Stay connected over SSH. Install Git and clone the repository if it is not
already on the Pi:

```sh
sudo apt update
sudo apt install -y git
git clone https://github.com/DadJokez/family-audio-box.git
cd family-audio-box
sudo ./scripts/install-pi.sh --hostname familybox-player
sudo reboot
```

The SSH connection will close during reboot. Wait a minute, reconnect, and run:

```sh
ssh <username>@familybox-player.local
familybox-diagnostics --stage base
systemctl is-active familybox
```

Both base checks should say `PASS`, and the service should say `active`. From
the Mac or phone on the same Wi-Fi, open
<http://familybox-player.local>. Hardware-specific warnings are expected while
those parts are still boxed.

**Checkpoint:** base diagnostics pass and the FamilyBox page opens. This proves
the card, Pi, OS, network, installation, service, GPIO subsystem, and web UI.

## Stage 4: add the PN532 NFC reader

Open the PN532, GPIO breakout/ribbon cable, breadboard, jumper wires, and
multimeter. Keep the audio and controls boxed.

1. On the Pi, run `sudo poweroff`.
2. Wait until Linux has stopped and microSD activity has ceased, then disconnect
   the power bank.
3. Photograph both sides of the PN532 closely enough to read the switch labels
   and board revision. Confirm its SPI switch position from that exact board's
   markings before wiring; clone boards do not all use the same switch truth
   table.
4. With power still disconnected, wire:

   | Pi physical pin | Pi signal | PN532 signal |
   | ---: | --- | --- |
   | 17 | 3.3 V | 3.3V / VCC |
   | 20 | Ground | GND |
   | 19 | GPIO10 / MOSI | MOSI |
   | 21 | GPIO9 / MISO | MISO |
   | 23 | GPIO11 / SCLK | SCK / SCLK |
   | 24 | GPIO8 / CE0 | SSEL / SS / CS |

5. Check every line end-to-end. Confirm there is no continuity between 3.3 V
   and ground, then reconnect power.
6. After boot, run:

   ```sh
   familybox-diagnostics --stage nfc
   sudo systemctl restart familybox
   journalctl -u familybox -n 100 --no-pager
   ```

7. Place the included test card or fob on the PN532. In the web UI, confirm an
   unknown tag UID appears. The diagnostic command proves the SPI plumbing;
   reading a real UID proves the PN532 itself.

**Checkpoint:** every NFC-stage check passes and repeated card placement/removal
is detected. Do not add audio until this works reliably.

## Stage 5: add the amplifier and speaker

Power down and unplug again. Open one MAX98357A board, the speaker, red/black
wire, and the soldering kit only if the board headers or speaker tabs require
solder. Confirm the kit contains electronics solder before making a joint.

1. Photograph the labels on the exact amplifier board before soldering if they
   differ from this guide.
2. With power disconnected, wire:

   | Pi physical pin | Pi signal | MAX98357A signal |
   | ---: | --- | --- |
   | 4 | 5 V | VIN |
   | 14 | Ground | GND |
   | 12 | GPIO18 / BCLK | BCLK |
   | 35 | GPIO19 / LRCLK | LRC / LRCLK |
   | 40 | GPIO21 / data | DIN |

3. Connect the speaker only between amplifier `SPK+` and `SPK-`. Neither
   speaker terminal connects to ground.
4. Check for a 5 V-to-ground short before powering up.
5. Boot and run:

   ```sh
   familybox-diagnostics --stage audio
   aplay -l
   vcgencmd get_throttled
   ```

   Expect all checks to pass, an ALSA `MAX98357A` card, and
   `throttled=0x0`.
6. From the Mac, copy a short, known-good MP3:

   ```sh
   scp /path/to/test.mp3 <username>@familybox-player.local:~/test.mp3
   ```

7. On the Pi, start very quietly:

   ```sh
   mpv --no-video --audio-device=alsa/default --volume=10 ~/test.mp3
   ```

**Checkpoint:** clean audio plays at low volume without heat, resets, crackle,
or undervoltage. Stop before increasing volume if anything is abnormal.

## Stage 6: add the colored transport buttons

Power down and unplug. Open the colored momentary buttons. Add and test one
button at a time between its GPIO and ground:

| Action | Pi physical pin | BCM GPIO | Other button contact |
| --- | ---: | ---: | --- |
| Previous | 29 | 5 | Ground |
| Play/pause | 31 | 6 | Ground |
| Next | 33 | 13 | Ground |

Choose three distinct colors and record the mapping. Boot after each addition
and verify that one press produces one action without affecting another input.

**Checkpoint:** all three buttons work individually and together during audio
playback.

## Stage 7: hold the KS0013 encoder for inspection

Do not connect the purchased Keyestudio KS0013 module yet. Its manufacturer
lists a 5 V supply, while the Pi's GPIO inputs are 3.3 V-only. Open it only when
ready to photograph both sides and inspect or measure it with us. Never connect
its `+` pin to 5 V while `CLK`, `DT`, or `SW` are connected to the Pi.

If inspection confirms that this exact board is safe when powered at 3.3 V,
the intended signal allocation is:

| Module signal | Pi physical pin | BCM GPIO |
| --- | ---: | ---: |
| CLK / A | 16 | 23 |
| DT / B | 18 | 24 |
| SW | 22 | 25 |
| GND | a Pi ground pin | — |

Its `+` connection is deliberately omitted until the board is verified. If it
cannot safely operate at 3.3 V, replace it with a bare mechanical EC11 encoder
or a module explicitly specified for 3.3 V GPIO.

## Stage 8: complete the bench acceptance test

With the working subsystems still accessible on the bench:

1. Import a real story through the Library page.
2. Scan the NFC card and assign the story to its UID.
3. Start playback by placing the card; remove it to pause; replace it to resume.
4. Verify previous, play/pause, next, and—after approval—the volume encoder.
5. Reboot and confirm the saved story position resumes.
6. Disconnect internet access while keeping the local Wi-Fi network available;
   repeat playback and control tests to prove local-first operation.
7. Play at the intended loudest volume for at least 15 minutes, then run
   `vcgencmd get_throttled` again and check the Pi, amplifier, power bank, and
   wiring for abnormal heat or resets.
8. Shut down with `sudo poweroff`, wait for storage activity to stop, and only
   then disconnect power.

Only after this passes should the standoffs, heat-shrink, permanent wire lengths,
strain relief, and enclosure layout be finalized. The OnOff SHIM remains a
future-build item, not part of this first bench test.

## Box-opening order at a glance

1. microSD card + card reader
2. Pi 3A+ + Micro-B cable + one power bank
3. PN532 + breakout/ribbon + breadboard + jumpers + multimeter
4. MAX98357A + speaker + wire; soldering kit only if needed
5. colored buttons
6. KS0013 encoder only for inspection and voltage verification
7. standoffs and heat-shrink only after all bench tests pass
