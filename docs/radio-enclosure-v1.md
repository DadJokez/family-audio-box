# FamilyBox radio enclosure V1

This document is the mechanical starting specification for the rounded retro
radio enclosure selected for FamilyBox. It is detailed enough to build the
first CAD model and print fit-test parts, but it is not a substitute for
measuring the exact delivered hardware with calipers.

The enclosure is intentionally parameterized around the actual V1 bill of
materials in [hardware.md](hardware.md), not around generic render proportions.
The wiring and separation rules in [wiring.md](wiring.md) remain authoritative.

## Status and conclusion

- **Recommended outside envelope:** 210 W x 150 H x 115 D mm.
- **The selected Miady 5,000 mAh power bank fits internally.** It mounts
  vertically in the rear-right electronics bay without reducing the speaker
  chamber.
- Keep the power-bank bay optional. The bench build still lacks a validated
  clean-shutdown and true-power-cutoff controller. Make two interchangeable
  rear-panel variants: internal-bank and external-bank.
- Use a sealed left speaker chamber and a separately ventilated right
  electronics bay.
- Put the NFC stage on the top-right, directly over the PN532 and laterally
  separated from the speaker magnet.
- Model the cream front baffle as the cheap-to-reprint fit-critical part. The
  speaker cutout data published by the vendor and reseller conflict, so do not
  bury that cutout in the expensive main shell.

All dimensions below are millimetres unless stated otherwise.

## Coordinate system

Use this coordinate system in CAD:

- Origin `(0, 0, 0)` is the outside front-left-bottom corner.
- `X` increases left to right.
- `Y` increases from the front face toward the rear.
- `Z` increases bottom to top.
- The nominal exterior occupies `X=0..210`, `Y=0..115`, `Z=0..150`.

“Front” means the cream baffle/speaker side. Coordinates locate centers unless
otherwise noted.

## Actual component envelopes

Use the **CAD reserve** column for collision checks. The source dimension is
recorded separately so later caliper measurements can replace assumptions
without changing the layout logic.

| Component | Published or supplied dimensions | CAD reserve | Confidence and action |
| --- | --- | --- | --- |
| Raspberry Pi 3 Model A+ | 65 x 56 board; 58 x 49 mounting-hole pattern; M2.5-class holes | 70 x 60 x 26, including standoffs, GPIO/header clearance and cable bends | High for board outline. Import the official mechanical drawing or a verified STEP model before creating bosses. |
| GRS 3FR-4 speaker | GRS drawing: 80.5 x 80.5 side envelope, four 4.5 holes on an 86 bolt circle, 78 basket, 60 magnet, 42 total depth. Reseller lists 95.3 overall and 71.6 cutout. | 96 x 96 x 45 behind the baffle | Published sources conflict. Measure frame tip-to-tip, cutout requirement, gasket, and hole centers. Print a speaker-ring coupon before the full baffle. |
| HiLetgo-style PN532 V3 | 42.7 x 40.4 x 4 board | 48 x 46 x 10 including header and connector | Medium until the delivered HiLetgo board is measured. Keep all mounting features slotted or on a replaceable carrier. |
| AITRIP MAX98357A breakout | Exact clone board not dimensioned by seller; common Adafruit-format board is about 19.4 x 17.8 x 3 before headers/terminal | 26 x 22 x 15 | Low-to-medium. Measure after headers and the speaker terminal are installed. Mount on a replaceable carrier. |
| Three 16 mm pushbuttons | Seller drawing: 16 panel thread/hole, approximately 19 cap, 5.5 projection above panel, 13.5 body behind flange plus 5.8 terminals | 20 diameter x 25 behind baffle per button | Medium. Print 16.0, 16.2 and 16.4 test holes; use the best measured fit. |
| Keyestudio KS0013 encoder module | 30 x 20 board, approximately 29 overall height, 6 shaft, two M2 mounting holes around 16 spacing | 32 W x 22 H x 35 D behind baffle | Medium. Its published supply is 5 V and the Pi GPIO is 3.3 V-only. Do not commit the final carrier until voltage safety is verified or a bare EC11 is selected. |
| Miady HYD009 5,000 mAh bank | 3.6 x 2.4 x 0.5 in = 91.4 x 61.0 x 12.7 | 95 H x 65 W x 17 D in cradle | Medium-high for body. Measure corner radius, port positions, indicator/button positions and actual thickness. |
| Wiring/connectors | No fixed outline | 10 minimum cable corridor; 25 above power-bank ports | Route and label removable harnesses. Do not model wires as zero-volume paths. |
| Future shutdown/cutoff controller | Not selected for the completed portable build | Reserve 45 x 25 x 12 or Pi-header headroom inside the Pi envelope | Do not drill a final power-button hole until the controller and button are selected. |

