"""Package the Python application and filesystem assets, without building FW."""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import zlib
import zipfile


def package(output):
    root=Path(__file__).resolve().parents[1]
    output=Path(output)
    (output/'mt_data').mkdir(parents=True,exist_ok=True)
    for name in ('midnight_terminal','midnight_show','midnight_fm','midnight_music','midnight_instruments','midnight_graphics'):
        shutil.copyfile(root/'micropython'/(name+'.py'),output/(name+'.py'))
    shutil.copyfile(root/'tools/story.py',output/'story.py')
    shutil.copyfile(root/'generated/midnight_assets.py',output/'midnight_assets.py')
    source=(root/'generated/assets.c').read_text()
    manifest={}
    for bits,name,body in re.findall(r'const uint(8|16)_t (\w+)\[\d+\]=\{([^}]+)\}',source):
        if not name.startswith(('img_','eye_')) and name not in ('mplus_rows','misaki_rows'):
            continue
        values=[int(v.strip(),0) for v in body.split(',') if v.strip()]
        data=struct.pack('<'+('B' if bits=='8' else 'H')*len(values),*values)
        if name.startswith('img_'):
            data=zlib.decompress(data,-12)
            assert len(data)==115200
            name=name[4:]
        (output/'mt_data'/(name+'.bin')).write_bytes(data)
        manifest[name]=len(data)
    shutil.copyfile(root/'LICENSES.md',output/'MIDNIGHT_LICENSES.md')
    (output/'licenses').mkdir(exist_ok=True)
    for name in ('LICENSE_E','LICENSE_J','misaki.txt'):
        shutil.copyfile(root/'vendor'/name,output/'licenses'/name)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in output.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.pyo'):
                archive.write(path,str(path.relative_to(output)))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',nargs='?',default='build/midnight-terminal/micropython-app')
    print(json.dumps(package(parser.parse_args().output),indent=2))
