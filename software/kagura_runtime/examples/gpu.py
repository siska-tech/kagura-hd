"""Draw for one second, then restore the framebuffer REPL."""
from kagura_gpu import Device
from time import sleep_ms

with Device() as gpu:
    gpu.palette(0,0x012)
    gpu.palette(1,0x38f)
    gpu.fill_rect(0,0,0,640,360,0)
    gpu.fill_rect(0,80,80,480,200,1)
    gpu.present(0)
    sleep_ms(1000)
