"""M+ 2.2.4 JIS0208 + official JIS0201 patch -> UTF8-indexed subset/atlas."""
import subprocess,sys
from pathlib import Path
subprocess.run([sys.executable,str(Path(__file__).with_name('generate.py')),'--font','mplus'],check=True)
