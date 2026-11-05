> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Kagura-FB implementation status

> 設計・実装・診断構成の開発記録です。過去の製品名・資源値・ビルド構成が含まれます。現行 KAGURA-HD の仕様と最新の検証値は [README](../README.md) を参照してください。

2026-11-03. Base commit f562b2ec84605860fdb9f701f5b2e197b5ed4432.
Kagura-FB uses its own board top, build and CI. Hardware verification remains pending.

## Opaque BLIT and ABI 1.2 implementation, 2026-11-04

Opaque COPY_RECT is implemented before glyph rendering and the public audio
API. See the [BLIT specification](kagura-fb-blit.md) and [host API](kagura-fb-host-api.md).
Opcode 6, ABI minor 2 and capability bit6 (full capability value 0x7f) cover even
source/destination X and width, equal word phase (`sx % 8 == dx % 8`), page 0/1
and overlap-safe copying. Vertical scrolling, page-to-page copies and horizontal
moves in multiples of eight pixels are supported. Other alignment/transparency
is rejected, with no memory request. The C/Python `copy_rect` APIs validate
strict bounds without clipping, test capability and never automatically retry
an uncertain submission. Raw submit/wait remains available for asynchronous use.

The existing FILL walker shares row traversal and mask generation with COPY.
Reverse chunk planning, initial Y products and signed source/destination word
delta are staged. The command layer validates full-width bounds and emptiness
before invoking the trusted nonempty engine. Normal standalone FILL validation
is preserved. Request valid and command mode are registered to reduce decode
paths. A pixel-local line-tag capture isolates the held SYS mailbox payload
from the wide pixel-domain tag comparison; toggle/ack ownership is unchanged.

Each COPY source response is saved through the existing READ-result path into
the upload window before the masked destination write. Scanout/PCM arbitration
continues between every transaction. The controller response can be replaced
by another client's read without corrupting the saved source. There is no new
512-bit copy scratch register or read/write-pair arbitration lock.

To reduce fabric FFs/routing, the upload window is now sixteen explicit Gowin
SP blocks, each storing a 32-bit lane at word 0. SP's native byte enables preserve
neighbouring CPU-upload bytes; bulk READ/COPY capture writes all lanes. The
output holds on write and updates at the next read edge. COPY admission leaves
that edge before the destination write; normal READ completion is deferred
until the output is ready. A CPU byte-write recovery edge also prevents an
immediate read from seeing stale bytes. Small inferred arrays were converted
to fabric by this tool, hence the explicit primitive and separate Verilator
model. The installed Gowin SP model passes the same register-window test via
`bash tools/test-fb-upload-gowin.sh`; no vendor simulation source is committed.

Startup now clears both framebuffer pages to black and the two 64-byte PCM
loops to zero. It uses the reset-cleared upload window, removing the separate
512-bit boot-data merge/pattern generator. The six diagnostic synth voices,
two PCM engines, HDMI audio and host/cursor functionality remain present.
Variable image/PCM patterns are independently checked in simulation.

Validation added to the existing regression:

- `tb_fb_blit`: 1,150 pixel-oracle cases over both complete pages, all byte
  phases, forward/reverse chunks, four-way/diagonal overlaps, full pages,
  invalid ranges/alignment, empty/self copies, memory failures, in-flight
  reset and recovery. Other clients interleave between source read and write.
- `tb_fb_register_window`: immediate masked byte writes/readback, six READ
  completion sequences, eighteen intermediate COPY captures and warm reset.
  Both the behavioral and installed vendor SP models pass.
- SPI/QSPI host integration uses the actual six-bit CSR protocol and window
  to copy a full page while scanout, PSG6, PCM2 and cursor commits run.
  It compares the complete destination page and ordered PCM data, and checks
  the 1,920-system-cycle line deadline. The source/display page stays stable.
- Portable C/Python: 15 tests pass, including descriptor equivalence,
  overlaps, cross-page copies, strict range/alignment validation, missing
  capability, memory errors and uncertain-submit handling. Actual MicroPython
  1.26 Unix smoke tests cover the new API too.
- The retained analytic model passes 884 pixel-oracle cases/eight rejections;
  memory-service test measures 96 intervals over 1..16 words. Those transaction-
  only estimates are separate from the implemented engine's measured latency.

Measured simulation latency at 54 MHz: isolated full-page COPY takes 210,609
system cycles (3.900 ms). Host/core integration takes 252,756 cycles SPI and
252,696 cycles QSPI (about 4.681/4.680 ms), excluding command transport and
PRESENT/vblank waiting. During that integration, 111/106 display lines are
checked, with worst 595/594 system cycles, and 235/228 ordered stereo PCM
boundaries. These are simulation workload results, not physical-board rates
or RP2040/RP2350 CPU measurements.

