"""Official Misaki Gothic 2021-05-05 Unicode BDF -> independent subset/atlas."""
import subprocess,sys
from pathlib import Path
subprocess.run([sys.executable,str(Path(__file__).with_name('generate.py')),'--font','misaki'],check=True)
