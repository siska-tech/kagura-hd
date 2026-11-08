# RAM / Flash memory map

ELF section/symbol analysis. Offline bounds only; no device readback.

|Variant|Binary B|BSS B (allocated NOBITS)|Firmware erase end|
|---|---:|---:|---|
|A-off|281044|174832|0x10045000|
|A-summary|281892|174832|0x10045000|
|A-detailed|281956|174832|0x10045000|
|B-summary|283212|176884|0x10046000|
|C-test128|283212|176884|0x10046000|
|absolute30|282036|174832|0x10045000|
|cooperative|282132|175864|0x10045000|
|work64|282300|174848|0x10045000|

Filesystem starts at 0x100a0000; every firmware erase extent stays below it. Stack is reserved at __StackBottom..__StackTop (8192B). bss_end <= StackBottom verified; this is not a runtime stack watermark.

Frame log: 4600 × 24 = 110400B, down from 147200B. VECTOR previous masks: 2 × 7296B. Current mask: 7296B. LZ history: 32768B. DMA staging only in B/C: 2048+4B. Cooperative seed cache only in separate cooperative candidate: 1024B. PSRAM layout remains memory.json.

Exact allocated sections and symbols: [headroom-memory.json](evidence/headroom-memory.json). Per-variant full linker maps: out/headroom-firmware/<variant>/beyond16.elf.map. Existing memory.json and rp2040-build.json are historical and have not been relabeled as current.
