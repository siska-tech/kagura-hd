// SPDX-License-Identifier: Apache-2.0
#ifndef KAGURA_QSPI_H
#define KAGURA_QSPI_H
#include "../../kagura_fb/kagura_fb.h"
#define KAGURA_SYS_HZ 120000000u
#define KAGURA_SCK_HZ 5000000u
#define KAGURA_PIO_DIV 2.0f
#define KAGURA_TIMEOUT_US 100000u
#define KAGURA_CSS_NS 250u
#define KAGURA_CSH_NS 40u
#define KAGURA_CSW_NS 250u
typedef struct {
 uint64_t transactions,wire_bytes,elapsed_us,begin_us,transfer_us,end_us;
 uint64_t dma_setup_us,dma_wait_us,dma_transfers,wire_wait_us,fifo_stalls;
 uint32_t max_transaction_us,timeouts,dma_errors;
 bool faulted;
} kg_transport_stats;
/* Uses PIO0 + one unclaimed SM; GP2..5 IO, GP6 SCK, GP7 CS.
 * Caller must set the proven RP2040 120MHz system clock first.
 * No automatic retry or speed fallback after an uncertain transaction. */
int kg_transport_init(void);
void kg_transport_deinit(void);
kfb_io kg_transport_io(void);
const kg_transport_stats *kg_transport_statistics(void);
#endif
