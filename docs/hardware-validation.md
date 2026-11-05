> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Dynabook hardware validation — 2026-11-04

Status: BLOCKED at the QSPI numeric STA gate. No KAGURA-HD hardware PASS is claimed.

Source: origin https://github.com/siska-tech/kagura-hd.git, main at
`1d46c6db71eb48e486a8e038d41e5a44342fe699`; fresh clone into this directory.
Local working branch: `bringup-dynabook-standard`.

## Initial read-only observations (before user clarification)

- Dynabook Inc. dynabook GZ/HYL; Intel Core i7-1360P; 31.60 GiB physical RAM.
- Windows NT 10.0.26200.0 (OS API version; product edition not established).
- Installed directories: Gowin_V1.9.12.04_x64 and Gowin_V1.9.11.03_Education_x64.
- Standard-candidate installation contains gw_sh.exe and Programmer programmer_cli.exe.
  Exact executable version, Edition, license checkout and device entitlement remain unconfirmed.
- A license file exists. A date token is not proof of validity or entitlement.
  No license contents, host identifiers or authentication data are included here.
- USB Serial Converter A/B and COM8 are present; COM7 USB serial device is present.
  Tang Nano/RP2040 identity and port mapping have not been established.
- UGREEN 15390 camera and media devices report OK. FFmpeg DirectShow lists its video
  and digital audio inputs. Enumeration is not proof of HDMI lock or 48 kHz capture.
- Python resolves to WindowsApps alias but execution failed. CMake is absent from PATH.
- Existing sibling ../Kagura source and hardware acceptance records were found.
  They describe KAGURA-9 ABI 0.6 and historical QSPI testing, not KFB1 validation.
- Current KFB1 connect_rp2040 uses SoftSPI; it is not a QSPI implementation.

## Initial stop reason (superseded by user clarification below)

The user requires stopping when Standard license confirmation is unavailable.
The existing license's legitimacy, active configuration, successful checkout and GW1NR-9C
coverage have not been verified. gw_sh -version printed a Tcl console banner only;
this did not establish version or license validity. No synthesis was attempted.
RP2040 known-good firmware and filesystem backup / restoration have not been secured.
Do not open a serial REPL in a way that resets/intercepts the running application yet.

Resume with read-only license/version verification in the installed IDE, without changing
license configuration. Establish applicable EULA and generated-IP rights before release.
Locate a real Python interpreter, confirm exact port/device mapping, and secure existing
RP2040 firmware/files plus a documented recovery path before changing hardware state.

## Independent acceptance gates

| Gate | Result |
|---|---|
| Standard QSPI bitstream generation | PASS (generation only; gate failed) |
| Standard SPI build | NOT TESTED |
| QSPI numeric STA | FAIL: setup 0.097 ns < 0.100 ns |
| SPI numeric STA | NOT TESTED |
| SRAM programming / JTAG device identification | NOT TESTED |
| Physical wiring verification / PSRAM | NOT TESTED |
| HDMI lock / video patterns | NOT TESTED |
| KFB1 ABI 1.2 QSPI / READ / WRITE / FENCE | NOT TESTED |
| FILL / PRESENT | NOT TESTED |
| Cursor | NOT TESTED |
| COPY_RECT / BLIT timing | NOT TESTED |
| HDMI audio / nonzero samples | NOT TESTED |
| RP2040 recovery | NOT TESTED |
| Release conditions | BLOCKED |

No FPGA/RP2040 write, driver update, license change, push, tag or release was performed.
A rejected QSPI bitstream and pre-change KAGURA-9 capture exist locally. No new firmware or release candidate exists.


## Resumed run after user clarification

On 2026-11-04 the user confirmed that the license is valid and authorized continuing;
Python is available through uv. License validity is user-confirmed, not independently audited.
No license settings were changed. Public redistribution rights remain a separate pending gate.

uv selected installed Python 3.14.7. UV_CACHE_DIR was directed to build/uv-cache to avoid
sandbox cache permission failures; the interpreter directory was prepended to this process PATH.
The existing build script and Tcl were used without modifications. All 12 pinned HDMI files
passed tools/check-dependencies.ps1. No RTL, manifest or constraint changes were made.

| QSPI build result | Standard V1.9.12.04 (64-bit) |
|---|---|
| Device/package/speed | GW1NR-9C / GW1NR-LV9QN88PC6/I5 |
| Logic | 7713 / 8640 |
| Register total | 5346 / 6771 (5338 logic FF + 8 I/O FF) |
| CLS | 4208 / 4320 (98%) |
| BSRAM | 19 / 26 |
| DSP | 1 / 10 |
| Worst setup slack | 0.097 ns |
| Worst hold slack | 0.527 ns |
| Setup / hold violated endpoints | 0 / 0 |
| Negative analyses | none |
| Required setup gate | >= 0.100 ns: FAIL |
| Release ready | false |

