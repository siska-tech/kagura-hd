"""Write 2x PNG previews of the artwork: python preview_art.py OUT_DIR [bar title terminal ...]"""
import sys
from pathlib import Path
from paint import to_image, rgb444
import bar_reference, ai_art

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
makers = {'bar': bar_reference.bar_indices, 'title': ai_art.title_indices, 'terminal': ai_art.terminal_indices}
for name in sys.argv[2:] or list(makers):
    idx, pal = makers[name]()
    if name == 'title':
        pal = pal.copy(); pal[12:15] = rgb444(['68a', '9bd', 'cef'])
    to_image(idx, pal).resize((1280, 720), 0).save(out/(name+'-2x.png'))
    print(name, 'ok')