Cursor CSR now captures/classifies a request before execution (two system
edges to the endpoint response). COMMIT's value==1 flag is predecoded in that
capture. The palette is snapshotted in SYS together with the held cursor
position, removing the bank-selection mux from the pixel CDC path. Its bank
ownership/coalescing/API semantics are unchanged. TMDS popcounts use explicit
balanced pairs/quads, with the same four-stage latency and upstream symbols.

The fractional audio clock has equivalent combinational/registered-zero tick
representations. The board selects combinational ticks for SPI and registered
ticks for QSPI to meet packing/timing constraints. Both produce exactly the
same 48 kHz decisions, including reset phase and short intervals; 720,000 tick
decisions cover both representations, integer ratios and the fallback. Clock
frequencies remain 54/74.25/371.25 MHz. P&R remains place 1/route 2 for both.

All 26 RTL regression tests pass, as do 15 portable C/Python tests, actual
MicroPython 1.26 smoke tests and the installed vendor SP test. Dependency
verification matches all 12 pinned files and git diff --check passes.

| Current build | SPI | QSPI |
|---|---:|---:|
| Logic | 7,815/8,640 | 7,795/8,640 |
| Logic FF | 5,221/6,480 | 5,222/6,480 |
| CLS | 4,245/4,320 | 4,223/4,320 |
| BSRAM | 19/26 | 19/26 |
| DSP | 1/10 | 1/10 |
| Worst setup | +1.122 ns | +0.660 ns |
| Worst hold | +0.558 ns | +0.552 ns |
| Setup / hold violated endpoints | 0 / 0 | 0 / 0 |

The numeric >=+0.10 ns setup gate passes. Recovery/removal are positive too
(SPI +0.760/+1.135 ns, QSPI +5.396/+0.872 ns). Relative to the cursor baseline,
SPI adds 354 Logic and 81 CLS, removes 378 FF, and uses 16 more BSRAMs; DSP and
resolution stay unchanged. CLS packing remains tight, so arbitrary alignment,
transparent copies and glyphs need a separate resource/timing evaluation.

Bitstream SHA256:

- `build/kagura-fb/impl/pnr/kagura_fb.fs`:
  `beb015d6a7a4da77312b77a69f1a122b4614cfcb084cef579fed58c6429148f3`
- `build/kagura-fb-qspi/impl/pnr/kagura_fb.fs`:
  `26ab8591cfb61d7c934d338296a9f3d76b7b6d5a4fed7f9b1392865ee70739f6`

Timing-report SHA256 (also bound in each timing-status.json):

- SPI: `ec0e163c0fb82c297ba44e68c3e32552847e9b666097a74af236cc1007133602`
- QSPI: `72b21fe83e26354a2704205a95b044a38260b885109163fa8049cd5cbb5f47cc`

Logs: `build/fb-blit-final-regression.log`, `build/fb-blit-drivers.log`,
`build/fb-blit-micropython.log`, `build/fb-blit-vendor-test.log`,
`build/fb-blit-spi-build.log`, `build/fb-blit-qspi-build.log`.
The cursor-era section below is historical; current build outputs overwrite
its paths.
External PSRAM IO/phase, board loading, host physical transport and CPU/p95
latency remain unverified; `release_ready` remains false.

## Hardware cursor and ABI 1.1 milestone, 2026-11-04

The current build includes a 32x32 logical 2bpp cursor with transparent index
0 and three private RGB444 colors, 2x nearest-neighbour output, per-bank
hotspot, signed positions, edge clipping and vblank-atomic updates. The
256-byte shape has two banks in one additional BSRAM. It never writes PSRAM
or the framebuffer. Active/pending/latest banks reject image/metadata writes.
A toggle/ack mailbox plus one latest-value slot coalesces motion independently
of drawing BUSY. Applied generation is a wrapping 16-bit count of actual
updates. Cursor completion/error IRQ acknowledgement is separate from GPU IRQ.

See [cursor specification and examples](kagura-fb-cursor.md) and
[host ABI/API](kagura-fb-host-api.md). ABI minor is 1 and capability bit5
advertises the cursor. The FB transport uses six address bits (CSR32..63);
the shared SPI adapter retains its legacy five-bit default. A registered
one-request dispatcher isolates the two CSR banks. Position, image, colors
and hotspot registers are write-only; only cursor status/generation/error
read back, reducing the mux cost. Command-staging reads and data-window
accesses take two endpoint edges, with additional dispatcher latency.

C and MicroPython provide cursor_shape/move/status/wait. Move only submits;
wait acknowledges the applied update. Raw GPU submit/wait APIs also separate
command submission from completion so an application can update the cursor
while a drawing command is outstanding, from one serialized caller. The
existing synchronous drawing methods keep their behavior. The C device
structure did not grow. Neither uncertain GPU nor cursor submissions retry
automatically. Old firmware without the cursor capability is rejected only
when a cursor API is requested.

