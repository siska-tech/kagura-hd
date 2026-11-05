> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Standard QSPI timing improvement — 2026-11-04

Final status: BLOCKED. No trial passed the unchanged +0.100 ns gate. Best result remains
the baseline +0.097 ns. All experimental RTL was rejected and restored; no RTL changes
remain. SRAM programming and all KAGURA-HD hardware tests were not performed.

Source baseline: `1d46c6db71eb48e486a8e038d41e5a44342fe699`.
Gowin Standard V1.9.12.04, GW1NR-LV9QN88PC6/I5.
Quality gate remains setup >= 0.100 ns, zero setup/hold violated endpoints and no
negative analyses. RTL, ABI 1.2, source manifest and SDC are unchanged.

## First-run limiting path

From `core/display/held_palette_75_s0/Q` at R8C22[1][B]
to `core/display/palette_75_s0/D` at R6C26[1][A], system54 -> pixel74.
The existing SDC applies a 10.000 ns max delay to this bundled-data mailbox CDC path.

| Component | Delay ns |
|---|---:|
| Launch PLL clock latency | 4.730 |
| Launch clock routing | 2.642 |
| Launch FF clock-to-Q | 0.458 |
| Data routing | 4.283 |
| Intermediate combinational cell delay | 0.000 |
| Capture clock routing | 2.640 |
| Clock uncertainty | 0.030 |
| Setup requirement | 0.400 |

Data arrival = 4.730 + 2.642 + 0.458 + 4.283 = 12.113 ns.
Data required = 10.000 + 2.640 - 0.030 - 0.400 = 12.210 ns.
Slack = 0.097 ns. Of the 4.741 ns data-path delay, routing is 90.333% and
clock-to-Q is 9.667%. The report says logic level 1; there is no intermediate LUT
on the reported path. Source inspection confirms held_palette is captured on the
system clock, held through acknowledgement and copied into palette at pixel VBlank.
The finding supports trying placement/routing first; it does not justify weakening CDC constraints.

## Bounded P&R experiments

The installed SUG1220-2.1E, pages 36–37 (printed numbering), defines placement
0..4: 0 speed/default, 1 routability, 2 timing, 3/4 improved-placement attempts;
routing 0..2: 0 default, 1 better result with slower compile, 2 faster routing.

Trial 1 uses placement 2 / routing 1. If it fails, consider placement 3 / routing 1,
then reassess congestion before the third and final trial, stopping as soon as a trial passes. This is at most
three new full builds before reassessing; there is no unbounded seed search.
A parser/tool error stops the sequence for diagnosis rather than consuming retries.

The build entry points now accept PlaceOption/RouteOption (Tcl positional arguments).
Original defaults 1/2 are preserved. Non-default outputs get a -pN-rN suffix,
so the original failed build and its reports remain intact. No timing gate changed.

| Trial | Place / route | Logic | FF total | CLS | BSRAM | Setup ns | Hold ns | Gate |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Baseline | 1 / 2 | 7713 | 5346 | 4208 | 19 | 0.097 | 0.527 | FAIL |
| Trial 1 | 2 / 1 | 7713 | 5346 | 4208 | 19 | N/A | N/A | FAIL: 166 unrouted nets |
| Trial 2 | 3 / 1 | 7713 | 5346 | 4201 | 19 | N/A | N/A | FAIL: 82 unrouted nets |
| Trial 3 | 1 / 0 | 7713 | 5346 | 4208 | 19 | -0.475 | 0.527 | FAIL: 1 setup endpoint |
| Palette 192-bit stage (rejected) | 1 / 2 | 7712 | 5538 | 4201 | 19 | N/A | N/A | FAIL: 237 unrouted nets |
| Palette 12-bit stage (rejected) | 1 / 2 | 7712 | 5358 | 4215 | 19 | -0.858 | 0.407 | FAIL: 1 setup endpoint |
| Final original-RTL route trial | 1 / 1 | 7713 | 5346 | 4208 | 19 | N/A | N/A | FAIL: 166 unrouted nets |

Evidence is stored per trial under build/kagura-fb-qspi[-pN-rN]/.
FB and shared-component Verilator 5.032, seed 1, strict-version full regressions
both passed on the baseline and on each RTL experiment: FB 26/26 and shared 22/22; see build/bringup/fb-regression.log and common-regression.log.
No hardware programming is allowed until the numeric gate is passed and actual
recovery/host ownership is established. Flash programming is prohibited.


