"""Derive ONLY a simulation harness; never rewrite the protected RTL snapshot."""
from pathlib import Path
import hashlib,json
app=Path(__file__).resolve().parents[1];repo=app.parents[1]
source=repo/'sim/tests/tb_fb_board_qspi.sv'
text=source.read_text();assert '#500;sck=1;' in text and '#500;sck=0;' in text
text=text.replace('#500;sck=1;','#100;sck=1;').replace('#500;sck=0;','#100;sck=0;')
text=text.replace(';#300;',';#250;').replace('#100;cs_n=1;oe=0;#300;','#40;cs_n=1;oe=0;#250;')
# The first replacement converts trailing guards too, so cover that form.
text=text.replace('#100;cs_n=1;oe=0;#250;','#40;cs_n=1;oe=0;#250;')
text=text.replace(' task transfer(', ' always @* if((oe & dut.host.io_oe)!=0) $fatal(1,"5MHz QSPI contention");\n task transfer(')
text=text.replace('  $display("PASS: PCM2 board', '  if(dut.host.transport.late)$fatal(1,"5MHz QSPI late");\n  $display("PASS: 5MHz QSPI PCM2 board')
out=app/'out/qspi-rtl';out.mkdir(exist_ok=True)
(out/'tb_fb_board_qspi_5mhz.sv').write_text(text)
(app/'evidence/qspi-rtl-harness.json').write_text(json.dumps({'source':str(source.relative_to(repo)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'derived_sha256':hashlib.sha256(text.encode()).hexdigest(),'changes':'test-only SCK half period 100ns, CS guards 250/40/250ns, contention/late assertions','clock_phy_lvds':'existing functional test stubs; not physical validation','release_ready':False},indent=2))
print(out/'tb_fb_board_qspi_5mhz.sv')
