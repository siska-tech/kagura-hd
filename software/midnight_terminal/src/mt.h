#ifndef MT_H
#define MT_H
#include <stdint.h>
#include <stddef.h>
#ifdef _WIN32
#define MT_API __declspec(dllexport)
#else
#define MT_API
#endif
/* Explicit SDK-level operations. No invented GPU opcode or transparent BLIT. */
enum { MT_FILL=1, MT_BLIT, MT_WRITE, MT_PALETTE, MT_PRESENT, MT_AUDIO, MT_CURSOR };
typedef int (*mt_emit)(void *,int,const int32_t *,const uint8_t *,uint32_t);
typedef struct { uint32_t cp; uint8_t advance; uint16_t rows[13]; } mt_glyph;
typedef struct {
 mt_emit emit; void *ctx; uint32_t elapsed, frames, commands, bytes, presents;
 int scene, page, choice, selected, error, reduced_flash, autoplay;
 int last_text[2], last_count[2], last_warning[2], last_scroll[2], last_rain[2], last_expression[2], blink,reveal_id;
 uint32_t selected_at;
 uint32_t next_frame, last_talk; int last_audio;
} mt_engine;
MT_API size_t mt_size(void);
MT_API int mt_init(mt_engine *,mt_emit,void *,int);
MT_API int mt_tick(mt_engine *,uint32_t,int);
MT_API uint32_t mt_decode(const char **);
MT_API const mt_glyph *mt_lookup(uint32_t,int);
MT_API int mt_layout(const char *,int,int,int16_t *,int16_t *,uint32_t *,int);
MT_API const uint8_t *mt_sound(int,uint32_t *);
#endif