Trial 1 diagnosed failure: PR0004, 166 unrouted nets. No timing report or bitstream
exists for this trial, so slack is N/A, never zero or PASS. P&R report resource counts
remain Logic 7713, total FF 5346, CLS 4208, BSRAM 19 and DSP 1. This is a routed-design
convergence failure, not an invalid option or license/parser error. Retain all reports.
Trial 2 therefore proceeds with documented placement algorithm 3 and routing 1.

A slow MicroPython KFB1 QSPI diagnostic backend is prepared separately from RTL.
Its four pin-level oracle tests passed (six-bit address, nibble order, dummy/turnaround,
exception cleanup/no replay). This is software verification, not hardware acceptance.
No firmware image or device filesystem has been changed.


After the first unrouted-net failure, the third trial (if needed) will preserve the
baseline's routability-prioritized placement 1 and use default routing 0, rather
than another timing-focused placement. This isolates routing variation on a known-routable
placement mode and avoids spending all attempts on similar congested configurations.
No more than three new P&R builds will be run before reviewing the evidence.

Additional preparation: COM7 enumerates as USB VID_2E8A/PID_0005 (RP2040 MicroPython).
No serial session has been opened. The PC-side single-connection raw REPL helper and
RAM-only diagnostic runner are staged locally; they do not install device files or firmware.
C/Python driver regression: 15/15 plus QSPI waveform oracle 4/4. Existing Unix MicroPython
ABI driver regression: all three groups PASS. A firmware UF2 is not being generated or written.

Normalized synthesis netlists for baseline, trial 1 and trial 2 match exactly after removing
only timestamp and generated config source-directory comments. Normalized SHA-256:
0f84083743b4e0137834ba5053b3fcaa9a967370c87b735cef22af9969739822.
See build/bringup/netlist-comparison.json. This supports isolating P&R differences.



## Palette-only RTL experiment after the three P&R trials

The three P&R-only trials did not pass. Trial 3 routed, but its worst path moved to
next_row -> banks/pix_underrun (pixel74), with -0.475 ns and one setup violation.
The proposed RTL change is restricted to the 192-bit palette mailbox in
rtl/fb/kagura_fb_scanout.sv: sample the held source palette into a free-running
pixel-domain data register, then use that sampled value at the existing VBlank commit.
Page, toggle synchronizers, acknowledgement and ABI are unchanged. No new feature or SDC change.

Why this need not add a PRESENT frame/cycle: at the first pixel edge sampling a new
request, present_sync[0] is updated and the data stage samples the payload; at the
second edge present_sync[1] is updated while the consumer still sees its old value;
at the third edge the consumer can first observe the request and uses the preceding
edge's data sample. The source payload is held until acknowledgement throughout.
This is a bundled-data mailbox, not independent synchronization of every palette bit.
The extra stage gives the bounded CDC endpoint freedom from the output palette fanout,
with the following pixel-domain register-to-register path receiving its normal timing check.
The original 10 ns CDC constraint and 0.100 ns gate remain unchanged.

This experiment returns to the baseline's place 1 / route 2, outputs to
build/kagura-fb-qspi-palette-stage, and reruns both full Verilator suites.
The baseline directory was copied to build/kagura-fb-qspi-baseline before this trial;
all previous P&R directories remain intact. A local invocation initially failed to resolve
an empty PowerShell PSScriptRoot before Gowin was launched; the path was corrected to
an absolute repository path. No failed hardware operation or synthesis retry occurred.

Additional differential evidence for the palette stage: Verilator 5.032 seed 1 compared
scanout from the fixed baseline commit against the changed module on asynchronous
54 MHz / 74.25 MHz clocks. Across 10,000 pixel edges, 323 accepted requests and 322
completed requests (one pending at stop), palette/page state, completion and ready timing,
request behavior, RGB, generation and underrun remained equal. VBlank events every 31
pixel cycles and randomized request phase stress the mailbox boundary; this is an
accelerated control test, not a substitute for full-frame video regression or hardware.
Source/reference/test and build/run logs are retained under build/bringup/ with names
kagura_fb_scanout_reference.sv, tb_palette_equivalence.sv and palette-equivalence-*.log.
The all-palette-stage RTL passed all 26 existing FB and all 22 shared regressions.

