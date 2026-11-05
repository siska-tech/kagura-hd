> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Dynabook bring-up and recovery

Read hardware-validation.md first. Hardware state has not been changed in this session.
This document supersedes the older Education-based bring-up instructions for this task.

Keep KAGURA-9 wiring intact. Before use, physically verify the following mapping:

| Signal | RP2040 GPIO | FPGA host.cst pin |
|---|---|---|
| IO0 | GP2 | 28 |
| IO1 | GP3 | 29 |
| IO2 | GP4 | 30 |
| IO3 | GP5 | 33 |
| SCK | GP6 | 35 |
| CS_n | GP7 | 42 |
| BUSY | GP8 | 26 |
| READY | GP9 | 27 |
| IRQ_n | GP10 | 49 |

Verify common GND, 3.3 V logic and IRQ pull-up. This table is a source mapping,
not confirmation of the physical wires. Do not drive pins until verified.

Before replacement, identify the RP2040 board, current firmware version, known-good UF2,
boot.py/main.py and filesystem contents; back up and hash them. Verify board-specific
BOOTSEL recovery instructions and availability of the exact known-good firmware.
Historical recovery assets and restore records were located; see hardware-validation.md.
Their match to the current device is pending. Firmware replacement remains blocked.

After license, STA and recovery gates pass: identify JTAG device and use only explicit
SRAM programming mode. Record tool version, device ID, duration and result. Never
select embedded/external Flash programming: all Flash writes are prohibited in this session.
If verify fails, distinguish transfer failure from readback protection; do not loop retries.

Start KFB1 ABI 1.2 QSPI at low speed with bounded timeouts and no automatic replay of
side-effecting commands. The current MicroPython convenience connection is SPI-only;
the new software/kagura_fb/rp2040_qspi.py provides slow GPIO diagnostics and has passed
PC pin-waveform tests, but remains hardware-unverified. rp2040_bringup.py is a RAM-only
minimum diagnostic, not a firmware UF2 or full acceptance suite. Do not reuse KAGURA-9 ABI command encoding.
After ID/ABI/capability/FENCE, test READ/WRITE, FILL/PALETTE/PRESENT, cursor and BLIT.
Capture recognizable patterns; a black startup frame or transfer success is insufficient.

Restore RP2040 from the verified backup when required. Power cycling the FPGA discards
SRAM configuration, but restoration of KAGURA-9 requires confirming the existing Flash
image or loading its known-good SRAM image. Neither is yet verified; do not assume recovery.



