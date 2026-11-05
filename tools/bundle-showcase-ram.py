"""Generate ordered, bounded RAM-only REPL packets. Does NOT open a serial port."""
from pathlib import Path
import base64,json,hashlib,re
r=Path(__file__).resolve().parents[1];s=r/'software/kagura_fb';out=r/'build/showcase/ram-loader';out.mkdir(parents=True,exist_ok=True)
names=['kagura_fb','kagura_fb_audio','rp2040_qspi','showcase','showcase.vendor',
       'showcase.vendor.ascii_rows','showcase.vendor.fonts','showcase.diagnostics',
       'showcase.gpu_api_adapter','showcase.music','showcase.scenes','showcase.scene_manager','showcase.demo_main']
manifest=[]
def ram_imports(source,package):
 def replace(match):
  indent,module,items=match.groups()
  if module.startswith('.'):
   module=package+module
   module=module.rstrip('.')
  if not (module.startswith('showcase') or module in ('kagura_fb','kagura_fb_audio')):return match.group(0)
  return '\n'.join(indent+name+"=_ram[%r]"%(module+'.'+name) if match.group(2)=='.' else
                   indent+name+"=_ram[%r].%s"%(module,name)
                   for name in (x.strip() for x in items.split(',')))
 return re.sub(r'^([ \t]*)from ([.\w]+) import ([\w, ]+)$',replace,source,flags=re.M)
for i,name in enumerate(names):
 path=s/(name.replace('.','/')+'.py')
 package=not path.exists()
 if package:path=s/name.replace('.','/')/'__init__.py'
 data=path.read_bytes();pkg=name if package else name.rpartition('.')[0]
 ram_source=ram_imports(data.decode(),pkg).encode();encoded=base64.b64encode(ram_source).decode()
 lines=['# RAM-only packet: no connection, GPIO access or filesystem writes.',
        '# MicroPython cannot construct ModuleType. Only local import binding',
        '# is rewritten to the shared RAM export map; public APIs are unchanged.',
        'import binascii, gc',
        "if '_kagura_ram' not in globals():",
        '    _kagura_ram={}',
        '    class _RAMView:',
        '        def __init__(self,namespace):self._ns=namespace',
        '        def __getattr__(self,name):',
        '            try:return self._ns[name]',
        '            except KeyError:raise AttributeError(name)',
        "_ram_namespace={'__name__':%r,'_ram':_kagura_ram}"%name,
        '_kagura_ram[%r]=_RAMView(_ram_namespace)'%name,
        # Bytes literals avoid permanently interning the encoded source as
        # MicroPython qstr data. Each packet's temporary bytes can be collected.
        '_ram_source=binascii.a2b_base64(%r)'%encoded.encode(),
        'exec(_ram_source,_ram_namespace)',
        'del _ram_source,_ram_namespace','gc.collect()']
 file=out/('%02d_%s.repl.py'%(i,name.replace('.','_')));file.write_text('\n'.join(lines)+'\n')
 manifest.append({'module':name,'packet':file.name,'source':str(path.relative_to(r)),
                  'source_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                  'ram_source_sha256':hashlib.sha256(ram_source).hexdigest()})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
runner=['import gc']+["exec(open(%r).read())"%str(out/x['packet']) for x in manifest]
fixture=ram_imports((s/'showcase/tests/memory_micropython.py').read_text(),'')
runner += ["assert _kagura_ram['showcase.demo_main'].run_on_device",'gc.collect()',
           "print('PASS: RAM export load, no GPIO/serial/file writes; alloc=%d free=%d'%(gc.mem_alloc(),gc.mem_free()))",
           "exec(%r,{'__name__':'ram_memory_proof','_ram':_kagura_ram})"%fixture]
(out/'unix-proof.py').write_text('\n'.join(runner)+'\n')
print('Generated',len(manifest),'RAM packets; no automatic sender or device actions')