The all-192-bit data-stage experiment failed P&R with PR0004: 237 unrouted nets.
Its resources were Logic 7712, FF total 5538, CLS 4201, BSRAM 19, DSP 1;
STA and bitstream were not generated. Both full regressions passed (26 FB, 22 shared),
but functional equivalence alone is insufficient for acceptance.

A second, smaller RTL experiment stages only palette color 6 (RGB444 bits 72..83,
which contain the baseline's worst bit 75), adding 12 rather than 192 FF. All other
palette words retain the original direct mailbox path. The same handshake argument
preserves simultaneous page/palette commit and PRESENT timing. This is explicitly a
Nano 9K timing/resource tradeoff, not a new color format or host feature.
The baseline place 1 / route 2 and every constraint/gate remain unchanged.
Output: build/kagura-fb-qspi-palette6-stage. Full regression and differential tests rerun.

The 12-bit experiment routed but failed STA: Logic 7712, FF total 5358, CLS 4215,
BSRAM 19, DSP 1, setup -0.858 ns, hold +0.407 ns, setup endpoints 1, hold endpoints 0.
The limiting path moved outside the palette to HDMI packet_assembler/first_s1 ->
packet_assembler/rest_rest_RAMREG_0_G[92]_s0. This is not accepted merely because
functional regressions passed. FB 26/26, shared 22/22 and the fixed-reference differential
comparison all passed. Tested RTL and patch are retained in the trial directory.

Both palette RTL experiments are rejected. The working RTL has been restored exactly to
baseline (git diff --exit-code on the scanout file passed). No RTL changes remain.
One final, explicitly bounded P&R-only trial uses baseline placement 1 plus routing 1,
which was not among the first three combinations. Unlike trials 1/2 this keeps the
known-routable placement mode. Output: build/kagura-fb-qspi-p1-r1.
If it fails, stop and report the evidence rather than expanding RTL outside the authorized
palette scope or lowering the gate. All original RTL full-regression results remain applicable.


## Final disposition and next minimum investigation

The final baseline-RTL place 1 / route 1 attempt ended with PR0004, 166 unrouted nets.
Logic 7713, FF 5346, CLS 4208, BSRAM 19, DSP 1; no STA or bitstream was generated.
No further attempts were started. No SRAM/Flash/device writes or serial sessions occurred.
No accepted bitstream or release candidate exists. The best rejected artifact remains the
original baseline at +0.097 ns, SHA-256
ed5b1fbb19f136a5d9ec1a4fbe9b5036c2a8eec4eaad2b5eda6faba4ff87692a.

The evidence demonstrates congestion and sensitivity to placement/routing, not a proven
functional defect in the palette mailbox. The two pipeline variants are not proposed for merge.
A next bounded engineering investigation would be a physical-placement review of the original
held_palette_75 / palette_75 FF pair and surrounding congestion, retaining all timing bounds.
Check legal placement sites and shared clock/control constraints before selecting a targeted
location/region constraint. Do not assume that another unmeasured constraint will pass.
Any RTL optimization outside the palette path requires a scope decision; it was not attempted.

Current source changes retained: optional P&R algorithm arguments/output separation,
software-only slow QSPI diagnostics with four pin-oracle tests, and investigation documents.
The diagnostic sources load successfully with exec into a RAM namespace on Unix MicroPython.
An earlier dynamic-module constructor test failed before any device connection; the direct
namespace method avoids that unsupported operation. Its success is not a hardware PASS.

Local evidence archive: build/bringup/standard-timing-investigation.zip
SHA-256: 7744e47ee7a9654e5ec1513d7502e9d079d4622126262e3c1b47e09612de03af
This is an investigation archive, excludes .fs files, and is not a Release candidate.


A separately authorized single local-placement investigation followed these experiments.
See [physical-placement.md](physical-placement.md): identical-control source FFs 75/147
were exchanged at known baseline sites in one separate CST. It routed, but worst setup
was +0.060 ns on palette bit38; the constraint was rejected and removed. RTL and baseline
artifacts remain unchanged, and no further attempt or hardware programming was performed.
