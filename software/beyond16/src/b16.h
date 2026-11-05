#ifndef B16_H
#define B16_H
#include "../../kagura_fb/kagura_fb.h"
#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API
#endif
#define B16_DURATION 150000u
#define PAGE_BYTES 115200u
#define BGM_ADDR 0x80000u
#define BGM_SIZE 384000u
#define FX_ADDR 0xe0000u
typedef struct {uint64_t commands,blit_pixels,upload_bytes;uint32_t frames,skipped,scene,now_ms;int error;} b16_stats;
typedef struct {kfb_device *gpu;uint32_t seed,next_frame,last_audio_poll,audio_epoch_ms;int scene,page,started,error,page_scene[2],final_ready[2];unsigned stars,objects;uint8_t dirty[2][26][80];b16_stats stats;} b16_engine;
API size_t b16_size(void);
API int b16_init(b16_engine *,kfb_device *,uint32_t);
API int b16_tick(b16_engine *,uint32_t);
API int b16_finish(b16_engine *);
API void b16_load_test(b16_engine *,unsigned,unsigned);
API const b16_stats *b16_statistics(b16_engine *);
int b16_assets(kfb_device *);
int b16_audio(kfb_device *,int);
int b16_audio_poll(kfb_device *);
int b16_audio_stop(kfb_device *);
/* Session-local immutable CAPS cache; all command execution remains in the SDK. */
typedef struct {kfb_io raw;uint8_t caps;int cached;} b16_bus;
kfb_io b16_cached_io(b16_bus *,kfb_io);
#endif
