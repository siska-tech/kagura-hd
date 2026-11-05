"""Derive an observational host wrapper; product RTL remains untouched."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[2];out=Path(__file__).resolve().parent
source=(root/'rtl/fb/kagura_fb_host.sv').read_text()
ports='''    input wire [7:0] cursor_rsp_data,
    output wire obs_rx_take,obs_rx_write,
    output wire [5:0] obs_rx_addr,
    output wire [7:0] obs_rx_data,
    output wire obs_csr_take,obs_csr_write,
    output wire [4:0] obs_csr_addr,
    output wire [7:0] obs_csr_data,
    output wire obs_csr_rsp,obs_tx_rsp,
    output wire [7:0] obs_csr_rdata,obs_tx_rdata,
    output wire [31:0] obs_upload
'''
derived=source.replace('module kagura_fb_host #','module kagura_fb_host_observe #')
assert '    input wire [7:0] cursor_rsp_data\n' in derived
derived=derived.replace('    input wire [7:0] cursor_rsp_data\n',ports)
assigns='''    // Diagnostic observation only; no source control or memory signals changed.
    assign obs_rx_take=req_valid && req_ready;
    assign obs_rx_write=req_write;
    assign obs_rx_addr=req_addr;
    assign obs_rx_data=req_wdata;
    assign obs_csr_take=base_valid && base_ready;
    assign obs_csr_write=base_write;
    assign obs_csr_addr=base_addr;
    assign obs_csr_data=base_data;
    assign obs_csr_rsp=base_rsp_valid;
    assign obs_csr_rdata=base_rsp_data;
    assign obs_tx_rsp=rsp_valid && !bus_cursor;
    assign obs_tx_rdata=rsp_rdata;
    assign obs_upload=upload_data[31:0];
'''
derived=derived.replace('endmodule',assigns+'endmodule')
(out/'kagura_fb_host_observe.sv').write_text(derived)
# Prove the derivation differs only in module name, observation ports and wires.
restored=derived.replace('module kagura_fb_host_observe #','module kagura_fb_host #')
restored=restored.replace(ports,'    input wire [7:0] cursor_rsp_data\n').replace(assigns,'')
assert restored==source
serializer=(root/'diagnostics/psram-isolation/pdt_snapshot.sv').read_text()
serializer=serializer.replace('module pdt_snapshot #','module window_snapshot #')
serializer=serializer.replace("16'd1,(writing ? 8'd2 : 8'd3)","16'd2,8'd4")
(out/'window_snapshot.sv').write_text(serializer)
top=(root/'diagnostics/psram-isolation/host_isolation_top.sv').read_text()
top=top.replace('host_isolation_core core','window_observe_core core')
(out/'host_isolation_top.sv').write_text(top)
(out/'derivation.json').write_text(json.dumps(dict(product_host_sha256=hashlib.sha256((root/'rtl/fb/kagura_fb_host.sv').read_bytes()).hexdigest(),
    observer_inverse_transform_matches_product=True),indent=2)+'\n')
