"""Run existing SDK tests against freshly compiled default and packed SDKs."""
import ctypes as C
import importlib.util
import json,re,subprocess,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
SDK=R.parent/'kagura_fb'
OUT=R/'out/headroom-tests'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(SDK/'tests'))
spec=importlib.util.spec_from_file_location('sdk_regression',SDK/'tests/test_drivers.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
VC=r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
exports=' '.join('/EXPORT:'+n for n in re.findall(r'int (kfb_\w+)\(', (SDK/'kagura_fb.h').read_text()))
original=C.CDLL;rows=[]
for packed in (0,1):
    dll=OUT/f'sdk{packed}.dll'
    cmd=f'call "{VC}" >nul && cl /nologo /LD /O2 /std:c11 /DKFB_PACK_DESCRIPTOR={packed} "{SDK}/kagura_fb.c" /Fo"{OUT}/" /link {exports} /IMPLIB:"{OUT}/sdk{packed}.lib" /OUT:"{dll}"'
    subprocess.run('cmd.exe /d /c '+cmd,check=True,capture_output=True)
    C.CDLL=lambda path,*args,**kwargs:original(str(dll) if str(path).endswith('libkagura_fb.so') else path,*args,**kwargs)
    try:result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(module))
    finally:C.CDLL=original
    assert result.wasSuccessful()
    rows.append(dict(packed=packed,tests=result.testsRun,status='PASS'))
(R/'evidence/headroom-sdk.json').write_text(json.dumps(rows,indent=2))