Resource/timing changes retain the clock rates and numeric setup >=0.10 ns
gate. Scanout uses five-pixel lookahead, separately registered pixel index
and one-hot color selection, and takes line ownership one pixel earlier;
its externally visible RGB positions are unchanged. The cursor has its own
four-pixel lookup pipeline and replaces the old HDMI input register. Bounds
checks use the final 32-word region instead of a full 21-bit end-address
carry chain; the command layer validates fill bounds before invoking the
trusted-input fill engine (simulation asserts that contract). Read-result
capture is registered and occurs on command completion, before the arbiter
can replace the controller response. GPU writes invalidate the PCM word
cache on successful completion; PREPARE still flushes immediately. Live
PCM buffer modification still requires proper prefetch reconfiguration.

The boot payload is cleared before host enable. Locked upload/command
registers remain zero throughout boot, allowing mutually exclusive boot and
host write payloads to be OR-combined; simulation asserts non-overlap. The
board-top test also injects a rejected upload before READY and checks that
neither initialized FB page nor PCM data is contaminated. This diagnostic
initialization is not the excluded W65C02S/ROM boot loader.

Audio keeps all six synthesized voices plus two PCM voices. The FIFO stores
one-ahead Gray read position and aligns conservative occupancy with its empty
flag; its memory read latency stays one edge. Audio delivery prepares its
existing output slot independently of packetizer ready and holds valid/data
until accepted. The 525/1 clock uses a short integer counter; 12375/8 uses
seven 1547-clock periods followed by one 1546-clock period, exactly matching
the original phase accumulator. Other ratios retain a generic implementation.
Noise zero detection and TMDS balance classification are registered without
altering sample/symbol sequences.

Validation on Verilator 5.032, seed 1:

- All 23 FB regression tests pass. Cursor reference compares 7,425,407 pixels,
  including transparency, colors, hotspot, clipping, bank switch, skipped
  intermediate positions, IRQ clear, pending-reset cancellation and zero
  same-address RAM collisions. SPI/QSPI tests submit motion during a busy
  full-page fill, check unchanged command staging and framebuffer contents,
  and observe cursor color on the HDMI RGB input.
- Existing checks still compare 1,843,200 raw RGB and TMDS pixels, 2,388 decoded
  stereo samples, 49 ACR and 4 AVI packets with actual 6+2 audio and host writes.
- 480,000 audio tick decisions match an independent modulus reference for
  525/1, 12375/8, 7/4 and generic 5/3, including mid-phase reset. FIFO checks
  1,024 ordered words, wrap/reset and occupancy/empty consistency.
- The inherited synthesizer reference matches 34,774 stereo samples, full
  32,767-state LFSR period, 0x8000-period borrow, disable/re-enable, resets,
  snapshots, pan and saturation. Command bounds exhaust 1,222 read/write
  cases, in addition to the controller's 1,216 end-of-die cases.
- All 13 C/Python model tests and the actual MicroPython v1.26 Unix smoke pass,
  including asynchronous GPU/cursor interleaving, no framebuffer mutation,
  generation wrap, timeout, old-capability rejection and uncertain submission.
- Separate compatibility runs pass both legacy SPI/QSPI bus tests (5-bit mode)
  and VIC1/VIC4 HDMI tests (1,024 ordered stereo pairs after partial-group reset).

Gowin Education 1.9.11.03, place option 1 / route option 2:

| Cursor-enabled configuration | Logic / 8640 | Logic FF / 6480 | CLS / 4320 | BSRAM / 26 | DSP / 10 | Setup | Hold |
|---|---:|---:|---:|---:|---:|---:|---:|
| SPI | 7461 | 5599 | 4164 | 3 | 1 | +0.170 ns | +0.552 ns |
| QSPI | 7440 | 5599 | 4126 | 3 | 1 | +0.274 ns | +0.405 ns |

Current bitstreams (each build invocation emits one selected transport):

- build/kagura-fb/impl/pnr/kagura_fb.fs: SHA256 `76e6585c8e6a91288a97d513f4682d9c10a9a6b1de315f78c97d8399ae896595`
- build/kagura-fb-qspi/impl/pnr/kagura_fb.fs: SHA256 `acbd9d18b9708255f191a51c1f92de1e660cc8e64e01b02e17c2b53ba47a8f65`

Numeric STA passes for both configurations. SPI has only 0.170 ns setup
margin and CLS occupancy is 96-97%, so later audio-control/BLIT/glyph features
need resource reduction and renewed timing assessment. The image retains
fixed diagnostic audio settings; public audio configuration and BLIT/glyph
commands remain pending. Physical board operation, PSRAM external timing,
final CDC signoff and RP2040/RP2350 firmware performance are unverified;
release_ready remains false. No device programming was attempted in this phase.

The following milestones are historical. Their build paths are reused; use
the current table and hashes above for ABI 1.1 artifacts.

## Host/GPU and driver milestone, 2026-11-03