Reference sources:

- [Raspberry Pi 3 Model A+ mechanical information](https://pip.raspberrypi.com/categories/512-raspberry-pi-3-model-a)
- [GRS 3FR-4 manufacturer specification sheet](https://www.parts-express.com/pedocs/specs/GRS%20Spec%20Sheets/292-436--grs-3fr-4-spec-sheet.pdf)
- [GRS reseller mounting and enclosure data](https://www.parts-express.com/GRS-3FR-4-Full-Range-3-Speaker-4-Ohm-292-436)
- [PN532 V3 module dimensions](https://www.sunrobotics.in/products/pn532-rfid-reader-writer-nfc)
- [MAX98357A reference-breakout dimensions](https://www.adafruit.com/product/3006)
- [Keyestudio KS0013 documentation](https://wiki.keyestudio.com/Ks0013_keyestudio_Rotary_Encoder_Module)
- [Miady HYD009 manual](https://manuals.plus/asin/B08T8TDS8S.pdf)

## Master CAD parameters

This block is deliberately close to OpenSCAD syntax so it can be copied into a
parameter file or translated directly into another CAD system.

```scad
case_w = 210;
case_h = 150;
case_d = 115;

outer_corner_r = 18;
wall = 3.0;
front_baffle_t = 4.0;
rear_panel_t = 3.2;
partition_t = 3.0;

front_baffle_w = 202;
front_baffle_h = 142;
front_baffle_corner_r = 14;
front_baffle_recess = 1.0;
front_baffle_per_side_clearance = 0.35;

speaker_partition_x0 = 112;
speaker_partition_x1 = 115;
speaker_center_x = 58;
speaker_center_z = 78;
speaker_frame_reserve = 96;
speaker_cutout_prototype_d = 79.0;
speaker_bolt_circle_d = 86.0;
speaker_mount_hole_d = 4.8;

button_hole_prototype_d = 16.2;
button_cap_reserve_d = 20;
button_center_spacing = 27;
button_center_z = 44;
button_centers_x = [132, 159, 186];

encoder_center_x = 159;
encoder_center_z = 100;
encoder_shaft_hole_prototype_d = 7.0;
volume_knob_d = 38;

nfc_pad_center_x = 171;
nfc_pad_center_y = 67;
nfc_pad_d = 62;
nfc_pad_relief = 0.8;
nfc_window_t = 2.0;

electronics_rear_aperture_x0 = 119;
electronics_rear_aperture_x1 = 202;
electronics_rear_aperture_z0 = 8;
electronics_rear_aperture_z1 = 142;

nominal_fdm_clearance = 0.30;
sliding_part_clearance = 0.40;
gasket_t = 1.0;
```

Treat every hole marked `prototype` as a starting value, not a production
dimension.

## Exterior geometry

### Main sage shell

- Rounded rectangular body: 210 x 150 x 115.
- Outer front-view corner radius: 18.
- Nominal wall: 3.0.
- Avoid shelling a complex filleted solid if the CAD system produces variable
  wall thickness. Build the inside and outside profiles explicitly.
- Keep the bottom flat. Use purchased adhesive rubber feet instead of printed
  angled legs.
- Add four shallow foot-location recesses on the bottom, 10 to 12 diameter and
  0.5 deep. Place their centers approximately 18 from each adjacent side.
- The right rear is a removable electronics service panel. The left rear is a
  permanent wall of the sealed speaker chamber.
- Do not put ventilation slots through the speaker chamber.

### Cream front baffle

- Visible insert: 202 x 142 x 4 with radius 14, centered in the front.
- Recess it 1.0 behind the front edge of the sage shell.
- Start with 0.35 clearance per side around the insert. Parameterize it.
- Reinforce behind the baffle around the speaker and controls to 6 local
  thickness, using ribs rather than making the entire baffle thick.
- Use six M3 fasteners into shell bosses for the first prototype. Suggested
  absolute front coordinates:
  - bottom: `(14, 14)`, `(105, 14)`, `(196, 14)` in X/Z;
  - top: `(14, 136)`, `(105, 136)`, `(196, 136)` in X/Z.
- Countersink or counterbore fasteners and cover them later with color-matched
  printed plugs if a screw-free appearance is still desired.
- Make this panel independently printable. Speaker or control fit errors should
  cost one flat-panel reprint, not one entire enclosure reprint.

### Rear electronics panel

- Main rear aperture: `X=119..202`, `Z=8..142`.
- Cover panel: approximately 91 x 142 x 3.2 with radius 10 and 4 perimeter
  fasteners. Adjust overlap to leave at least 4 around the aperture.
- Use M3 heat-set inserts or captured M3 nuts in the shell, not screws biting
  repeatedly into printed plastic.
- Add electronics ventilation to this panel only:
  - eight horizontal slots;
  - each slot 25 x 3 with 1.5 end radii;
  - four high and four low, separated from fastener bosses;
  - target open area approximately 600 square millimetres.
- Keep an uncut 25 x 25 power-control reservation near the lower-right rear.
  Add its hole only after the clean-shutdown hardware is selected.

## Front control layout

### Speaker

- Center: `X=58`, `Z=78`.
- Initial baffle cutout: 79.0 diameter.
- Manufacturer drawing indicates four 4.5 mounting holes on an 86 bolt circle.
  Use 4.8 x 6.0 radial slots for the prototype, centered at 45, 135, 225 and
  315 degrees. Slots absorb small source/print discrepancies.
- Reserve a 96 square collision envelope around the frame even though the GRS
  drawing calls out an 80.5 side envelope. This covers the larger reseller
  dimension until the physical part is measured.
- Recess the speaker flange 1.5 to 2 behind the front bezel so the cone is less
  exposed to direct impacts.
- Use a 1 closed-cell foam gasket between driver flange and baffle.
- Recommended fastener starting point: four M4 x 12 machine screws, washers and
  nyloc nuts. Confirm fit through the actual 4.5 holes.
- Optional child-facing guard: a separate snap/screw-mounted sage ring with
  three broad ribs. Keep at least 70 percent open area and at least 4 clearance
  from the moving surround and dust cap at maximum excursion.

### Transport buttons

- Exactly three identical round buttons.
- Hole centers: `(132, 44)`, `(159, 44)`, `(186, 44)` in X/Z.
- Center spacing: 27.
- Initial panel hole: 16.2. Print a coupon before committing the baffle.
- Reserve 20 diameter on the visible face and 25 depth behind the baffle.
- Keep terminals at least 5 from adjacent printed walls and insulate all solder
  joints with heat-shrink.
- Suggested color/action order: blue previous, green play/pause, red next. The
  software behavior is authoritative; add embossed icons only after the
  physical order is accepted.

### Volume encoder

- Shaft center: `(159, 100)` in X/Z.
- Visible knob: 38 diameter, approximately 18 deep, with a grippy knurled rim.
- Initial shaft hole: 7.0 for the nominal 6 shaft.
- Behind-panel reserve: 32 W x 22 H x 35 D.
- Put the KS0013 on a small removable adapter plate with slotted M2 holes. Do
  not make its board pattern integral to the cream baffle.
- Also create a second adapter plate for a bare 3.3 V-safe EC11 if the purchased
  module fails voltage verification.

## NFC stage and reader

- Pad center on top: `X=171`, `Y=67`.
- Pad diameter: 62.
- The pad is solid. Use a 0.8 raised or recessed ring only; do not make a hole.
- Thin the top wall locally to 2.0 over the reader antenna. Keep the surrounding
  top wall at 3.0.
- Mount the PN532 directly under the pad, antenna parallel to the top surface.
- Reserve `X=149..197`, `Y=44..90`, approximately `Z=137..148` for the board,
  carrier, header and wiring.
- Use nylon M2.5 fasteners/standoffs near the antenna when possible.
- Do not put steel screws, the power bank, speaker wire loops or the Pi directly
  beneath the antenna.
- The reader center is approximately 113 laterally from the speaker center. The
  nearest reader-board edge remains more than 40 from the conservative speaker
  frame envelope.
- Route the SPI harness down the right outer wall, not across the speaker magnet
  or amplifier output wiring.
- Make the PN532 carrier removable and slotted because the exact clone board
  hole pattern is not yet verified.
- Acceptance target: ten consecutive reads/removals with the real figure/tag,
  printed 2.0 wall, final reader carrier and the speaker playing.

## Internal zoning

### Sealed speaker chamber

Nominal clear boundaries:

- `X=3..112` -> 109 W.
- `Y=4..112` -> 108 D.
- `Z=3..147` -> 144 H.

Gross volume is approximately 1.695 L. Allowing roughly 0.15 to 0.20 L for the
driver, ribs, gasket and wire pass-through leaves approximately **1.50 L net**.

Using the published `Vas=0.6 L`, `Qts=0.85` and `Fs=145 Hz`, a simplified
sealed-box estimate at 1.50 L gives:

- `Qtc ~= 0.85 * sqrt(1 + 0.6 / 1.5) ~= 1.01`;
- `Fc ~= 145 * sqrt(1 + 0.6 / 1.5) ~= 172 Hz`.

This is close to the reseller’s 1.70 L sealed recommendation and is appropriate
for speech/stories and modest music playback. It will not produce deep bass.
Do not add a reflex port to V1; a sealed chamber is simpler, more tolerant and
keeps electronics airflow acoustically isolated.

Construction details:

- Integral partition: `X=112..115`, full chamber height and depth.
- Add 8 to 10 triangular ribs, 3 thick, where the baffle rim, outer walls and
  partition meet. Do not place ribs where they reduce speaker magnet clearance.
- Add a 1 closed-cell gasket around the complete front perimeter of the chamber.
- Speaker wire pass-through: one 6 to 8 hole high on the partition, fitted with
  a printed plug or grommet and sealed after wiring.
- Keep the chamber rear wall solid.
- Add no electronics vents, battery door or NFC opening to this chamber.

### Electronics bay

Nominal clear volume before carriers is approximately 92 W x 144 H x 108 D,
or 1.43 L gross. It contains the controls, Pi, PN532 harness, amplifier, optional
power bank and future power-control allowance.

Use these conservative collision envelopes:

| Item | Envelope location |
| --- | --- |
| Power-bank cradle | `X=120..185`, `Y=95..112`, `Z=8..103` |
| Pi side carrier | `X=181..207`, `Y=18..88`, `Z=70..130` |
| PN532 + carrier | `X=149..197`, `Y=44..90`, `Z=137..148` |
| Encoder module | `X=143..175`, `Y=4..39`, `Z=83..115` |
| Button bodies/terminals | approximately `Y=4..29`, centered at the three front coordinates |
| Amplifier carrier | `X=116..142`, `Y=12..40`, `Z=94..118` |
| Main cable corridor | 10 minimum along the bay bottom and rear of the partition |

These are collision boxes, not exact printed carrier geometry.

### Raspberry Pi carrier

- Mount the Pi vertically to the inside of the right wall on a removable tray.
- Orient the Wi-Fi antenna edge toward the outer plastic wall and away from the
  speaker partition and power bank.
- Use the official 58 x 49 mounting-hole rectangle only after confirming model
  orientation against the mechanical drawing.
- Use M2.5 standoffs; allow at least 3 under-board clearance.
- Reserve 26 thickness into the bay for the board, header, optional shutdown
  shim and connectors.
- Keep the microSD reachable after removing only the rear service panel.
- Do not require removal of the speaker or front baffle to service the card.

### Amplifier carrier

- Mount the MAX98357A on the electronics side of the partition, close to the
  speaker wire pass-through.
- Use a replaceable 26 x 22 carrier with slotted M2/M2.5 holes.
- Keep the I2S harness short.
- Twist `SPK+` and `SPK-` together and route them directly through the sealed
  partition pass-through.
- Maintain at least 40 separation from the PN532 board and its cable wherever
  practical.

## Power-bank decision and rear variants

### Does the selected bank fit?

Yes. The physical bank is approximately 91.4 x 61.0 x 12.7. A 95 x 65 x 17
vertical cradle fits in the rear-right collision box and can be removed through
the electronics service aperture. It does not intrude into the 1.50 L net
speaker chamber.

### Variant A: internal power bank

- Print a removable cradle attached to the rear panel, not the main shell.
- Internal cradle clearance: 95 H x 65 W x 17 D.
- Use a soft retention strap or compliant clip. Do not rigidly clamp the bank
  against every face; it must be removable and must not be trapped if damaged.
- Orient the bank’s ports upward, leaving at least 25 cable-bend clearance.
- Use the already selected USB-A-to-Micro-B cable from bank to Pi unless bench
  testing selects another safe path.
- Add a parameterized covered access window for the bank’s USB-C charging port,
  but do not place it until the actual port offset is measured.
- Do not assume charge-through/pass-through behavior. Charge with FamilyBox
  shut down unless the exact bank is tested and documented otherwise.
- If the bank becomes hot, swells, smells abnormal or resets the Pi, stop using
  it and remove it.

### Variant B: external power bank

- Omit the internal cradle.
- Use the same main shell and electronics layout.
- Replace the battery panel with a vented flat panel containing a recessed
  bottom cable notch and strain-relief feature.
- Keep the external bank in a separate clip-on cradle or weighted base; do not
  leave a child-facing cable dangling freely.

### Power control remains a blocker for a “finished portable” label

The enclosure can physically hold the bank, but mechanical fit does not solve
safe Linux shutdown or true power cutoff. The current project supports a future
Pimoroni OnOff SHIM path but has not validated it with this bank. Preserve the
reserved power-control area and do not finalize its hole until all four power
tests in [hardware.md](hardware.md#power-and-safe-shutdown) pass.

## Printed parts

Minimum part set:

1. **Sage main shell** with sealed left rear wall, partition, front recess and
   right rear service aperture.
2. **Cream front baffle** with speaker, three button and encoder features.
3. **Sage rear electronics panel — external-bank variant.**
4. **Sage rear electronics panel — internal-bank variant.**
5. **Power-bank cradle** for the internal-bank panel.
6. **Pi carrier** using M2.5 standoffs.
7. **PN532 top carrier** with slotted holes and nylon fastener support.
8. **MAX98357A carrier** with slots.
9. **Encoder adapter plate — KS0013.**
10. **Encoder adapter plate — bare EC11 fallback.**
11. **Volume knob** for a 6 shaft.
12. **Optional three-rib speaker guard/bezel.**
13. **Small color-matched front screw plugs**, optional.

Avoid combining carriers with the main shell. Clone-board dimensions and
connector positions are the most likely measurements to change.

## Suggested fasteners and consumables

The current procurement list includes M2.5 standoffs but not all enclosure
hardware. Plan to add:

- 4 x M4 x 12 speaker screws, washers and nyloc nuts, subject to physical fit;
- 10 to 12 x M3 x 8 or M3 x 10 enclosure screws;
- matching M3 heat-set inserts or captured nuts;
- M2/M2.5 hardware for module carriers;
- 1 mm closed-cell foam speaker/baffle gasket;
- four 10 to 12 mm-diameter adhesive rubber feet;
- a soft hook-and-loop battery strap if using the internal bank;
- nylon fasteners or standoffs for the PN532 when available;
- small removable connectors between the front controls and main harness.

For typical M3 heat-set inserts, begin with 7.5 boss OD and the hole recommended
by the exact insert supplier. Print an insert coupon first. Do not guess the
heat-set hole from this document.

## FDM print guidance

The 210 x 115 main-shell footprint is deliberately sized to fit a common 220 x
220 bed with a 5 brim. Verify the printer’s true usable area and clips before
slicing.

- Material: PETG preferred for better heat resistance; quality PLA+ is suitable
  for indoor prototypes if the device is never left in a hot car or direct sun.
- Nozzle: 0.4.
- Layer height: 0.20 for prototypes; 0.16 to 0.20 for final cosmetic parts.
- Perimeters: 4 minimum.
- Top/bottom layers: 5 minimum.
- Infill: 20 to 25 percent gyroid or cubic; use local modifiers around bosses.
- Main-shell orientation: rear face down, front opening upward. Design rear
  radii and the electronics aperture to avoid unsupported bridges.
- Front-baffle orientation: cosmetic front face down on a smooth/textured plate
  according to the desired finish.
- Carriers/panels: largest flat face down.
- Use 45-degree internal chamfers instead of support-dependent horizontal
  ledges wherever possible.
- Minimum structural wall: 2.4; nominal shell remains 3.0.
- Minimum rib: 2.4 thick, preferably 3.0.
- Boss-to-wall fillet: 2 minimum.

## Fit-test coupons to print first

Do not start with the complete shell. Print these inexpensive checks:

1. **Speaker coupon:** 110 square baffle segment with 78.0, 79.0 and/or measured
   cutout, 86 bolt circle and radial slots.
2. **Button coupon:** 3 wall with 16.0, 16.2 and 16.4 holes.
3. **Encoder coupon:** final baffle thickness, shaft hole and adapter slots.
4. **Front-panel corner coupon:** shell recess, 0.25/0.35/0.45 clearances and one
   M3 boss.
5. **NFC roof coupon:** 1.6, 2.0, 2.4 and 3.0 plastic thicknesses tested with
   the actual tag in the intended figure base.
6. **Power-bank cradle coupon:** one corner and retention feature before the
   complete cradle.

Record the winning values back into the master parameter block.

## Measurements required from delivered parts

Capture these with calipers before calling the CAD model production-ready:

### Speaker

- maximum frame width and corner-to-corner extent;
- required baffle cutout;
- mounting-hole diameter and both adjacent/diagonal center spacing;
- flange/gasket thickness;
- total rear depth;
- magnet diameter;
- terminal position and required connector clearance.

### PN532

- board X/Y/Z;
- antenna location relative to board edges;
- all mounting-hole centers and diameters;
- header height and exit direction;
- switch access required after mounting.

### Amplifier

- populated board outline and height;
- mounting holes;
- screw-terminal and header overhang;
- wire exit directions.

### Buttons and encoder

- successful printed panel-hole diameter;
- button thread length through the final baffle;
- terminal depth after solder and heat-shrink;
- encoder shaft diameter/length;
- encoder board mounting-hole spacing;
- safe operating voltage of the actual KS0013.

### Power bank

- actual body dimensions and corner radius;
- USB-A and USB-C port sizes and offsets;
- power/indicator position;
- cable plug overhang and bend radius;
- whether the bank stays on under Pi idle load;
- whether it supports safe intended charging behavior.

## Assembly sequence

1. Print and approve all fit coupons.
2. Print the front baffle and module carriers before the main shell.
3. Install M3 inserts/captured nuts in the shell and rear panel.
4. Install PN532 under the top-right stage with its connectorized SPI harness.
5. Install the Pi carrier, leaving the microSD accessible from the rear.
6. Install the amplifier carrier and front-control harness.
7. Mount the speaker to the baffle with its gasket.
8. Feed the twisted speaker pair through the partition and seal the pass-through.
9. Gasket and fasten the front baffle; verify the speaker chamber is sealed.
10. Install the optional power-bank cradle and bank, or the external-power rear
    panel.
11. Check every wire for pinch and strain before closing the rear panel.
12. Test at low volume, then perform NFC range, thermal, idle and power tests.

## Mechanical acceptance checklist

- The body sits flat on all four rubber feet and does not tip under button or
  encoder force.
- Front baffle can be removed without touching the speaker cone.
- Rear service panel exposes the microSD, Pi connectors, PN532 connector,
  amplifier and optional bank.
- Power bank can be removed without flexing or desoldering another component.
- No wire crosses a sharp printed edge or is pinched by either panel.
- Speaker surround and dust cap cannot touch the bezel/guard at full excursion.
- Speaker chamber has no visible air path into the electronics bay.
- Electronics vents are open and not blocked by the battery or cables.
- NFC reads reliably with the speaker idle and playing.
- The figure’s tag plane is parallel to the PN532 antenna.
- External or internal power cable has strain relief.
- The device completes the documented clean shutdown before power is removed.

## Recommended first-CAD order

Model in this order so uncertain measurements stay isolated:

1. master parameters and coordinate planes;
2. simple component collision solids;
3. front baffle and its fit coupons;
4. speaker chamber and partition;
5. outer shell and rear aperture;
6. PN532 stage/carrier;
7. controls and replaceable encoder carrier;
8. Pi and amplifier carriers;
9. rear panel variants and battery cradle;
10. fillets, cosmetic bezel, screw plugs and optional guard last.

Do not begin with cosmetic fillets. First prove collision clearance, assembly
access, speaker seal and NFC range.
