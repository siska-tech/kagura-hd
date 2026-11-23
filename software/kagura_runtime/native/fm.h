// SPDX-License-Identifier: Apache-2.0
#ifndef KAGURA_FM_H
#define KAGURA_FM_H
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#define FM_RATE 48000u
// Patches: 59 bytes each, Python kagura_fm.Patch.pack(). Commands: <IBBBBII.
void fm_init(void);
bool fm_effects(const uint8_t *parameters,size_t bytes);
bool fm_configure(const uint8_t *patches,size_t patch_bytes,const uint8_t *events,size_t event_bytes);
bool fm_configure_pages(const uint8_t *patches,size_t patch_bytes,const uint8_t *const *pages,size_t page_count,size_t total_bytes);
bool fm_command(unsigned op,unsigned channel,unsigned a,unsigned b,uint32_t v0,uint32_t v1);
bool fm_note_on(unsigned voice,unsigned instrument,unsigned note,unsigned velocity,uint32_t gate_ms);
bool fm_note_off(unsigned voice);
bool fm_all_off(void);
void fm_render(int8_t *left,int8_t *right,unsigned frames);
uint32_t fm_position(void);
uint32_t fm_peak(void);
uint32_t fm_clipped(void);
int fm_configuration_error(void); /* -1 OK, -2 layout/patch, >=0 invalid event index */
const uint8_t *fm_configuration_event(void);
#endif
