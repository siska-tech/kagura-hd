// SPDX-License-Identifier: Apache-2.0
// Reuse the proven C/PIO host; keep divider changes local to this RAM test.
#include "../beyond16/src/b16_qspi.c"
int bench_divider(unsigned div256) {
    if (div256 < 256 || div256 > 2560) return KFB_ARGUMENT;
    mt_qspi_deinit();
    int rc = mt_qspi_init();
    if (rc) return rc;
    pio_sm_set_enabled(bus, (uint)sm, false);
    pio_sm_set_clkdiv_int_frac(bus, (uint)sm, div256 >> 8, div256 & 255);
    pio_sm_clkdiv_restart(bus, (uint)sm);
    pio_sm_set_enabled(bus, (uint)sm, true);
    return 0;
}