The dedicated board top now exposes SPI (default) or QSPI (build-time choice)
after its diagnostic boot. Both use ABI 1.0: one tagged command outstanding,
locked command/data staging, status/credit/error/completion IRQ, and a 64-byte
data window. Commands are FENCE, FILL, PALETTE, PRESENT, WRITE and READ.
The protocol and software usage are specified in [host API](kagura-fb-host-api.md).
The legacy Kagura-9 register map is not compatible with this endpoint.

The rectangle engine computes bounded burst lengths in word units, uses
up to 16 words per burst, byte masks, and one-word
read/modify/write only for odd nibble edges. Full-page fill is 95,762 system
clocks (1.773 ms at 54 MHz) in the isolated engine/controller simulation;
this excludes scanout/PCM arbitration and host overhead, and is not a measured
board throughput. Page/palette presentation completes at vblank. Arbitrary
host memory transfers cover a 4 MiB die; public byte APIs preserve neighbors
with aligned transactions and byte masks.

The TMDS encoder precomputes positive/negative disparity deltas in stage 2
without changing symbol latency; its output is compared against the pinned
upstream implementation in the FB regression.

The controller uses a separate long initialization counter and 7-bit active
transfer counter with registered terminal counts for the fixed LAT14/RDL6
configuration. CSR data-window reads and writes use two edges to split their wide mux
and write enables;
other register responses use one edge. Pixel-domain error levels are
synchronized before host status decoding.

The controller's wide read alignment mux was replaced by 32 one-hot 16-bit
receive slots. A registered bounds check separates request selection from
transfer state. Read-only clients share the unused host write fields to eliminate a wide
arbitration mux. PCM requests register their address before cache lookup.
The arbiter relies on stable relevant fields through ready, and the
register endpoint holds the command/payload until completion. READ captures
its 64-byte result on the memory-response edge before another client can
replace the shared result. These contracts avoid duplicate 512-bit buffers.
Scanout now registers the color index between the line RAM and palette mux,
with four-pixel lookahead preserving externally visible pixel positions.

Eighteen Verilator tests include both SPI/QSPI pin-level command paths with
active video, six synthesized voices and two looping PCM voices. They check
busy-submit rejection, tags/errors, full fills, odd pixel edges, masked writes,
64-byte readback during scanout, palette/vblank present and resulting RGB.
A separate 1,216-case test exhausts lengths 0..18 over the final 64 word
addresses; invalid requests must not assert memory CS. The saturated
scanout/PCM/GPU line-fetch test takes at most 529 system clocks per line
(9.80 us), below the 1,920-clock test limit. The full regression
continues to decode HDMI pixels and audio independently. In addition to the
17 core/host checks, a board-top test verifies all 230,400 initialized FB
bytes, both PCM loops, host READY/SPI identity and a displayed pixel. The real
boot sequencer is used, with platform clocks, physical PHY and LVDS stubbed;
this does not validate DDR pins. AUDIO_APPLY starts PCM at the following
sample boundary, so active PCM is checked after that boundary. Diagnostic
payload selection/color is registered in LOAD before each SEND transaction.

The portable C11 driver compiles with -Wall -Wextra -Werror. Nine shared
C/Python tests use an independent register/memory model, including clipping,
tag wrap, unaligned and end-of-memory transfers, timeouts, invalid identity,
transport/device errors and no automatic retry of an uncertain submission.
Actual MicroPython v1.26.0 Unix also passes API and SPI-framing smoke tests.
CI runs the RTL and driver tests with pinned Verilator and MicroPython.
RP2040/RP2350 firmware cross-builds, physical transport and performance have
not been verified. The MicroPython helper uses 1 MHz SoftSPI on existing pins;
QSPI requires a separate transport backend.

At the ABI 1.0 milestone, the boot initialized fixed diagnostic synth/PCM parameters.
Audio configuration commands, waveform upload ownership, BLIT, glyph drawing,
and hardware cursor were pending (cursor is implemented in ABI 1.1 above). Numeric STA results below must be read with
their configuration/date; the prior AV-only result is not the host build.
CDC constraints remain draft and physical PSRAM timing remains unverified.

### Host-enabled board implementation results

Gowin Education 1.9.11.03, place option 1 / route option 2. Both configurations
pass the numeric gate (setup >=0.10 ns and no setup/hold violations):

| Configuration | Logic / 8640 | Logic FF / 6480 | CLS / 4320 | BSRAM / 26 | DSP / 10 | Setup | Hold |
|---|---:|---:|---:|---:|---:|---:|---:|
| SPI host + video + diagnostic 6+2 audio | 7042 | 5176 | 4026 | 2 | 1 | +0.107 ns | +0.552 ns |
| QSPI host + video + diagnostic 6+2 audio | 7021 | 5176 | 4031 | 2 | 1 | +1.109 ns | +0.558 ns |

Bitstreams and SHA256:

