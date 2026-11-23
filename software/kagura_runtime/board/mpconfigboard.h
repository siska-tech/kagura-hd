// SPDX-License-Identifier: Apache-2.0
#define MICROPY_HW_BOARD_NAME "KAGURA-HD GPU runtime"
#define MICROPY_HW_FLASH_STORAGE_BYTES (1408 * 1024)
#ifndef __ASSEMBLER__
void kagura_soft_reset(void);
#endif
#define MICROPY_BOARD_START_SOFT_RESET() kagura_soft_reset()
