"""Stage optional common filesystem files; never connects to a board."""
from pathlib import Path
import argparse
import shutil


def package(output):
    root=Path(__file__).resolve().parents[1]
    output=Path(output)
    (output/'fonts').mkdir(parents=True,exist_ok=True)
    (output/'examples').mkdir(exist_ok=True)
    for name in ('mplus12.kmf','LICENSE_MPLUS'):
        shutil.copyfile(root.parent/'kagura_fb/fonts'/name,output/'fonts'/name)
    for name in ('gpu.py','fm.py'):
        shutil.copyfile(root/'examples'/name,output/'examples'/name)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',nargs='?',default='build/kagura-runtime/files')
    package(parser.parse_args().output)
