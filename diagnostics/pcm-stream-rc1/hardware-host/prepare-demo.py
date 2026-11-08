"""Build an isolated copy of the current BEYOND drawing engine for the RAM Host."""
import hashlib
from pathlib import Path
import sys

source, destination = map(Path, sys.argv[1:])
original = source.read_bytes()
code = original.decode("utf-8").replace("\r\n", "\n")

# The RAM Host supplies the PCM stream. Omit the legacy song and FX upload,
# and leave the compressed visual assets and scene renderer intact.
start = code.index("c.address=BGM_ADDR;")
end = code.index("if(!r)r=kfb_fence(g);return r;}", start)
code = code[:start] + code[end:]
start = code.index("static int aw(")
end = code.index("static int fs(", start)
code = code[:start] + code[end:]
code = code.replace('#include "../../midnight_terminal/src/mt_lz.h"', '#include "mt_lz.h"')
code = code.replace('#include "../generated/assets.inc"', '#include "assets.inc"')
code = code.replace("e->stats.upload_bytes=636928", "e->stats.upload_bytes=2*PAGE_BYTES")
destination.write_text(code, encoding="utf-8")
destination.with_suffix(".source-sha256").write_text(hashlib.sha256(original).hexdigest() + "\n")
