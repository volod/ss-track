# Board and sensor telemetry sources

Catalog and design input for
[specification section 18](spec.md#18-board-and-sensor-telemetry). The specification stays
authoritative when they differ. This page names sources so adapters can be scheduled: it selects no
hardware, and nothing here is a measured property of any device. Format and interface facts were
read from the linked sources on 2026-11-02 and must be confirmed on the actual board and firmware.
Where only a community source exists, the row says so.

## How a source describes itself

The useful distinction between telemetry formats is where their schema lives. It decides how an
adapter is written, and how much new code a new device needs.

| Class | Where the schema is | Examples | Adapter work |
| --- | --- | --- | --- |
| Self-describing | Inside the data | ULog, DataFlash, MCAP, Blackbox, GPMF, FIT, JLS, IIO scan elements | One reader per format. A new message or firmware needs no code |
| Dictionary-described | In a versioned file outside the data | MAVLink XML, ROS `.msg`, Protobuf descriptors, DroneCAN DSDL, CAN DBC, Ouster metadata | One reader, plus a pinned dictionary |
| Undescribed | Only in documentation | hwmon, thermal and powercap sysfs, `vcgencmd`, `tegrastats`, TI mmWave TLV | A profile written here, declaring paths or layouts, units and scale |

## Flight controllers

| Family | Examples | On-board log | Live link |
| --- | --- | --- | --- |
| [Pixhawk standard](https://docs.px4.io/main/en/flight_controller/autopilot_pixhawk_standard.html) | FMUv6X, FMUv6X-RT and FMUv6C boards from Holybro, CUAV, NXP and RaccoonLab, running PX4 | ULog on SD card | MAVLink |
| ArduPilot autopilots | Boards running ArduPilot | DataFlash `.bin` on SD card or flash | MAVLink, saved by ground stations as `.tlog` |
| Betaflight and iNav | FPV flight controllers | Blackbox to flash or SD card | MSP, not covered here |
| DJI aircraft | Closed system | Flight record `.txt`, encrypted from version 13 | Closed |

### ULog (PX4)

[Specification](https://docs.px4.io/main/en/dev_log/ulog_file_format.html). Little-endian.

| Part | Layout |
| --- | --- |
| File header, 16 bytes | Magic `ULog 01 12 35`, version byte, `uint64` start time in us |
| Message header | `uint16 msg_size`, `uint8 msg_type`, where size excludes the header |
| Definitions | `B` flag bits, first; `F` format; `I` info; `M` multi info; `P` parameter; `Q` default parameter |
| Data | `A` subscribe, `D` data, `L` and `C` logged strings, `S` sync, `O` dropout, plus `I`, `M`, `P`, `Q` |
| `F` format | `name:type field;type[n] field;`, with `char`, `bool`, `int8_t` to `uint64_t`, `float`, `double` or a nested format |
| `A` subscribe | `uint8 multi_id`, `uint16 msg_id`, name. Binds a topic instance to a `msg_id` |
| `D` data | `uint16 msg_id`, then the fields as declared |

Reader rules from the specification: ignore unknown messages, refuse any log with an unknown
`incompat_flags` bit, and discard a message cut off at the end of a log. Fields beginning `_padding`
are ignored, and trailing padding may be missing from the data, which a spike reader must handle or
every message looks short. `timestamp` is `uint64` us, monotonic per `msg_id`.

### DataFlash (ArduPilot)

No formal specification exists. The sources are
[`LogStructure.h`](https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Logger/LogStructure.h)
and [`DFReader.py`](https://github.com/ArduPilot/pymavlink/blob/master/DFReader.py).

| Part | Layout |
| --- | --- |
| Record header | `0xA3 0x95`, then a one-byte message id |
| `FMT` | `type`, `length`, `name[4]`, `format[16]`, `labels[64]`, 89 bytes with its header |
| `UNIT` and `MULT` | Tables mapping an id to a unit string, and an id to a multiplier |
| `FMTU` | For one message type, the `UnitIds` and `MultIds` of each field |

| Format character | Type | Format character | Type |
| --- | --- | --- | --- |
| `b` `B` | `int8`, `uint8` | `n` `N` `Z` | `char[4]`, `char[16]`, `char[64]` |
| `h` `H` | `int16`, `uint16` | `c` `C` | `int16`, `uint16`, times 100 |
| `i` `I` | `int32`, `uint32` | `e` `E` | `int32`, `uint32`, times 100 |
| `q` `Q` | `int64`, `uint64` | `L` | `int32` latitude or longitude, times 1e7 |
| `f` `d` | `float`, `double` | `M` | `uint8` flight mode |
| `a` | `int16[32]` | | |

Records carry no length, so a reader needs the `FMT` of a message type before it can skip that type.
Units in the log itself make this the richest self-describing format here.

### MAVLink and telemetry logs

[Serialization](https://mavlink.io/en/guide/serialization.html) and
[XML definitions](https://mavlink.io/en/guide/define_xml_element.html).

| Part | MAVLink 2 | MAVLink 1 |
| --- | --- | --- |
| Start marker | `0xFD` | `0xFE` |
| Header | `len`, `incompat_flags`, `compat_flags`, `seq`, `sysid`, `compid`, 24-bit `msgid` | `len`, `seq`, `sysid`, `compid`, 8-bit `msgid` |
| Trailer | CRC-16, optional 13-byte signature | CRC-16 |
| Payload | Up to 255 bytes, with trailing zeros removed | Up to 255 bytes, full length |

The schema is an XML dialect: messages hold typed fields with `units` and `enum`, and fields after
`<extensions/>` can be added without breaking a receiver. Fields go on the wire sorted by size, largest
first and stable within a size. The checksum folds in `CRC_EXTRA`, computed from the message
definition, so a reader with another definition fails the checksum: a built-in schema-mismatch
detector. An unknown `incompat_flags` bit means discard the packet.

A `.tlog` is a sequence of big-endian `uint64` us receive times, each followed by one MAVLink frame,
as [`pymavlink`](https://github.com/ArduPilot/pymavlink/blob/master/mavutil.py) reads it. That time is
when the ground station received the frame, so it is an arrival time.

### Blackbox (Betaflight)

[Internals](https://betaflight.com/docs/development/Blackbox-Internals). `H name:value` ASCII lines,
then frames with no length or checksum: `I` intra, `P` inter, `G` GPS, `H` home, `S` slow, `E` event.
`H Field X name:`, `predictor:`, `encoding:` and `signed:` declare every field of frame type `X`.

Decoding reverses an encoding, such as signed variable byte, Elias delta or `TAG8_8SVB`, and then a
predictor such as last value, straight line or average of two. Damage is mainly dropped bytes, and a
rejected frame invalidates every `P` frame until the next `I`, so a reader reports rejected frames and
never interpolates them. One file can hold several sessions.

### DJI

[`dji-log-parser`](https://docs.rs/dji-log-parser) documents AES-encrypted records from format
version 13, with a keychain fetched from a DJI API using a developer key. ss-track stays out of this
path. An operator may import their own decoded export as a declared CSV, under a profile.

## Companion computers and boards

| Board | Interface | Facts | Source |
| --- | --- | --- | --- |
| Any Linux board | hwmon, thermal, cpufreq, devfreq sysfs | See [Linux interfaces](#linux-interfaces) | Kernel documentation |
| Raspberry Pi 4 and 5 | `vcgencmd` | `get_throttled` bits 0 to 3 are now: undervoltage, Arm capped, throttled, soft limit. Bits 16 to 19 say each condition has occurred. `measure_temp [pmic]`, `measure_clock <arm core v3d ...>`, `measure_volts <core sdram_c ...>` | [Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/os.html) |
| Raspberry Pi 5 | `vcgencmd pmic_read_adc` | Pi 5 only. Lists rails as `EXT5V_V volt(24)=5.06520000V`, with `current(N)=...A` lines for supply rails | Same page |
| NVIDIA Jetson | `tegrastats --interval <ms> --logfile <file>` | `RAM`, `SWAP`, `CPU [X%@Z,...]`, `EMC_FREQ`, `GR3D_FREQ`, `NVDLA`, block temperatures, rails as `VDD_x cur/avg` in mW. CPU load is described as a rough approximation from `/proc/stat` | [Jetson Linux r36.4](https://docs.nvidia.com/jetson/archives/r36.4/DeveloperGuide/AT/JetsonLinuxDevelopmentTools/TegrastatsUtility.html) |
| NVIDIA Jetson | INA3221 through hwmon | Rails differ by carrier board, and a custom board may have none. `VDD_IN` is the module total, per [NVIDIA forum staff](https://forums.developer.nvidia.com/t/gpu-power-consumption-from-tegrastats-utility/290190) | Community |
| Rockchip RK3588 family | thermal zones, devfreq, debugfs | NPU load is read from debugfs and needs root, per the third-party [`rockchip-stats`](https://pypi.org/project/rockchip-stats/) | Community |
| Hailo-8 modules | `hailortcli measure-power`, `run --measure-power`, `--measure-temp` | Power needs an on-board INA part. It fails with `HAILO_UNSUPPORTED_OPCODE(48)` on the Raspberry Pi AI HAT, and two on-die sensors `TS0` and `TS1` give temperature, per the [Hailo community](https://community.hailo.ai/t/how-to-measure-the-power-and-temp-of-hailo-8-m-2-async/100) | Community |
| Coral PCIe Edge TPU | `/sys/class/apex/apex_0/` | Trip points default to 85000, 90000 and 95000 millidegrees, stepping the clock down. `temp` in millidegrees C is from community use | [Coral](https://www.coral.ai/docs/pcie-parameters/) |
| x86 hosts | powercap RAPL | See below | Kernel documentation |

## Linux interfaces

### hwmon

Attributes under `/sys/class/hwmon/hwmon*/`, identified by the `name` file, with `*_label` for a
channel name. Units come from the
[hwmon ABI](https://github.com/torvalds/linux/blob/master/Documentation/ABI/testing/sysfs-class-hwmon).

| Attribute | Unit | Attribute | Unit |
| --- | --- | --- | --- |
| `inY_input` | millivolt | `powerY_input`, `powerY_average` | microwatt |
| `currY_input` | milliampere | `energyY_input` | microjoule |
| `tempY_input` | millidegree C | `humidityY_input` | milli-percent |
| `fanY_input` | RPM | `*_alarm` | Boolean |

Numbering is not stable across boots, so a profile selects a chip by `name` and a channel by label.
The [INA3221 driver](https://docs.kernel.org/hwmon/ina3221.html) adds `in[456]_input` shunt voltage in
uV, `shunt[123]_resistor` in uOhm, `samples` and `update_interval`. A value read faster than that
interval is a repeat, so a sampler must not count it as a new sample.

### powercap

[`energy_uj`](https://docs.kernel.org/power/powercap/powercap.html) is a counter in microjoules, with
`max_energy_range_uj` as its range, under zones named `intel-rapl:j` and `intel-rapl:j:k`, where the
`name` file identifies each. A difference must handle the wrap at that range, and
[reading needs root](https://github.com/canonical/ujoules). It covers CPU package domains, so it never
backs an energy claim at a declared system boundary.

### Industrial I/O

The [IIO buffer interface](https://docs.kernel.org/driver-api/iio/buffers.html) is a self-describing
high-rate stream, and the natural route for an IMU, ADC or pressure sensor on a Linux board.
`scan_elements/` holds `enable`, `index` and `type` per channel. The `type` string has the grammar
`[be|le]:[f|s|u]bits/storagebits[Xrepeat][>>shift]`, so `le:s12/16>>4` is little-endian, signed, 12
bits in 16, shifted right by 4. Ordering enabled channels by index gives one sample's layout, and
that maps directly onto a NumPy dtype. A timestamp, when enabled, is the last element.

### Camera metadata

libcamera's `SensorTimestamp` is nanoseconds in `CLOCK_BOOTTIME` for the
[first exposed row](https://patchwork.libcamera.org/patch/12173/), though the
[simple pipeline](https://patchwork.libcamera.org/patch/12180) fills it from DMA time, which is not
that moment. This is the same care that section 5 asks of V4L2 buffer timestamps.

## Sensors

| Sensor | Format | Schema class | Facts | Source |
| --- | --- | --- | --- | --- |
| GoPro cameras | GPMF in an MP4 `gpmd` track | Self-describing | KLV: FourCC, type, struct size, repeat, big-endian, 32-bit aligned. `SCAL`, `SIUN`, `STNM`, `TSMP`, `TYPE` give scale, units, names and timing. `ACCL` m/s^2, `GYRO` rad/s, `GPS5`, `GPS9`, `MAGN` uT, `CORI`, `IORI`, `GRAV`, `SHUT` | [gpmf-parser](https://github.com/gopro/gpmf-parser) |
| TI mmWave radar | TLV over UART | Undescribed | Magic `02 01 04 03 06 05 08 07`, frame header, then 8-byte TLV headers. Type 1 is 16 bytes per point. Header size varies by demo and SDK: 40, 48 or 52 bytes reported, so pin the SDK. Packets pad to 32 bytes | [TI out-of-box demo](https://dev.ti.com/tirex/explore/content/mmwave_industrial_toolbox_4_10_0/labs/Out_Of_Box_Demo/docs/understanding_oob_uart_data.html), [TI forum](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/1037458/iwr6843-uart-output-data-format) |
| Ouster lidar | UDP packets | Dictionary | `udp_profile_lidar`, default `RNG19_RFL8_SIG16_NIR16`. `lidar_data_format` metadata gives geometry. `LEGACY` is deprecated from firmware 3.2 | [Ouster](https://docs.ouster.com/sensor-docs/docs/sensor-data/lidar-data) |
| Prophesee event cameras | `.raw` EVT2 or EVT3 | Self-describing header | ASCII `%` header with `format EVT3;height=720;width=1280`, then binary words. Word sizes of 32 and 16 bits are from secondary sources | [Prophesee](https://docs.prophesee.ai/stable/data/file_formats/raw.html) |
| iniVation event cameras | AEDAT 4.0 | Dictionary | Size-prefixed FlatBuffers, per-file compression among LZ4 and Zstd | [iniVation](https://docs.inivation.com/software/software-advanced-usage/file-formats/aedat-4.0.html) |
| Garmin and sports sensors | FIT | Self-describing | Definition messages describe data messages, and developer fields extend any message at runtime | [Garmin](https://developer.garmin.com/fit/articles/cookbook/developer_data.html) |
| GNSS receivers | NMEA, UBX, RTCM | Undescribed or dictionary | Serial streams. `pyubx2`, `pynmeagps` and `pyrtcm` are reference parsers | PyPI |
| CAN sensors | DBC, DroneCAN DSDL, Cyphal DSDL | Dictionary | Frames with an external dictionary. `cantools`, `dronecan` and `pycyphal` are reference parsers | PyPI |

## Power instruments

| Instrument | Output | Facts | Source |
| --- | --- | --- | --- |
| Joulescope | JLS v2 | Open tag-length-value format, little-endian, with fixed and variable rate signals | [JLS format](https://jls.readthedocs.io/en/stable/h_format.html) |
| Qoitech Otii Arc | CSV export | 4 ksps default on Arc. Export is from the app, with no dedicated CSV API | [Otii](https://docs.qoitech.com/user-manual/otii3/projects/csv-recording-export) |
| Nordic PPK2 | CSV export | Export from nRF Connect Power Profiler. One report of wrong digital channels in v5.0.0 | [Nordic forum](https://devzone.nordicsemi.com/f/nordic-q-a/112245/issue-exporting-data-to-csv-file-from-nrf-connect-for-desktop-ppk2-device/489553) |

These reach `power-trace-ingest`, and their calibration decides any energy claim.

## Containers and records

| Format | Role | Facts | Source |
| --- | --- | --- | --- |
| MCAP | Robotics log container | Major 0, opcode-framed records, `Schema` and `Channel` records, nanosecond `log_time` and `publish_time`, optional chunks with Zstd or LZ4, CRCs, summary index. Readers ignore unknown fields | [Specification](https://mcap.dev/spec) |
| MCAP registry | Schema encodings | `protobuf`, `flatbuffer`, `capnproto`, `ros1msg`, `ros2msg`, `ros2idl`, `omgidl`, `jsonschema`. Message encodings add `ros1`, `cdr`, `cbor`, `msgpack`, `json` | [Registry](https://mcap.dev/spec/registry) |
| rosbag2 | ROS 2 bags | [MCAP became the default](https://index.ros.org/p/rosbag2_storage_default_plugins/) storage plugin, with sqlite3 still shipped | ROS index |
| OpenTelemetry | Metric names | `hw.temperature`, `hw.power`, `hw.energy`. [Still in development](https://opentelemetry.io/docs/specs/semconv/hardware/common/), so a possible export name and never a foundation | OpenTelemetry |

MCAP deserves attention beyond ingest: it carries Protobuf and JSON Schema descriptors inside the file,
which matches the event contracts here. A run bundle could later be exported to MCAP for inspection in
existing viewers.

## Existing libraries

Versions and licenses from PyPI. ss-track is MIT licensed.

| Library | Version | License | Use here |
| --- | --- | --- | --- |
| `pyulog` | 1.3.0 | BSD-3-Clause | Test oracle for ULog |
| `pymavlink` | 2.4.50 | LGPLv3 | Reference reading only |
| `mavsdk` | 4.1.0 | BSD-3-Clause | Not used: it drives vehicles, and adapters are read-only |
| `orangebox` | 0.5.0 | GPL-3.0 | Reference reading only |
| `rosbags` | 0.11.9 | Apache-2.0 | Optional reference for CDR |
| `mcap` | 1.6.0 | MIT | Test oracle for MCAP |
| `foxglove-sdk` | 0.30.3 | MIT | Not used |
| `asammdf` | 8.8.28 | LGPLv3+ | Not used: automotive MDF4 has no scheduled source |
| `cantools` | 45.1.2 | MIT | Later oracle for DBC |
| `python-can` | 4.6.1 | LGPL-3.0 | Not used |
| `dronecan`, `pycyphal` | 1.0.27, 1.27.1 | MIT | Later oracles |
| `pyubx2`, `pynmeagps`, `pyrtcm` | 1.4.1, 1.1.8, 1.2.1 | BSD-3-Clause | Later oracles |
| `py-gpmf-parser` | 0.1.1 | Apache-2.0 | Test oracle for GPMF |
| `fitdecode` | 0.11.0 | MIT | Later oracle |
| `jetson-stats` | 7.2.2 | AGPL-3.0 | Reference reading only |
| `pylibiio` | 1.0 | LGPL-2.1-or-later | Not used: the sysfs and character device need no library |
| `joulescope`, `ppk2-api` | 1.7.3, 0.9.2 | Apache-2.0, GPLv2 | Reference reading only |
| `kaitaistruct` | 0.11 | MIT | Not used, see below |
| `pyarrow` | 26.0.0 | Apache-2.0 | Optional export extra only |

## Why from-scratch adapters

Three reasons, each specific to this project.

**Licensing.** Several of the established parsers are LGPL, GPL or AGPL, and this is an MIT project.
A reader written from a public format specification carries no such terms. Permissive libraries stay
useful as test oracles.

**Determinism.** Evidence must be reproducible byte for byte across hosts. A parser that converts
units on the way in, or fills gaps, changes what is stored. A reader here keeps exact values and names
every skipped byte.

**Speed through schema.** A declared record layout is a NumPy dtype. A reader walks framing once, in
Python, then decodes each message type as one array. A spike decoded a synthetic 208 MB ULog of 4.28
million messages at 5.0 million messages per second, where `pyulog` 1.3.0 reached 2.0 million. Both
ran on one core of an i9-14900K, three runs each, and the checked timestamp, gyro and voltage columns
matched exactly. Peak memory stayed bounded by gathering 64 Ki rows at a time. Python is limited by
the framing walk, and that figure sets the order of magnitude, since a real log has more topics and a
Raspberry Pi 5 is slower. The reader on a target host must be measured there.

Declarative tools such as Kaitai Struct solve a different problem. They need a compile step and build
an object per record, and vectorizing records is where the gain comes from. The small layout language
in `declared-binary-layouts` covers fixed records and TLV only, and a format needing more gets a reader.

## Adapter design

```text
source bytes          immutable, hashed, read-only copy
   |  format reader   ulog, dataflash, tlog, blackbox, mcap, gpmf, iio, tlv, lines, sysfs
   v
observed schema       what this file declared, normalized and hashed
   |
   v
raw typed columns     exact values, little-endian, one file per field, sealed index
   |  profile         applied at read, versioned, never baked into the columns
   v
canonical channels    SI unit, frame, clock domain, sensitivity
   |
   +-- report, comparison, Parquet or Arrow export
   +-- corpus stream of an encounter, through its split rules
```

This is the fl-op layering, applied where it fits. A format reader owns the physical schema, a profile
is the mapping, and the channel catalog is the canonical model. A tractor and an excavator are one
`asset` in fl-op, and a PX4 `battery_status.voltage_v` and an ArduPilot `BAT.Volt` are one
`power.battery.voltage` channel here.

Columns store raw decoded values because a wrong unit in a profile must be fixable by a new profile
version, with nothing re-staged, and because floating-point conversion is not where evidence should
acquire rounding.

Parquet and Arrow stay exports. `pyarrow` stamps `created_by: parquet-cpp-arrow version 26.0.0` into
each file, so file bytes change with the library, and a hash of them would not be reproducible. NumPy
already reads raw typed columns with memory mapping, so the evidence form needs no new dependency.

Live streams use the same readers on bounded chunks. A receive time is an arrival time, a full queue
is counted loss, and each host's sustainable rate is measured, with anything above it `UNSUPPORTED`.

## Limits

- On-board rails and temperature are software-reported. They explain behavior, and they cannot back an
  energy claim, which needs the calibrated boundary of section 7.9.4.
- Flight logs hold GNSS tracks, serial numbers and parameters, so they are restricted by default.
- Adapters read. None sends a MAVLink command, sets a parameter or needs root, and a source that needs
  root is `UNSUPPORTED` for an unprivileged process.
- Synthetic fixtures prove a reader against the specification as understood.
  `collect-telemetry-samples` supplies real logs, because real firmware is where such understanding
  fails.
