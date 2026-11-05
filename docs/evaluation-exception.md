> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Evaluation-only timing exception and pre-insertion review

Exception EVAL-QSPI-SETUP-003PS-20261104, authorized by the user on 2026-11-04.
Timing optimization is closed. No further P&R/RTL optimization is authorized here.

## Fixed candidate and unchanged gate

Source baseline: 1d46c6db71eb48e486a8e038d41e5a44342fe699.
Standard V1.9.12.04 QSPI, GW1NR-LV9QN88PC6/I5, place 1 / route 2.
SHA-256: ed5b1fbb19f136a5d9ec1a4fbe9b5036c2a8eec4eaad2b5eda6faba4ff87692a.
Setup +0.097 ns, Hold +0.527 ns, setup/hold violated endpoints 0/0, full routing.
The +0.100 ns gate STILL FAILS by 0.003 ns (3 ps). Neither the checker nor its
threshold nor timing-status.json.release_ready is changed. This is an explicit
exception for volatile hardware evaluation, not a numerical PASS or Release waiver.
Only this exact hash is covered. Later failed optimization artifacts are excluded.
Formal Release use is prohibited; hardware results and removal of the timing
exception must receive separate Release review. No tag/push/publication is authorized.

## Palette mailbox / reset / 10 ns review

scanout captures page+192-bit palette and toggles the request only when ready.
One pending slot blocks another capture. Pixel-domain present_sync is two FF stages;
the consumer sees a new synchronized toggle no earlier than the third sampling edge
and applies page+palette together at VBlank. It then acknowledges that toggle. The
source does not reuse the held payload until the two-stage return acknowledgement.
Thus the bundled payload remains stable across the entire consuming window. VBlank
stall extends that window; it does not release or overwrite the payload early.

The baseline worst data route is 4.283 ns plus 0.458 ns clock-to-Q. The original
absolute inter-domain 10 ns max-delay constraint stays intact. It is a CDC bound,
not proof of analog metastability MTBF. Even a request sampled at the first possible
pixel edge must pass through the control pipeline before consumption, allowing two
pixel periods (~26.94 ns) from that first sample to the consuming edge. Source data
is launched with the request and is then held. The 3 ps gate deficit does not by itself
show a broken bundled-data handshake. This is a structural review, not silicon proof.

Both local resets derive from common asynchronous reset assertion and three-stage
release synchronization in each domain. Toggle, seen and acknowledgement state reset
to zero. Preserve common reset assertion and do not reset only one mailbox endpoint
in a running test. Existing cross-domain hold exceptions remain unchanged; global
zero hold violations do not establish external-interface hold timing.

## PSRAM and I/O review

PnR maps embedded PSRAM pads to LVCMOS18, host pins to LVCMOS33, and reset/LED bank
pins to LVCMOS18. This agrees with the board's documented separate voltage domains;
no rewiring, driver update or power-setting change is needed or permitted.
Gowin DS117 specifies a 1.8 V PSRAM interface bank for this device family:
https://dl.sipeed.com/fileList/TANG/Nano%209K/6_Chip_Manual/EN/DS117-2.9.3E_GW1NR%20series%20of%20%20FPGA%20Products%20DataSheet.pdf

The design uses die0 only (4 MiB); die1 is deselected and held reset, with DQ/RWDS
tri-stated. CK is 54 MHz with PLL output phase 67.5 degrees (3.472 ns), registered
CK enable, CS/reset and per-pin output enables. DDR DQ capture uses system-clock
IDDR with fixed RDL=6, not RWDS strobed calibration. The controller writes CR0=8F1F,
uses LAT=14 and transactions of 1..16 32-bit words, with a CS-high recovery gap.
The inherited KAGURA-9 records support these clock/PHY settings, but do NOT validate
KAGURA-HD burst transactions or this placement.

The SDC lacks complete min/max external PSRAM input/output delay constraints and
board/PVT margins. ODDR TX enable paths are noted as not fully timed by Gowin.
The existing host false paths also do not prove an operating QSPI speed; use slow
software GPIO transfer initially with data direction released before dummy clocks.
HDMI/TMDS clock constraints exist, but electrical eye/sink compatibility still needs
capture testing. No timing constraints will be relaxed to make this evaluation pass.

The memory simulation model assumes linear addressing and fixed latency; it does
not establish physical burst wrap, turnaround, data-eye or refresh behavior. Actual
burst/register behavior is not fully verified from a die-specific data sheet. This is
an explicit functional risk: test distinct 64-byte scratch data and boundaries BEFORE
basic drawing. A mismatch stops the test; do not replay an uncertain operation.
Startup writes of all-zero framebuffer data and controller initialized/READY are not
proof of correct PSRAM storage/readback. Board timing calibration and burst testing
remain Release blockers, irrespective of this 3 ps exception.

## Preflight disposition and staged execution

Static review found no demonstrated voltage conflict, overlapping bus drive or broken
palette-mailbox ownership/reset contract that mandates blocking a bounded volatile
characterization. Disposition: CONDITIONAL GO for this exact SRAM evaluation only;
external I/O timing closure and burst correctness are NOT certified. Stop on fault,
PSRAM mismatch, unstable USB/JTAG, or loss of recoverability. No Flash writes.

