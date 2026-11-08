# Queue8 STA placement experiments

These profiles apply only to the frozen QSPI Queue8 mapped design in
`frozen-inputs.json`. They are not part of the board's default constraints.
The device is GW1NR-LV9QN88PC6/I5; the reference tool is Gowin
V1.9.12.04 (89079).

From the repository root in PowerShell:

```powershell
./tools/reroute-fb-netlist.ps1 -OutputBuild build/<unique-run> -ExtraCst diagnostics/queue8-sta/control-mid.cst
./tools/check-fb-timing.ps1 -BuildDir build/<unique-run>
```

The helper defaults to place=4, route=2, route_maxfan=23 and no resource
replication. It copies the reference mapped netlist and base pin constraints,
uses the unchanged board SDC, and runs P&R only. `-SourceBuild` may select a
fresh equivalent build: the mapped Verilog must match after removing only
lines beginning with `//`; the base CST and SDC must match byte for byte.
Output directories cannot be reused. Inputs and the source bitstream are
checked again after P&R. `plan.json`, `result.json`, native reports and any
extra placement constraints are retained with the output.

If the reference build directory is unavailable, first rebuild the baseline
using the current restored RTL, then use that directory as `-SourceBuild`:

```powershell
./tools/eval-fb-command-queue.ps1 -Depths 8 -ReplicatePacketFirst -OptimizationGoal auto -PlaceOption 4 -RouteOption 2 -OutputBase build/<new-reference>
./tools/reroute-fb-netlist.ps1 -SourceBuild build/<new-reference>/qspi-depth-8 -OutputBuild build/<unique-run> -ExtraCst diagnostics/queue8-sta/control-mid.cst
```

The equivalence hash check remains mandatory for this route; a changed
mapping requires a new investigation rather than editing the frozen hashes.

`control-mid` places the high-fanout memory control LUT at R8C15. The
`left`/`right` profiles bracket it at R8C14/R8C16. `cursor-a`/`cursor-b`
add adjacent cursor mailbox receiver placements based on the remaining
critical path of `control-mid`. The center/near profiles are other recorded
experiments, not recommended production settings.

The numeric gate requires Setup >= +0.100 ns, no Setup/Hold violations and
no negative Recovery/Removal slack. A successful tool exit or a fresh
bitstream alone does not meet that gate. New bitstreams are not hardware
validated. This workflow performs no FPGA SRAM/Flash or RP2040 programming.

See [the investigation report](../../docs/gpu-queue-sta.md) for results and
the limits of the existing CDC/external PSRAM IO constraints.
