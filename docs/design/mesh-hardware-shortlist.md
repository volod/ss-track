# Candidate shortlist for the reference sensor mesh

Design input for [spec section 16.4](spec.md#164-hardware-selection) and
[spec section 16.5](spec.md#165-reference-sensor-mesh), feeding the
[selection flow](test-stands.md#selection-flow)'s "shortlist provisionally" step for the
`shortlist-mesh-sensors` and `select-reference-host` tasks. Every figure here is a **datasheet
claim**, not a measured result: [test-stands.md](test-stands.md#limits) is unchanged by this
document -- no hardware model is selected here, and a candidate becomes a chosen configuration only
through `ss-track hardware-select` against versioned Stand A/B/C requirements. Facts were checked
against vendor material on 2026-11-05 where a citation is given; unmarked figures are long-standing
public specifications and must still be confirmed against the current datasheet before acquisition.

This list responds to the sensor set proposed in `Adapting arXiv 2405.13542 tracking for area
safety.pdf` (repository root): two or more visible/thermal cameras, a scanning or solid-state lidar,
a synchronized microphone array, and an FMCW or Doppler radar, run on a Raspberry Pi 5 or Rockchip
RK3588-class board. That source also proposes a four-model IMM-JIPDA tracker variant and a
multi-cue track classifier -- see [spec section 16.7](spec.md#167-track-level-classification) and the
`imm-motion-model-bank`, `jipda-track-existence`, `imm-jipda-mesh-variant` and `track-cue-fusion` plan
tasks -- and a camera-pointing law. Its net-capture/interceptor application stays outside this
project's [measurement-only scope](spec.md#measurement-only-scope); the sensor-pointing-only variant
is scheduled as its own capability, with its own quality measurement, in
[spec section 16.8](spec.md#168-guidance-pointing-law-and-quality-measurement) and the
`sensor-pointing-guidance-law` / `pointing-guidance-quality-suite` plan tasks.

## Stand A: compute host candidates

| Candidate | Class | Datasheet facts (unmeasured) | Source |
| --- | --- | --- | --- |
| Raspberry Pi 5 (8 GB/16 GB) | Arm SBC, no on-die NPU | Broadcom BCM2712, 4x Cortex-A76 at up to 2.4 GHz, one PCIe 2.0 x1 lane (FPC) for an accelerator such as a Hailo-8/8L AI HAT, two 4-lane MIPI CSI/DSI combo connectors. Already has a `vcgencmd` throttle/rail profile in [telemetry-sources.md](telemetry-sources.md#companion-computers-and-boards) | Vendor documentation; confirm the current RAM and connector revision before acquisition |
| Orange Pi 5 / 5 Plus / 5 Pro (RK3588/RK3588S family) | Arm SBC with an integrated NPU | Rockchip RK3588(S), 4x Cortex-A76 + 4x Cortex-A55, a vendor-stated INT8 NPU on-die (publicly cited around 6 TOPS), more MIPI CSI lanes than the Pi 5 on most carrier variants. Already has a thermal-zone/devfreq/debugfs profile class in [telemetry-sources.md](telemetry-sources.md#companion-computers-and-boards) | Vendor documentation; exact RAM, CSI lane count and PCIe generation vary by board variant and must be confirmed per unit |
| Hailo-8 / Hailo-8L accelerator (added to either host) | M.2/PCIe NPU add-on | `hailortcli measure-power`/`measure-temp` already has a documented profile in [telemetry-sources.md](telemetry-sources.md#companion-computers-and-boards); power measurement needs an on-board INA part and the command fails with `HAILO_UNSUPPORTED_OPCODE(48)` on the Raspberry Pi AI HAT | Same page |

Both boards are plausible `select-reference-host` bootstrap candidates under
[Stand A](test-stands.md#stand-a-module-measurement-stand). Neither is assumed final; the task
compares at least two available candidates under identical workload and limits, and a reduced or
different host set is a valid outcome.

## Stand B/C: sensor candidates by spec section 7.6 evidence role

### Visible / thermal camera (`AIRBORNE_CANDIDATE`, first baseline)

No specific module is shortlisted here; spec section 7.6 already treats the wide/narrow/stereo camera
role generically, and [perception-bench-test-plan.md](perception-bench-test-plan.md) covers the
capture/optics trial. A CSI-2 module (for example a Raspberry Pi Camera Module family part) or a
USB/GigE industrial camera are both candidate interfaces for Stand B; the characterization trial, not
this list, decides between them.

### Lidar / scanning laser (`AIRBORNE_CANDIDATE`, active optical range)

| Candidate | Class | Datasheet facts (unmeasured) | Source |
| --- | --- | --- | --- |
| Ouster OS-class (for example OS1) | Spinning mechanical, UDP | Already a supported dictionary-described format in [telemetry-sources.md](telemetry-sources.md#sensors) (`lidar_data_format` metadata, `RNG19_RFL8_SIG16_NIR16` default profile). This is the sensor class the adapted paper's own detector (VoFOD) was built on | [telemetry-sources.md](telemetry-sources.md#sensors) |
| Solid-state / non-repetitive-scan lidar (for example a Livox-class module) | Compact, no spinning head | Denser near-axis point return than a spinning unit at a fixed frame time, a property relevant to hitting a small, fast target; no adapter exists yet, and its raw format needs its own `telemetry-sources.md` row before a profile is written | Vendor documentation; unverified in this session |
| Compact ToF module (for example a TFmini-S-class part) | Short-range ToF | Spec section 7.6 already names this class as **not** a 100 m small-target sensor; useful only as a near-field/contact-zone reference, per the same row's citation | [spec section 7.6](spec.md#sensor-family-registry-and-feasible-observation-roles) |

### Microphone / acoustic array (`AIRBORNE_CANDIDATE` only with calibrated geometry)

Verified against the vendor's own microphone-specific selection guide,
`infineon-xensiv-mems-microphones-productselectionguide-en.pdf` (repository root, "XENSIV MEMS
microphones," version V1.0_EN, dated 05/2026) -- this replaces the earlier press-release-sourced
figures in this document with the exact product-table values. SNR and AOP (1%/10% THD) are both
dB(A)/dBSPL unless noted; all digital parts share a PDM interface and bit clock, the property a
TDOA/beamforming array needs for sample-level synchronization "for free."

| Candidate | Qualification | SNR | AOP (1%/10% THD) | Current | Package (mm) | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| XENSIV IM63D135A | AEC-Q103-003, IP57, -40 to +105C | 63.5 | 135 | 1100 uA | 3.50 x 2.65 x 0.98 | **Explicitly optimized for exterior/external applications**: highest AOP in the whole family, for wind-noise robustness in loud outdoor environments, at the lowest SNR of the shortlisted parts |
| XENSIV IM73D122 | Consumer | 73 (ultrahigh SNR) | 120/122 | 980 uA | 4.00 x 3.00 x 1.20 | Highest-SNR digital part, for a faint/distant source, at a lower AOP than IM72D128 |
| XENSIV IM72D128 | Consumer | 72 | 126/128 | 980 uA | 4.00 x 3.00 x 1.20 | Balanced high SNR and high AOP, the all-around digital candidate |
| XENSIV IM69D130 | Consumer | 69 | 128/130 | 980 uA | 4.00 x 3.00 x 1.20 | Widely used baseline part; evaluation flex boards already exist (`KIT_IM69D130_FLEXKIT`) |
| XENSIV IM73A135 | Consumer, analog | 73 (ultrahigh SNR + AOP) | 132/135 | 170 uA at 2.75 V | 4.00 x 3.00 x 1.20 | Best combined SNR+AOP in the family; needs an external multi-channel synchronized ADC instead of a shared PDM clock |

Guide pages: consumer table page 7 (IM73D122, IM72D128, IM69D130, IM73A135); automotive table page 4
(IM63D135A); evaluation boards page 9. The full consumer table lists 14 digital and 3 analog parts and
the full automotive table lists 9 AEC-Q103-003 parts; this is a curated shortlist, not the complete
catalog, trading SNR against AOP against environmental rating for this project's outdoor,
synchronized-array use case -- the guide itself states no single part wins on every axis.

A single microphone has no justified range or bearing per spec section 7.6; an array needs calibrated
geometry and the section 7.9 clock-alignment evidence before any bearing claim, and propeller/wind
noise and acoustic association must be measured on the actual installed array. IM63D135A's
weatherization and wind-noise robustness make it the lead candidate for an uncovered outdoor mount;
IM72D128 or IM69D130 are lead candidates for a covered or indoor-adjacent mount where the AEC
qualification's cost and lower SNR are not needed.

### Radar (`AIRBORNE_CANDIDATE`, RF scatter)

Verified against the vendor's own radar-specific selection guide,
`infineon-xensiv-radar-sensors-productselectionguide-en.pdf` (repository root, "XENSIV radar
sensors," version V1.0_EN, dated 05/2026) -- this corrects and replaces the earlier, search-sourced
radar entries in this document.

| Candidate | Band / mode | Verified facts | Guide page |
| --- | --- | --- | --- |
| XENSIV BGT60CUTR13AIP | 60 GHz FMCW, CMOS, 1Tx/3Rx AIP (L-shaped: azimuth + elevation) | 7 GHz bandwidth; 11 dBm output power; detection range over 20 m at boresight and up to 16 m across the full field of view -- the longest-range compact IoT part in the family; on-chip hardware-accelerated pre-processing and motion detection offload the host MCU; 4.3 x 6.05 x 0.9 mm package | 2, 15 |
| XENSIV BGT60TR13C | 60 GHz FMCW, 1Tx/3Rx AIP (L-shaped) | 400 MHz/us chirp speed, >5 GHz bandwidth, people detected up to 15 m, azimuth + elevation angle measurement, <5 mW duty-cycled (FCC waiver) | 8, 11 |
| XENSIV BGT60UTR11AIP | 60 GHz FMCW, AIP, +-60 deg FoV | 6 GHz bandwidth, ramp speed up to 400 MHz/us, sub-mm movement sensing, detection up to 15 m, sub-mA average current, 16 mm2 package | 8, 13 |
| XENSIV BGT24LTR11 / BGT24LTR22 | 24 GHz, 1Tx/1Rx or 2Tx/2Rx | Measures speed, direction **and distance** (not Doppler-only); product benefit copy states long-range moving-object detection up to 50 m and speed up to +-100 km/h. The guide's general 24 GHz-vs-60 GHz comparison states the 24 GHz band itself reaches up to 100 m, against up to 20 m for 60 GHz, trading away up to 28x of 60 GHz's range resolution and the AIP integration (no integrated antenna, ~5x larger system) | 3, 16 |

The guide's own band comparison (page 3) is the resolution-versus-range trade-off this project's own
adapted-paper analysis already expected: 24 GHz (BGT24LTR11/22) buys range and weather/obstacle
robustness at a resolution and integration cost; 60 GHz (BGT60CUTR13AIP, BGT60TR13C) buys angle
resolution, a smaller antenna-in-package footprint and lower host-compute cost (via the CUTR13AIP's
on-chip accelerator) at a shorter stated range. Both bands are plausible Stand B/C candidates for
different roles in a layered perimeter; only a measured trial decides between them for this project's
actual range and clutter conditions.

**Excluded from this shortlist.** The guide also lists automotive-grade parts that do not fit a
hobbyist/research reference mesh: BGT60ATR24AIP (60 GHz, 2Tx/4Rx AIP, AEC-Q100 Grade 2) targets
in-cabin occupant/vital-sign monitoring, not exterior area coverage; the RASIC CTRX8191F/CTRX8191FS
77-81 GHz automotive transceiver family (cascadable to 24T24R, ISO 26262 ASIL C) is explicitly stated
in the guide as **not available via Infineon's distribution partners** (page 7), so it is inaccessible
through the ordinary channel this project would use.

Spec section 7.6 already cautions that a frequency-band name is not a performance guarantee; cross
section, beamwidth, clutter, antenna gain and full-system power decide small-target feasibility at this
project's actual range, and only a measured Stand B trial can settle it. The guide's figures are
vendor-stated detection/presence ranges for its own reference use cases (people/occupant sensing), not
a measured claim for this project's small-airborne-target scenario.

## What this document does not establish

- No candidate above has been measured against a Stand A/B/C requirement. Every figure is a vendor
  claim. The radar and microphone tables are now both read directly from the vendor's own
  family-specific selection guides, with page citations, superseding the earlier search-sourced
  figures; the general `infineon-xensiv-sensor-solutions-product-selection-guide-en.pdf` (120 pages,
  repository root) was also read and its radar and MEMS-microphone sections (pages 85-100 and 77-84)
  confirmed as the same content as the two dedicated guides, so no further sensor family in that
  broader catalog (current, position, pressure, gas sensors) adds a candidate for this project's camera
  / lidar / microphone / radar / compute-host shortlist.
- Thermal imaging, event cameras and contact/vibration sensors from the spec section 7.6 registry are
  not shortlisted here because the source document did not propose them; they remain candidates under
  the existing registry if a later gap calls for them.
- No interceptor, net-capture or other effector hardware is shortlisted or in scope; see the
  [measurement-only scope](spec.md#measurement-only-scope). The guidance pointing law in
  [spec section 16.8](spec.md#168-guidance-pointing-law-and-quality-measurement) is software-only at
  G3 and needs no new hardware here: it reads an existing tracker's state and is scored against a
  frozen wide recording. A physical gimbal, PTZ head or steerable-antenna mount is deliberately not
  shortlisted; that stays later, separately-scheduled hardware work once a software pointing-quality
  result exists to combine with a measured mechanical response.