Before FPGA programming: single-connection RP2040 identity/boot-file check; preserve
current firmware recovery evidence and release the existing GPIO/PIO owner. Do not
replace RP2040 firmware or device files. Diagnostic sources execute in RAM only.
Then: (1) HDMI capture/carrier observation, (2) READY/initialization observation,
(3) exact KFB1/ABI 1.2/capability identification, (4) PSRAM read/write verification
and basic FILL/PALETTE/PRESENT with recognizable capture. A startup black frame alone
is not HDMI PASS; capture output settings alone are not HDMI source-lock proof.
Confirm sync using the identifiable drawn pattern before reporting a video PASS.
Keep cursor/BLIT/long-duration/audio Release acceptance separate from these minimum tests.

Execution evidence is stored privately under build/hardware-eval-097. Existing recovery
UF2s are retained; current firmware matching/backup must be established before SRAM load.
No firmware recovery Flash write is authorized during this evaluation; preserve images
as standby and prefer normal VM reset for the unchanged installed firmware.

## Hardware execution and stop result (2026-11-04 JST)

**Evaluation FAILED at PSRAM data verification; stopped without basic drawing.**
No further timing, PHY, RTL, firmware or placement trials were performed.

| Stage | Observed result |
| --- | --- |
| Candidate SRAM load | PASS: exact candidate SHA above; Programmer `--run 2`, SRAM Program, Finished, 4.12 s; no programmer readback verify claimed |
| HDMI startup | Black 1280x720 capture received; provisional observation only, source sync NOT accepted |
| Initialization | READY=1, BUSY=0, IRQ_N=1; FSM completion only, not memory correctness |
| Identity | Exact KFB1 / ABI 1.2 / capabilities 0x7f: `4b46423101027f` |
| Command response | FENCE completed |
| PSRAM | FAIL: distinct 64-byte write/read at volatile scratch address 300000 |
| Basic drawing | NOT RUN after memory mismatch |
| Release | BLOCKED: hardware failure and unchanged 3 ps timing deficit |

Scratch expected (hex):
```
0b30557a9fc4e90e33587da2c7ec11365b80a5caef14395e83a8cdf2173c6186abd0f51a3f6489aed3f81d42678cb1d6fb20456a8fb4d9fe23486d92b7dc0126
```
Actual:
```
d8d4f51a2f6489aed3f81d42668cb1d63120456a8eb4d9fe48486d92dcdc0126d8d4f51a2f6489aed3f81d42668cb1d63120456a8eb4d9fe48486d92dcdc0126
```
The two 32-byte halves are identical; additional bytes differ from either expected
half. This is consistent with a possible burst-wrap issue plus another data-integrity
problem, but does NOT establish the root cause. Fixed-latency sampling, memory burst
configuration, controller and diagnostic transport remain possible contributors.
No calibration/retry experiment was authorized or performed. The scratch restoration
branch was not reached after the mismatch; scratch PSRAM contents are disposable,
not firmware. No framebuffer draw or palette/present command followed the fault.

### Recovery and evidence integrity

Existing FPGA configuration restored with Programmer `--run 1` Reprogram, Finished,
0.48 s. This reloads existing Flash into SRAM without programming Flash. RP2040
QSPI pins had been released by diagnostic `finally: deinit()` before restoration.
A normal VM soft reset restarted the unchanged installed KAGURA-9 HDMI console
(QSPI 5 MHz), MicroPython v1.26.0. A restored HDMI capture shows its normal banner.
All 2 MiB of RP2040 Flash were hashed using the same full-XIP address range as the
backup and exactly matched the pre-evaluation SHA-256:
`7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`.
Actual-current full Flash backup and round-trip-verified recovery UF2 are retained
privately. No RP2040 files or firmware were installed. FPGA/RP2040 Flash writes: **0**.

Diagnostic preparation had host-side/runtime errors before FPGA loading (finalized
hash reused, insufficient contiguous RAM, unsupported optional gc display). These
were resolved without automatic hardware-command replay. Method-wise RAM loading
passed all three existing Unix MicroPython driver test groups and completed on the
RP2040. After restoration, an initial hash check used the filesystem-relative
`rp2.Flash()` view rather than full Flash; its mismatch was an invalid comparison,
not evidence of firmware change. The corrected full-XIP comparison above passed.
Keep both logs for audit; do not silently replace a failed result with a PASS.

Private local evidence: `build/hardware-eval-097/` contains SRAM/reprogram logs,
startup/restored captures, `control-stage4/010-init`, `011-identity`, `012-scratch`,
`014-full-flash-verify`, and `restore-soft-reset.log`. The private full-Flash images
must not be included in public evidence bundles because they can contain user data.

Disposition: exact bitstream remains an evaluation-only timing-exception artifact;
it is not accepted for functional operation or Release. Any future PSRAM diagnosis
requires a separately scoped action. Timing exception resolution and full hardware
acceptance remain separate Release prerequisites.

Offline follow-up: [PSRAM mismatch investigation and prepared diagnostics](psram-investigation.md).
This follow-up does not authorize a new device write or alter this failed evaluation.
