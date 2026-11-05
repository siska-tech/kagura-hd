> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Baseline QSPI local physical-placement investigation

Final result: REJECTED after exactly one trial. Full routing and zero setup/hold
violations, but worst setup +0.060 ns < +0.100 ns. The active constraint was removed.
Baseline artifacts remain unchanged. No RTL or hardware changes were retained.

2026-11-04. One authorized constraint trial maximum; no RTL, ABI, SDC boundary,
quality-gate or default-build changes. Baseline commit:
`1d46c6db71eb48e486a8e038d41e5a44342fe699`.

## Read-only findings

| Property | held_palette_75 | palette_75 |
|---|---|---|
| Baseline site | R8C22[1][B] | R6C26[1][A] |
| Primitive | DFFRE | DFFRE |
| Clock | system_clk / system54, 54 MHz | pixel / pixel74, 74.25 MHz |
| CE | n8_7 | n3059_3 |
| Synchronous active-high reset | n2364_5 | pixel_reset_6 |
| Q data fanout | 1: palette_75.D | 1: color_3_s7.I1 |

The clocks, enables and resets differ, so these two endpoint FFs cannot share the
two A/B FF positions in one CLS. UG288-1.1.1E section 3.4 (printed pp.26–27)
requires compatible FF types and identical shared input controls. Its section 2.1
also permits the register D input from the configurable routing unit independently
of the LUT. Sections [0..2] have FFs; section [3] has LUTs only on this architecture.
A geometrically adjacent location is not sufficient evidence of a legal FF site.

Baseline timing: launch PLL clock latency 4.730 ns, launch clock route 2.642 ns,
clock-to-Q 0.458 ns, data route 4.283 ns; no intermediate combinational-cell delay.
Arrival 12.113 ns; required 12.210 ns; slack +0.097 ns. Capture clock route is
2.640 ns, uncertainty 0.030 ns, setup requirement 0.400 ns. Under the unchanged
clock quantities, meeting +0.100 ns needs data routing <=4.280 ns. Grid distance
is not a routing-delay prediction. The existing CDC max-delay boundary is 10 ns;
its cross-domain hold path is excepted by the original SDC. Global hold results
must still have zero violated endpoints; no exception was added or changed.

Netlist-level control loads in this scanout module are 197 sinks on n8_7 and 195
on n3059_3; these are module-local counts, not whole-design fanout. The global report
lists system_clk fanout 3976, pixel 1431 and n2364_5 2382. The critical DATA net itself
has fanout one, so replicating a high-fanout data driver is not indicated.

## Congestion and observation limits

The baseline uses 4208/4320 CLS, 5346 total FF, 19 BSRAM and 1 DSP. This is global
CLS pressure; it is not a measurement of the endpoint region. The saved timing report
contains only the ten highest route-congestion grids:
R23C19 0.944; R11C11/R9C15 0.931; R11C12/R22C9/R13C20/R23C15/R25C9 0.917;
R11C9/R20C6 0.903. Endpoint/candidate grids are absent from that top-ten list.
Their exact local congestion, route-track usage and switching detours cannot be
reconstructed from this truncated report. Do not label them uncongested.

Standard FloorPlanner was launched with the computer-use skill after app approval.
The original build was copied to build/physical-inspection/baseline-view before GUI
loading. Standalone File/New loaded the correct synthesized netlist and device,
but showed an unplaced device view. It did not expose the complete placed-design map.
The guide says back-annotation requires launching FloorPlanner from a completed IDE
project. A metadata-only project wrapper was created in the inspection copy (no run
command), but launching Standard IDE for that view hit an app-approval timeout.
No empty site, full local occupancy map or detailed routed-track display was inferred
from the unplaced GUI. No placement was edited or saved through the GUI.

## One legal substitution candidate

STA also identifies held_palette_147 at R6C23[1][A] and its receiver palette_147 at
R9C29[2][A]. held_palette_147 is DFFRE with the SAME system_clk, n8_7 and n2364_5
as held_palette_75; neither FF has an overriding INIT parameter (both default to 0).
Both Q nets have a single palette receiver. The source FFs can therefore exchange
their already-occupied, known-valid FF sites without assuming any empty neighboring
site. At each site the FF type, shared Clock/CE/Reset controls, INIT and FF occupancy
remain unchanged; the existing partner's compatibility is preserved. This proves
primitive/control placement compatibility, not routing completion or timing success.

The one plan swaps only those two source FFs and fixes the two receiver FFs at their
baseline sites. No CLS/region is reserved exclusively and no additional resource is
introduced. Manhattan grid distances: bit75 6 -> 3; bit147 9 -> 8. Changes to input
and output data routes still need complete global STA and full routing checks.