- build/kagura-fb/impl/pnr/kagura_fb.fs: `215a30c56117905a0e9a64d2f884abb0110bb378c136b839a0df36455471f874`
- build/kagura-fb-qspi/impl/pnr/kagura_fb.fs: `2516e3c371ad508846d4584c1ea0ce4a49c444ddd04fa6203b0c47eb2b959aec`

Timing status is in each build directory's timing-status.json. SPI margin
is only 0.107 ns and CLS occupancy is 94%; cursor/BLIT extensions require
another resource/timing assessment. The numeric gate does not establish CDC
signoff, external PSRAM timing closure, or successful SRAM programming on a
physical board. release_ready remains false. W65C02S and legacy ROM boot
loading are excluded from the FB manifest; SPI/QSPI build distinction remains.

## FB video/audio integration milestone, 2026-11-03

Kagura-FB now has its own default build and CI target. The three inherited
Kagura-9 workflows are manual-only reference checks. The common RTL source
manifest is rtl/fb/sources.f. The main test command is unchanged:

    wsl -- bash tools/test-fb-verilator.sh

The external-clock kagura_fb_core connects the burst controller, arbiter,
scanout, line banks, existing PCM control/prefetch and six-voice synthesizer,
and inherited HDMI packetizer/encoder. Audio remains 48 kHz signed 16-bit
stereo, with 6 synthesized voices and 2 signed-8-bit PCM voices mixed into
that output. System and pixel reset releases are synchronized separately.

Scanout uses 640x360 packed 4bpp, 320-byte stride and two physical pixels per
logical pixel in each axis. A page and 16 RGB444 colors are captured together
at vblank. The host must wait for prior host_done before presenting; this is
a raw transaction interface, not the final command ABI. A registered RGB
stage aligns the inherited HDMI encoder's delayed video-enable signal with
its first/last active pixels. Lookahead RAM controls, row tags and boundary
pulses are registered to meet the 74.25 MHz pixel clock.

The PCM byte bridge has independent valid/ready and a one-word cache. It
flushes on PREPARE or host writes. A flush while a read is outstanding also
prevents the returning data from repopulating the cache. This case is
covered by a focused regression and fixed during this milestone.

Twelve FB tests pass with seeds 1 and 17 on Verilator 5.032, including:

- All 1,843,200 pixels across two displayed frames, 2x nearest-neighbour,
  byte/nibble order, and atomic page/palette replacement.
- The same 1,843,200 pixels decoded independently from TMDS video symbols.
- Real two-channel PCM prefetch byte order and loops checked against uploaded
  reference samples, while all 6 synth voices and continuous host writes run.
- 2,388 non-startup stereo pairs decoded from HDMI TERC4 and matched, in order,
  to the synthesizer output. Startup silence is skipped. ACR (49 packets,
  N=6144/CTS=74250), AVI (4 packets, VIC4/aspect), packet start alignment,
  PCM statuses and audio FIFO overflow/underflow are checked.
- A 6,000-system-clock display-request stall causing 3 missing logical rows.
  Those rows are black, stale tags are discarded, and normal display resumes
  with the next page/frame correct. The late-line test compares all pixels.

The physical serializer is stubbed only at the OSER10 boundary in the HDMI
simulation. DDR pins, phase margin and memory silicon are not simulated.
Existing/vendor width warnings remain visible in the build logs.

Dedicated board build:

    powershell -NoProfile -File tools/build-fb.ps1

This builds boards/tang-nano-9k/kagura_fb_top.sv via tools/build-fb.tcl and
boards/tang-nano-9k/kagura-fb.sdc. The boot sequencer initializes both FB pages
and two PCM loops, presents grayscale page 0, and starts all 8 voices. LED
bits (lit means true) are 0 PLL locks, 1 memory initialized, 2 audio FIFO error,
3 video/memory error, 4 boot/PCM error, 5 boot sequence in RUN.

Gowin Education 1.9.11.03, place option 1 / route option 2, completed synthesis,
P&R and bitstream generation. Numeric STA meets the 0.10 ns setup target:

| Diagnostic configuration | Result |
|---|---|
| Logic | 3,788 / 8,640 (44%) |
| Logic FF | 3,086 / 6,480 (48%) |
| BSRAM | 2 / 26 |
| DSP | 1 / 10 blocks |
| Worst setup / hold | +1.926 ns / +0.552 ns |
| Violated setup / hold endpoints | 0 / 0 |

The configuration contains fixed diagnostic settings and a boot sequencer.
Host transport, programmable wave RAM and drawing commands will change the
resource counts and must be rechecked. The initial CDC delay bounds are a
draft, not a complete CDC signoff or external PSRAM interface STA. Numeric
success leaves release_ready=false. No board programming was attempted in
this simulation-first milestone.

