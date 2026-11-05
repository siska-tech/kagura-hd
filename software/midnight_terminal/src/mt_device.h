#ifndef MT_DEVICE_H
#define MT_DEVICE_H
#include "mt.h"
#include "../../kagura_fb/kagura_fb.h"
typedef struct {kfb_device *gpu;int audio_available,audio_error;uint8_t enabled[2],gain[2];uint32_t waits_ms; } mt_device;
int mt_device_start(mt_device *,kfb_device *);
int mt_device_poll(mt_device *);
int mt_device_emit(void *,int,const int32_t *,const uint8_t *,uint32_t);
#endif
