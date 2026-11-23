"""Shorten CMake's Python batch commands that exceed cmd.exe's 8191 limit.

Run after configuring on Windows and before cmake --build. Generated build
files only are changed; the MicroPython checkout is left intact.
"""
import json
import ctypes
from pathlib import Path
import runpy
import re
import subprocess
import sys


def split(command):
    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    result = parse(command, ctypes.byref(count))
    try:
        return [result[i] for i in range(count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(result)


def shorten(build):
    for batch in (Path(build) / 'CMakeFiles').glob('*.bat'):
        lines = batch.read_text().splitlines()
        changed = False
        for i, line in enumerate(lines):
            if len(line) < 8000:
                continue
            command, suffix = line.rsplit(' || ', 1)
            if command.startswith('cat '):
                pieces = command.split(' | ')
                args = ['--qstr', split(pieces[0])[1:], split(pieces[2]),
                        split(pieces[-1].split(' > ', 1)[1])[0]]
            else:
                args = split(command)
            if args[0] != '--qstr' and 'python' not in Path(args[0]).name.lower():
                raise RuntimeError('unsupported long batch command: ' + str(batch))
            response = batch.with_suffix('.args.json')
            response.write_text(json.dumps(args if args[0] == '--qstr' else args[1:]))
            lines[i] = '"{}" "{}" --run "{}" || {}'.format(
                sys.executable, Path(__file__).resolve(), response.resolve(), suffix)
            changed = True
        if changed:
            batch.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    if sys.argv[1] == '--run':
        sys.argv = json.loads(Path(sys.argv[2]).read_text())
        if sys.argv[0] == '--qstr':
            _, sources, compiler, output = sys.argv
            data = b''.join(Path(p).read_bytes() for p in sources)
            data = re.sub(rb'(?m)^(Q\(.*\))', rb'"\1"', data)
            response = Path(output).with_suffix('.gcc.rsp')
            response.write_text('\n'.join('"' + a.replace('\\', '\\\\').replace('"', '\\"') + '"'
                                          for a in compiler[1:]))
            data = subprocess.check_output([compiler[0], '@' + str(response)], input=data)
            Path(output).write_bytes(re.sub(rb'(?m)^"(Q\(.*\))"', rb'\1', data))
        else:
            runpy.run_path(sys.argv[0], run_name='__main__')
    else:
        shorten(sys.argv[1])
