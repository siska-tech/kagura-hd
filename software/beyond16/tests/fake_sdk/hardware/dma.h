#include "pico_stub.h"
typedef struct {bool read_inc,write_inc;unsigned dreq,size;} dma_channel_config;
#define DMA_SIZE_32 2
int dma_claim_unused_channel(bool required);
void dma_channel_unclaim(uint ch);
void dma_channel_abort(uint ch);
dma_channel_config dma_channel_get_default_config(uint ch);
void channel_config_set_transfer_data_size(dma_channel_config *c,uint n);
void channel_config_set_read_increment(dma_channel_config *c,bool b);
void channel_config_set_write_increment(dma_channel_config *c,bool b);
void channel_config_set_dreq(dma_channel_config *c,uint n);
uint pio_get_dreq(PIO p,uint sm,bool tx);
void dma_channel_configure(uint ch,const dma_channel_config *c,volatile void *dst,const volatile void *src,uint n,bool start);
void dma_start_channel_mask(uint mask);
bool dma_channel_is_busy(uint ch);

#define DMA_CH0_CTRL_TRIG_READ_ERROR_BITS (1u<<30)
#define DMA_CH0_CTRL_TRIG_WRITE_ERROR_BITS (1u<<29)
typedef struct {uint32_t ctrl_trig,transfer_count;} dma_channel_hw_t;
dma_channel_hw_t *dma_channel_hw_addr(uint ch);
