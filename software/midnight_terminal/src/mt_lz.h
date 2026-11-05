#ifndef MT_LZ_H
#define MT_LZ_H
#include <stdint.h>
typedef int (*mt_lz_sink)(void *,const uint8_t *,uint32_t);
int mt_lz_decode(const uint8_t *,uint32_t,uint32_t,mt_lz_sink,void *);
struct kfb_device_placeholder;
#endif
