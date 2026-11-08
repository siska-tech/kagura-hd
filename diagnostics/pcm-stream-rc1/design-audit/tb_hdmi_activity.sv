// RTL-only RGB independence test. Serializer deliberately stubbed; no wire claims.
`timescale 1ns/1ps
module serializer #(parameter NUM_CHANNELS=3,parameter real VIDEO_RATE=74.25e6)(
 input wire clk_pixel,clk_pixel_x5,reset,input wire [9:0] tmds_internal[NUM_CHANNELS-1:0],
 output wire [2:0] tmds,output wire tmds_clock);
 assign tmds=0;assign tmds_clock=clk_pixel;
endmodule
module tb_hdmi_activity;
 reg clk=0,reset=1;
 always #5 clk=~clk;
 reg sample_valid=0;
 reg [31:0] sample_data=0;
 wire [5:0] ready;
 wire [10:0] x[6];wire [9:0] y[6];
 reg [7:0] frame[115200]; reg [11:0] palette[16];
 wire [23:0] headers[6]; wire [223:0] subs[6];wire [8:0] packets[6];
 wire [29:0] symbols[6];wire [2:0] encmode[6];
 integer rgb_count[6],symbol_count[6],serial_count[6];
 longint unsigned symhash[6];
 reg [23:0] oldrgb[6];reg [29:0] oldsym[6];reg [2:0] lastbit[6];
 integer cycle=0,phase=0,accepted=0,asp=0,acr=0,di=0;
 reg [31:0] expected_pcm[2048]; integer consumed=0,transcript_fd;
 string transcript;
 reg packet_loaded=0;
 for(genvar p=0;p<6;p++) begin:g
  wire active=x[p]<1280 && y[p]<720;
  wire [16:0] offset=17'((y[p]/2)*320+x[p]/4);
  wire [7:0] packed_pixel=active?frame[offset]:0;
  wire [3:0] index=x[p][1]?packed_pixel[3:0]:packed_pixel[7:4];
  wire [11:0] color=palette[index];
  wire [23:0] original={color[11:8],color[11:8],color[7:4],color[7:4],color[3:0],color[3:0]};
  wire [23:0] rgb=!active?24'd0:p==0?24'd0:p==1?24'hffffff:p==2?24'hff0000:p==3?24'h00ff00:p==4?24'h0000ff:original;
  kagura_hdmi_stream #(.VIDEO_ID_CODE(4),.VIDEO_REFRESH_RATE(60.0),.PACKET_REPLICATE_FIRST(1),.DVI_OUTPUT(0),.AUDIO_RATE(48000),.AUDIO_BIT_WIDTH(16)) dut(
   .clk_pixel(clk),.clk_pixel_x5(clk),.reset,.sample_valid,.sample_data,.sample_ready(ready[p]),.rgb,.cx(x[p]),.cy(y[p]));
  assign headers[p]=dut.true_hdmi_output.header;
  assign subs[p]={dut.true_hdmi_output.sub[3],dut.true_hdmi_output.sub[2],dut.true_hdmi_output.sub[1],dut.true_hdmi_output.sub[0]};
  assign packets[p]=dut.true_hdmi_output.packet_data;
  assign symbols[p]={dut.tmds_internal[2],dut.tmds_internal[1],dut.tmds_internal[0]};
  assign encmode[p]=dut.tmds_gen[0].tmds_channel.mode2;
  always @(negedge clk) if(!reset) begin
   assert(ready[p]==ready[0] && headers[p]==headers[0] && subs[p]==subs[0] && packets[p]==packets[0]) else $fatal(1,"packet mismatch %0d",p);
   // tmds output corresponds to mode2 before the last posedge; use delayed mode.
   rgb_count[p]+=$countones(rgb^oldrgb[p]);oldrgb[p]=rgb;
   symbol_count[p]+=$countones(symbols[p]^oldsym[p]);oldsym[p]=symbols[p];
   symhash[p]=(symhash[p]^64'(symbols[p]))*64'h100000001b3;
   for(int lane=0;lane<3;lane++) begin
    for(int bitno=0;bitno<10;bitno++) begin
     serial_count[p]+=int'(lastbit[p][lane]!=symbols[p][lane*10+bitno]);lastbit[p][lane]=symbols[p][lane*10+bitno];
    end
   end
  end
 end
 reg [2:0] previous_mode=0;
 always @(posedge clk) if(!reset) begin
  previous_mode<=encmode[0];
  packet_loaded<=g[0].dut.true_hdmi_output.packet_enable;
  if(sample_valid && ready[0]) begin expected_pcm[accepted]=sample_data;accepted++;end
 end
 always @(negedge clk) if(!reset) begin
  if(previous_mode==3) begin
   di++;
   for(int p=1;p<6;p++) assert(symbols[p]==symbols[0]) else $fatal(1,"TERC4 mismatch");
  end
  if(packet_loaded) begin
   $fdisplay(transcript_fd,"%06x %056x",headers[0],subs[0]);
   if(headers[0][7:0]==2) begin
    asp++;
    for(int i=0;i<4;i++) begin
     assert(consumed<accepted && subs[0][i*56+8+:16]==expected_pcm[consumed][15:0] && subs[0][i*56+32+:16]==expected_pcm[consumed][31:16]) else $fatal(1,"PCM packet ordering %0d",consumed);
     consumed++;
    end
   end
   if(headers[0][7:0]==1) acr++;
  end
 end
 initial begin
  if(!$value$plusargs("TRANSCRIPT=%s",transcript)) $fatal(1,"missing transcript path");
  transcript_fd=$fopen(transcript,"w");
  $readmemh("diagnostics/pcm-stream-rc1/design-audit/frame.hex",frame);
  $readmemh("diagnostics/pcm-stream-rc1/design-audit/palette.hex",palette);
  for(int p=0;p<6;p++) begin rgb_count[p]=0;symbol_count[p]=0;serial_count[p]=0;oldrgb[p]=0;oldsym[p]=0;lastbit[p]=0;symhash[p]=64'hcbf29ce484222325;end
  repeat(10) @(negedge clk); reset=0;
  // Exactly two 720p frames, common 48 kHz fractional tick and PCM sequence.
  repeat(2475000) begin
   @(negedge clk);cycle++;phase+=8;
   sample_valid=phase>=12375;
   if(sample_valid) begin phase-=12375;sample_data+=32'h01010001;end
  end
  for(int p=0;p<6;p++) $display("HDMI pattern=%0d RGB24=%0d parallelTMDS30=%0d serializedEdges=%0d tmdsFNV64=%016x",p,rgb_count[p],symbol_count[p],serial_count[p],symhash[p]);
  $fclose(transcript_fd);
  $display("PASS RGB packet/TERC4 equality accepted=%0d consumed=%0d ASP=%0d ACR=%0d DI_symbols=%0d",accepted,consumed,asp,acr,di);$finish;
 end
endmodule
