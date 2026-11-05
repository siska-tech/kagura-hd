// SPDX-License-Identifier: Apache-2.0
#ifndef B16_QSPI_H
#define B16_QSPI_H
#include "../../kagura_fb/kagura_fb.h"
#define MT_QSPI_SYS_HZ 120000000u
#define MT_QSPI_SCK_HZ 5000000u
#define MT_QSPI_PIO_DIV 2.0f
#define MT_QSPI_TIMEOUT_US 100000u
#define MT_QSPI_CSS_NS 250u
#define MT_QSPI_CSH_NS 40u
#define MT_QSPI_CSW_NS 250u
typedef struct {
 uint64_t transactions,wire_bytes,elapsed_us,begin_us,transfer_us,end_us;
 uint32_t max_transaction_us,timeouts;
 bool faulted;
} mt_qspi_stats;
/* Uses PIO0 + one unclaimed SM; GP2..5 IO, GP6 SCK, GP7 CS.
 * Caller must set the proven RP2040 120MHz system clock first.
 * No automatic retry or speed fallback after an uncertain transaction. */
int mt_qspi_init(void);
void mt_qspi_deinit(void);
kfb_io mt_qspi_io(void);
const mt_qspi_stats *mt_qspi_statistics(void);
#endif
