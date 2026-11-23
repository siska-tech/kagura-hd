# SPDX-License-Identifier: Apache-2.0
# Copy as /boot.py after validating rp2040_pio and the console on the board.
# USB REPL is retained; an unavailable FPGA skips HDMI without waiting forever.
try:
    import kagura_console
    kagura_console.start()
except Exception as error:
    print('HDMI REPL skipped:', error)