```text
INS_LOC "core/display/held_palette_75_s0" R6C23[1][A];
INS_LOC "core/display/held_palette_147_s0" R8C22[1][B];
INS_LOC "core/display/palette_75_s0" R6C26[1][A];
INS_LOC "core/display/palette_147_s0" R9C29[2][A];
```

Attempted file (now removed): boards/tang-nano-9k/experiments/palette75-swap.cst.
This file is not imported by the default build. The one-shot local Tcl driver adds
it to the normal combined CST after the existing fragments, retaining the original
manifest, SDC, synthesis options, place 1 / route 2 and Standard V1.9.12.04 executable.
Official build scripts were not changed for this experiment. The result directory is
build/kagura-fb-qspi-local-swap-01; the baseline directory is not overwritten.

Legality/source evidence: build/physical-inspection/swap-legality-proof.json and
netlist-and-location-analysis.json. The proof checks exact baseline STA sites and
netlist control equality before starting the trial. SHA-256 of the standalone CST:
a16ae50c1ea4c1bd738c029644d53793506d44e51ef985a0102fd884e0d4dda7.

## Acceptance and stop rule

Trial count: 1 executed, 0 accepted, no retry performed.
Require full routing, no tool errors, setup >= +0.100 ns, zero setup/hold violated
endpoints and no negative analyses, then verify actual constrained sites and matching
baseline synthesized logic. The original check-fb-timing.ps1 is used unchanged.
On any failure, remove the active experimental CST, retain its text as inactive
trial evidence, record the cause and stop. No alternate placement or RTL region
will be tried. No FPGA/RP2040 programming or Flash write is part of this investigation.


## One-trial result and cause

| Metric | Baseline | Local swap 01 |
|---|---:|---:|
| Logic | 7713 | 7712 |
| Total FF | 5346 | 5346 |
| CLS | 4208 | 4215 |
| BSRAM | 19 | 19 |
| DSP | 1 | 1 |
| Worst Setup ns | +0.097 | +0.060 |
| Worst Hold ns | +0.527 | +0.527 |
| Setup / Hold violated endpoints | 0 / 0 | 0 / 0 |
| Full routing | completed | completed |
| Setup >= +0.100 ns | FAIL | FAIL |

Gowin completed placement, routing and bitstream generation without a physical-constraint
error. The unchanged numeric checker rejected the trial, and the one-shot failure handler
removed the active CST. Its exact contents remain only as inactive evidence in
build/kagura-fb-qspi-local-swap-01/attempted-constraint.txt and in the text above.
The combined CST in that rejected trial directory is historical build evidence, not an
active default-build input. No second location or another RTL region was attempted.

The new limiting path is held_palette_38 at R25C10[2][B] -> palette_38 at R25C22[2][A].
It is another one-fanout system54 -> pixel74 mailbox path: clock-to-Q 0.458 ns plus
routing 4.320 ns, no intermediate logic. Arrival 12.150 ns and required 12.210 ns give
+0.060 ns, 40 ps below the quality threshold. Clock latency/skew terms remain as in
the baseline. Local pinning did not freeze the placement/packing of the rest of the design;
the critical endpoint migrated and CLS increased by seven. A location-distance improvement
for one pair was insufficient to establish global timing closure.

Bit75 and bit147 paths are not present in the trial's limited top-25 timing report.
Their individual post-trial slack, route delay and actual placement were not independently
exported; do not infer a numeric improvement from their omission or from the requested CST.
No additional timing/placement run was made to obtain them after rejection.
The design was physically routable with the submitted constraints, but was not adoptable.

Normalized synthesized netlists are identical, replacing ONLY the generation-date and
file0 generated-config path comment lines. Both hashes:
5aec16935c58a3081440365d7cd230a7c3c867f3d870de37d117694abfb6dcd7.
Thus the different P&R Logic/CLS counts do not represent a source RTL change. The P&R
report counts one fewer ALU (820 versus 821), with unchanged LUT and FF counts.
The existing baseline 26 FB / 22 shared Verilator PASS results remain applicable; they
were not rerun for this unchanged-RTL physical trial.

Rejected bitstream SHA-256:
ebe5ecc919929b4ef0434cd6a4c607a9463a2419857d93311cbad78768a49a1a.
It is not a release candidate or an SRAM-programming candidate.

Evidence: build/physical-inspection/final-result.json,
local-trial-netlist-comparison.json, swap-legality-proof.json and the one trial directory.
Baseline FS, DB, synthesis netlist, P&R report and STA report hashes match their pre-trial
snapshot. Git diff confirms no changes to RTL, original board constraints, SDC or gate scripts.
The experimental source CST is absent. Work stopped after this failed one-shot trial.