Rejected artifact: build/kagura-fb-qspi/impl/pnr/kagura_fb.fs
SHA-256: ed5b1fbb19f136a5d9ec1a4fbe9b5036c2a8eec4eaad2b5eda6faba4ff87692a

Evidence: build/kagura-fb-qspi/build.log, timing-status.json and impl/pnr/kagura_fb.{rpt.txt,tr}.
The build wrapper exited 1 on its existing timing gate after generating the bitstream.
The limiting path is core/display/held_palette_75_s0/Q to core/display/palette_75_s0/D,
system54 to pixel74, under the existing 10 ns bundled-mailbox CDC maximum delay.
The timing report attributes 4.283 ns to the inter-register data net. This identifies the
limiting routed path; it does not prove a root cause or justify relaxing the constraint.
Compared with the Education reference, synthesis/resource results also changed; tool-version
and synthesis differences prevent attributing the regression to Edition alone.

Next minimum engineering step: review this CDC path and placement with unchanged ABI and
constraints; if selecting another P&R configuration, use a bounded, documented experiment
and preserve this first-run evidence. Do not bypass the 0.100 ns gate. Hardware programming
and SPI follow-up are paused at this failure; no automatic rebuild retry was attempted.

## JTAG and existing HDMI baseline

Standard Programmer help identifies V1.9.12.04 (64-bit) build(2743).
FTDI cable enumeration and a read-only chain scan succeeded on the first attempt.
One GW1N-9C/GW1NR-9C-family device was detected, ID 0x1100481B.
Logs: build/bringup/jtag-cables.log and jtag-scan.log.
No SRAM or Flash programming was performed.

UGREEN DirectShow modes include 1280x720 MJPEG at 60 fps. One pre-change frame was
captured successfully as build/bringup/kagura9-baseline.png, with baseline-capture.log.
Visual inspection shows the existing MicroPython v1.26.0 Raspberry Pi Pico REPL banner.
This is evidence of existing KAGURA-9 display, not KAGURA-HD video success. The requested
capture mode alone does not independently establish the HDMI source timing.

## Recovery assets discovered, not yet applied

Sibling KAGURA-9 has firmware-rollback files and historical backup/restore records:
- kagura-flash-backup-d2ccc104.uf2: SHA-256
  b8d7a38056f63cb32ca69ac896e3171ab01a7d95f0c70c009f27c77c5d4afcb1
- kagura-installed-firmware-20261101.uf2: SHA-256
  f3be5008b4b6b8f9bc8a1601c1e6a302ca21a41e31faede503e0342f47b3078e

Files are under ../Kagura/build/firmware-rollback; full-flash backup and restoration records
also exist in its hardware evidence directories. Their match to the currently running RP2040
is not yet established. Historical COM7 semaphore timeouts warrant bounded, observable
communication tests, not driver changes or unbounded retry. No serial session was opened.

## Timing-improvement session

Detailed trial resources, delay analysis, rejected RTL alternatives and regression logs are
listed in [standard-timing.md](standard-timing.md). P&R-only trials and palette-only experiments
have not yet produced an accepted bitstream. Working RTL is restored to the baseline;
the final place 1 / route 1 trial failed with 166 unrouted nets. No serial connection, FPGA programming,
RP2040 firmware/filesystem write or Flash operation has occurred during this session.
Prepared slow QSPI diagnostics are software-only and are not a hardware PASS.


Final timing outcome: no trial passed. P&R settings 2/1, 3/1 and 1/1 failed routing;
1/0 had setup -0.475 ns. Palette-only staging experiments also failed routing or STA
and were rejected. No RTL changes remain. Full Verilator FB 26/26 and shared 22/22
passed on baseline and both experiments. C/Python 15/15, QSPI pin oracle 4/4 and all
three existing MicroPython driver groups passed. KAGURA-HD hardware gates remain NOT TESTED.
The numeric gate, source ABI and SDC remain unchanged. No candidate is approved for SRAM use.

The subsequent one-shot local-placement trial also failed the +0.100 ns gate (+0.060 ns,
zero setup/hold violated endpoints, full routing). Its standalone CST was discarded;
see [physical placement investigation](physical-placement.md). All hardware gates remain
NOT TESTED and the baseline build is preserved.