Artifacts are build/fb-core-regression.log, build/fb-verilator/*.log,
build/kagura-fb/build.log, build/kagura-fb/timing-status.json and
build/kagura-fb/impl/pnr/kagura_fb.fs. The generated FS SHA-256 is
855df914b6e1bc406c02ffac8e5eecef20d89590d0530ce347112686d1a23bca.
tools/build-fb.ps1 checks fresh output,
Gowin errors and the numeric STA threshold, and tools/check-fb-timing.ps1
labels the remaining scope explicitly.

The next implementation stage is the packed drawing-command/host interface,
C/MicroPython bindings and the independent 32x32 hardware cursor. The legacy
byte-fill module remains separately tested; it is not yet the core's host
command processor.

## Memory subsystem milestone, 2026-11-03

Hardware connection work is deferred at the user's request. Verilator 5.032
is installed in WSL. Run from the repository root with:

    wsl -- bash tools/test-fb-verilator.sh

Eight FB tests pass. The burst test also passed random seeds 1 and 17.
The full inherited Kagura-9 Verilator regression completed with 61/61 pass
(log build/fb-upstream-regression.log, summary build/verilator/summary.tsv).

| Added module | Behavior | Standalone synthesis Logic / registers |
|---|---|---|
| kagura_fb_burst_ctrl | 1..16 words per linear read/write, byte masks, initialization, bounds checking, completion after CS recovery | 878 / 1137 |
| kagura_fb_arbiter | Scanout, PCM, host/GPU sharing one controller, bounded transactions, response ownership | 1229 / 12 |
| kagura_fb_line_fetch | Five 64 B reads produce eighty ordered 32-bit inactive-bank writes | 588 / 539 |
| kagura_fb_line_banks | Tagged toggle mailbox, stale-line discard and dual-clock ownership | 78 / 40, plus 2 BSRAM |

These are standalone Gowin synthesis counts, with IO register accounting.
They are not whole-engine utilization or placed timing results. The arbiter
holds its selected source until acceptance and forwards the controller's
held read result, avoiding 1,113 redundant registers from the initial version.
The legacy single-word controller and board top are unchanged.

Verification includes the original fill/byte-port tests, fill through the
real single-word controller and independent CA-decoding memory model, 100
random masked burst write/read pairs, invalid lengths and end-of-die bounds,
reset cancellation, two competing background clients, both FB pages, and
all 720 logical rows checked against an address-dependent byte reference.
Line-control tests also cover invalid row, request backpressure, memory error,
and reset during line-bank drain. No bank should be published after an error.

With a 320-byte line requested every 2,400 system clocks and PCM read/GPU
write clients continuously saturated, the actual line-fetch path completed
within 519 clocks (9.61 us at 54 MHz), against the 1,920-clock design target.
PCM request-to-response maximum was 137 clocks (2.54 us) in this workload.
The separate burst-only contention workload measured 474 clocks per line
and 158 clocks for PCM. A standalone maximum 64-byte read took 56 clocks.
These are observed simulation maxima under fixed LAT=14, RDL=6, CS_HIGH=2,
not a proof over arbitrary controller stalls. PCM is a synthetic traffic
client here; integration with the existing audio prefetch/mixer remains.

The new tests are included in the existing Verilator CI job, with logs in
build/fb-verilator. The memory model defaults to one-word behavior for all
legacy callers and accepts longer bursts only when explicitly configured.
Shell scripts use LF on checkout. Vendored HDMI bytes are protected from
newline conversion, since source generation verifies their SHA-256 hashes.
The 12 dependency hashes, register-generation checks, design checks, and CI
change-filter tests pass.

The dual-clock bank module is separately tested with unrelated system/pixel
clock edges. It accepts only matching row/page/generation tags, acknowledges
stale publications without transferring ownership, blanks invalid lines and
records underrun. A pending publication can be cancelled by a common reset.
The existing dual-port RAM collision checker is active in this test. Its
integer-address argument produces two pre-existing width-extension warnings.
The mailbox payload stays stable until acknowledgement; physical CDC timing
constraints and metastability behavior still require board implementation.

Next milestone is connecting the fetcher and bank mailbox to the 2x scanout
and palette alignment in the existing HDMI pipeline. The controller must be
initialized and line 0 fetched before enabling active video.
Packed GPU fills, host command/API integration and hardware cursor follow.
The byte fill test path and new burst path are separately verified; they
have not yet been connected through a packed-fill adapter. Physical burst
memory behavior, HDMI/audio integration, resource/timing closure of the
complete engine, and hardware performance remain unverified.

## Initial implementation

rtl/fb/kagura_fb_fill.sv accepts one rectangle for either 640x360 page.
Even x is the high nibble. Coordinates are checked with extended sums before
any memory request. Empty rectangles within the valid origin range complete
without memory access. Rectangles crossing a boundary are rejected, rather
than clipped. The caller clips before submission.

The byte memory interface holds requests under backpressure and waits for
completion of every operation. Partial edge bytes use read/modify/write.
Addresses are relative to PSRAM die 0, with page bases 0 and 115200.
Completion means the final write response has arrived.

The future adapter must convert byte addresses to the existing controller's
word addresses and byte masks. It must emit one delayed completion for every
accepted request, including writes. The existing controller's command acceptance
alone does not satisfy this completion contract. Serialize other writers to the
destination page across read/modify/write. Display and PCM reads may interleave.

## Verification

Run powershell -File tools/test-fb.ps1 with Icarus Verilog and vvp on PATH.
The independent pixel reference compares both complete pages after every
command. Coverage includes full-screen fill, the last pixel, both nibble
parities, neighboring pixel preservation, invalid/overflowing ranges, empty
rectangles, 80 random rectangles, request stalls and delayed responses.

Icarus simulation passed. This is byte-transaction functionality verification.
Throughput, synthesis, FPGA timing, reset during an outstanding memory operation,
and board behavior have not been validated.

## Next integration steps

1. Implement the completion-aware byte adapter, then packed word/burst writes.
   Reset must coordinate adapter/controller drain before accepting new work.
2. Implement burst reads and the deadline-based display/PCM/GPU arbiter.
3. Add dual-clock line banks and the 640x360 scanout to the inherited HDMI path.
4. Expose FB capabilities, FILL and page presentation through the host command
   queue, with C/MicroPython entry points.
5. Add the independent hardware cursor and compare resource/timing costs.

## PSRAM byte adapter and board diagnostic (2026-11-03)

Implemented rtl/fb/kagura_fb_byte_port.sv. It maps bytes to 32-bit controller
lanes using write masks, gates requests until initialization, and completes a
write only after the dedicated controller goes busy and returns idle. The
dedicated-controller idle indication is required. An arbiter ready signal
cannot be substituted for it. This byte implementation establishes correctness;
packed writes and bursts are still pending.

tools/test-fb.ps1 now also checks all adapter lanes, neighboring words, read
routing and delayed completion. Both simulations passed after the changes.
Both modules passed Gowin synthesis with no width-truncation warnings.

boards/tang-nano-9k/kagura_fb_memtest_top.sv connects fill, byte adapter,
the inherited 54 MHz controller and the existing Gowin PHY. It fills page 0
with index 3, overlays x=1,y=1,width=3,height=2 with index 10, then reads and
checks every byte of page 0. LED meanings (lit means true) are 0 initialized,
1 passed, 2 mismatch, 3 finished, 5 heartbeat. The diagnostic does not drive HDMI.

Build from build/fb-memtest using tools/build-fb-memtest.tcl. Gowin Education
1.9.11.03 completed synthesis, placement, routing and bitstream generation.
The diagnostic totals 372 logic elements and 250 registers including IO.
Reported worst setup slack is +5.327 ns, hold +0.708 ns, with no violated
setup/hold endpoints. The inherited constraints do not fully cover external
PSRAM electrical timing, so these values do not establish memory correctness.

Hardware programming remains unverified. Initial JTAG attempts reported
Cable failed to open and Windows reported USB Serial Converter B problem 10.
After user reconnection the CLI omitted that error but returned no actual
device ID, and SRAM Program and Verify returned exit code 1 without a success
message. Clearing PYTHONIOENCODING did not resolve it. Subsequent cable scans
found no cable and Windows no longer listed a connected VID_0403 device.
No flash programming was requested or performed. Board LED results have not
been observed, so the diagnostic has not passed on hardware.

## WSL toolchain migration (2026-11-03)

Windows FTDI A/B returned to problem code 0 and Gowin JTAG read the real
device ID 0x1100481B. A subsequent SRAM programming operation reached 100%,
but readback remained at 1% for several minutes. The specific programmer
process was stopped during readback. This is not a verified programming result.

After reboot Ubuntu has apt openfpgaloader 0.13.1-1. usbipd-win is installed
at C:/Program Files/usbipd-win/usbipd.exe, though it is absent from this chat's
PATH. The user bound bus 2-2 (0403:6010), allowing attachment to WSL.

WSL sees an FT2232-emulating SIPEED JTAG Debugger, serial "FactoryAIOT Pro".
apt openFPGALoader failed detection at 6 MHz, 2 MHz and 1 MHz with USB read
errors and varying invalid IDs. Releasing the JTAG ftdi_sio interface and
running as root did not resolve it. Separate detach/attach commands are
required because Windows device reenumeration is asynchronous.

For comparison, upstream v1.2.0 (befbab4f646207dbaf1daf8b144dd980ad283dd5)
was built under /path/to/openFPGALoader/build. This leaves the
apt binary in place. It also returned a varying invalid ID at 1 MHz.
The dependencies libftdi1-dev, libusb-1.0-0-dev, libudev-dev, libhidapi-dev
and pkg-config were installed in WSL for this build.
A physical USB reconnect has been requested before another detection test.

The intended command, once ID detection succeeds, is:
    openFPGALoader -b tangnano9k -m /path/to/kagura-hd/build/fb-memtest/impl/pnr/kagura_fb_memtest.fs

Do not equate openFPGALoader --verify with SRAM readback verification.
Its installed help limits --verify to SPI flash. Verify the running PSRAM
diagnostic via its pass/fail output after successful SRAM configuration.

After physical reconnection and rebinding, usbipd attach failed with Device in
error state. A subsequent usbipd list showed bus 2-2 as VID:PID 0000:0002,
Unknown USB Device (Device Descriptor Request Failed), Shared (forced),
instead of 0403:6010. This is a Windows USB enumeration failure before WSL
or openFPGALoader can access JTAG. A different data cable and direct PC port
have been requested. No WSL SRAM programming was attempted because correct
ID detection has not succeeded.

On bus 5-3, pre-attach enumeration was normal (0403:6010, Shared).
usbipd attach immediately failed and the device changed to 0000:0002,
Windows problem code 43. Application log provider usbipd-win recorded
Win32Exception 31 in VBoxUsb.ClaimDeviceOnce. This repeats the attach-related
failure on another port; it does not establish a cable or FPGA fault.
The native Windows MSYS2 openFPGALoader v1.2.0 executable was checked and runs.
Its USB scan found no accessible probe while the device was in this error state.
A native Windows path has been proposed, requiring administrator unbind and
WinUSB on JTAG Interface 0 only. UART Interface 1 should retain its driver.
No driver replacement has been performed by the agent.

Native Windows testing after the user installed WinUSB on Interface 0:
WinUSB service and problem code 0 confirmed. openFPGALoader v1.2.0 detected
Gowin GW1N(R)-9C, ID 0x0100481b (the ID revision nibble differs from the
Gowin CLI report; vendor/family/model were recognized).
First SRAM attempt failed during FTDI reset. A second attempt parsed the FS
but repeatedly reported usb bulk write failed during SRAM erase/loading;
the specific programming process was stopped. A 6 MHz retry also failed
with a USB bulk write error during initialization. No successful SRAM load
or running PSRAM diagnostic has been established. Logs are in
build/fb-memtest/openfpgaloader-sram*.log. A power-cycle followed by a single
direct SRAM load has been requested to distinguish stateful debugger failure.

Fresh reconnect changed the Windows device instance from the earlier
serial-less parent USB/VID_0403&PID_6010/6&183EFD69&0&4 to the correctly
identified parent ending FACTORYAIOT_PRO. Interface 0 on this instance uses
FTDIBUS, so the fresh SRAM attempt failed at usb_open (no memory transfer).
The user has been asked to set WinUSB on the current Interface 0 and leave
it connected for a direct SRAM attempt. This is a distinct device instance,
not evidence that the previously installed WinUSB driver was removed.

After WinUSB installation on the correct FACTORYAIOT_PRO instance,
Interface 0 has service WinUSB and problem code 0. Two direct SRAM attempts
failed before transfer with ftdi_usb_reset failed. No programmer processes
remained. usbipd list still showed the current device at bus 2-4 as Shared.
Unbind was attempted but requires administrator privileges; the user was
asked to remove this remaining USB/IP sharing configuration before another
native Windows attempt. Its contribution to the reset failure is unproven.

After user unbound bus 2-4, usbipd confirmed Not shared. Native SRAM load
still failed at ftdi_usb_reset. LIBUSB_DEBUG=4 provided the specific failure:
WinUSB successfully claimed interface 0 and assigned endpoints 0x81/0x02;
the subsequent control transfer completed with Windows error 31 and endpoint
STALL. Therefore this attempt failed before configuration data transfer.
Log: build/fb-memtest/openfpgaloader-usb-debug.log.
A final fresh-power direct load with the correct WinUSB instance and no
USB/IP binding has been requested. Firmware incompatibility remains a
hypothesis; no debugger firmware or flash has been modified.

User proposed measuring the original programmer after moving to USB 2.0.
With Interface 0 still WinUSB, Gowin --cable-index 5 successfully read
0x1100481B in 5.12 s (driver selection requires cable-index; the cable string
alone fell back to FT2CH). SRAM Program and Verify immediately failed with
Error found, exit 254, elapsed 0.2273 s. This is not a throughput measurement.
The user was asked to restore Interface 0 to the existing FTDI driver in
Device Manager for a comparison with the original FT2CH transport on USB 2.0.
Logs: build/fb-memtest/gowin-winusb-usb2*.log.

Original FTDI comparison on USB 2.0 after user restored FTDIBUS:
The driver initially reported problem code 0, but the Gowin FT2CH backend
could not open either channel. Direct D2XX enumeration returned two devices
with flags=1, blank serial/description and ID/location=0; this is not proof
that an application held them. After user closed Zadig and reconnected,
SRAM Program and Verify failed before transfer with exit 50 (Cable failed
to open), elapsed 0.2891 s. Converter B again reported Windows problem 10,
while A reported 0. No competing programmer processes were found and USB/IP
state was Not shared. Speed cannot be measured from these failed opens.
Log: build/fb-memtest/gowin-ftdi-usb2*.log.
