// SPDX-License-Identifier: Apache-2.0
// Independent cursor CSR window (absolute registers 32..63). 32x32 2bpp,
// MSB-first pixels, 0 transparent, three RGB444 colors. Bank ownership protects
// shape/palette/hotspot through the bundled-data toggle/ack mailbox. Position
// commits coalesce in one latest-value slot while a vblank update is pending.
// Resets must assert together. Physical CDC signoff remains a board obligation.
module kagura_fb_cursor #(parameter bit PIPELINE_MAILBOX=0) (
 input wire sys_clk,sys_reset,pix_clk,pix_reset,
 input wire req_valid,req_write,input wire [4:0] req_addr,input wire [7:0] req_wdata,
 output wire req_ready,output reg rsp_valid,rsp_error,output reg [7:0] rsp_data,output wire irq,
 input wire [10:0] cx,input wire [9:0] cy,input wire [23:0] background,
 output reg [23:0] rgb_out
);
 // Capture and classify the request before CSR execution. The endpoint
 // accepts one request every two system edges; the transport holds valid
 // until ready. Predecoded COMMIT data keeps an 8-bit reduction off held/queued.
 reg bus_valid,bus_write,bus_one;
 reg [4:0] bus_addr;
 reg [7:0] bus_data;
 assign req_ready=!sys_reset && !bus_valid;
 always @(posedge sys_clk) begin
  if(sys_reset) begin bus_valid<=0;bus_write<=0;bus_one<=0;bus_addr<=0;bus_data<=0;end
  else begin
   bus_valid<=req_valid && req_ready;
   if(req_valid && req_ready) begin
    bus_write<=req_write;bus_addr<=req_addr;bus_data<=req_wdata;bus_one<=req_wdata==1;
   end
  end
 end
 reg [15:0] stage_x,stage_y;
 reg [1:0] stage_control;
 reg x_range_ok,y_range_ok;
 reg edit_bank;
 reg [8:0] image_offset;
 reg [1:0][8:0] loaded;
 reg [1:0] shape_complete;
 reg [35:0] colors0,colors1,held_colors;
 wire [35:0] staged_colors=stage_control[1] ? colors1 : colors0;
 reg [4:0] hot_x0,hot_x1,hot_y0,hot_y1;
 reg [25:0] held,queued;
 reg pending,queued_valid,request_toggle,ack,seen;
 reg active_bank_sys,active_visible_sys,completed;
 reg [15:0] generation;
 reg [7:0] generation_high,last_error;
 (* ASYNC_REG="TRUE" *) reg [1:0] ack_sync,request_sync;
 wire locked=edit_bank==active_bank_sys || (pending && edit_bank==held[25]) || (queued_valid && edit_bank==queued[25]);
 wire fire=bus_valid;
 wire acked=pending && ack_sync[1]==request_toggle;
 // Capture the top-left origin once, instead of adding the hotspot on
 // every pixel. The mailbox owns this bank's metadata until acknowledgement.
 wire [4:0] selected_hot_x=stage_control[1] ? hot_x1 : hot_x0;
 wire [4:0] selected_hot_y=stage_control[1] ? hot_y1 : hot_y0;
 wire signed [11:0] origin_x=$signed({stage_x[10],stage_x[10:0]})-$signed({7'd0,selected_hot_x});
 wire signed [11:0] origin_y=$signed({stage_y[10],stage_y[10:0]})-$signed({7'd0,selected_hot_y});
 wire [25:0] staged={stage_control,origin_y,origin_x};
 wire [7:0] commit_error=!bus_one ? 8'd2 :
     (!x_range_ok || !y_range_ok) ? 8'd3 :
     (stage_control[0] && !shape_complete[stage_control[1]]) ? 8'd7 : 8'd0;
 wire [7:0] image_error=locked ? 8'd1 : image_offset>=256 ? 8'd5 :
     (image_offset!=0 && image_offset!=loaded[edit_bank]) ? 8'd2 : 8'd0;
 reg [7:0] write_error;
 always @* begin
  write_error=0;
  case(bus_addr)
   0: if(bus_data>3) write_error=2;
   1,2,3,4,14,21: begin end
   5,6: if(locked) write_error=1; else if(bus_data>31) write_error=3;
   7,9,11: if(locked) write_error=1;
   8,10,12: if(locked) write_error=1; else if(bus_data>15) write_error=3;
   15: if(bus_data>1) write_error=3;
   16: write_error=image_error;
   17: write_error=commit_error;
   18: if((bus_data & 8'hbf)!=0) write_error=2;
   default: write_error=2;
  endcase
 end
 wire commit=fire && bus_write && bus_addr==17 && commit_error==0;
 wire write_ram=fire && bus_write && bus_addr==16 && image_error==0;
 assign irq=completed || last_error!=0;
 always @(posedge sys_clk) begin
  if(sys_reset) begin
   stage_x<=0;stage_y<=0;stage_control<=0;x_range_ok<=1;y_range_ok<=1;edit_bank<=1;image_offset<=0;shape_complete<=0;
   held<=0;queued<=0;held_colors<=0;pending<=0;queued_valid<=0;request_toggle<=0;ack_sync<=0;
   active_bank_sys<=0;active_visible_sys<=0;completed<=0;generation<=0;generation_high<=0;last_error<=0;
   rsp_valid<=0;rsp_error<=0;rsp_data<=0;
   colors0<=0;colors1<=0;hot_x0<=0;hot_x1<=0;hot_y0<=0;hot_y1<=0;loaded<=0;
  end else begin
   ack_sync<={ack_sync[0],ack};
   rsp_valid<=fire;rsp_error<=0;rsp_data<=0;
   if(fire) begin
    if(bus_write) begin
     if(write_error!=0) begin rsp_error<=1;if(last_error==0) last_error<=write_error;end
     case(bus_addr)
      0: if(bus_data<=3) stage_control<=bus_data[1:0];
      1: stage_x[7:0]<=bus_data;
      2: begin stage_x[15:8]<=bus_data;x_range_ok<=bus_data[7:3]=={5{bus_data[2]}};end
      3: stage_y[7:0]<=bus_data;
      4: begin stage_y[15:8]<=bus_data;y_range_ok<=bus_data[7:3]=={5{bus_data[2]}};end
      5: if(!locked && bus_data<32) if(edit_bank) hot_x1<=bus_data[4:0]; else hot_x0<=bus_data[4:0];
      6: if(!locked && bus_data<32) if(edit_bank) hot_y1<=bus_data[4:0]; else hot_y0<=bus_data[4:0];
      7: if(!locked) if(edit_bank) colors1[7:0]<=bus_data; else colors0[7:0]<=bus_data;
      8: if(!locked && bus_data<16) if(edit_bank) colors1[11:8]<=bus_data[3:0]; else colors0[11:8]<=bus_data[3:0];
      9: if(!locked) if(edit_bank) colors1[19:12]<=bus_data; else colors0[19:12]<=bus_data;
      10: if(!locked && bus_data<16) if(edit_bank) colors1[23:20]<=bus_data[3:0]; else colors0[23:20]<=bus_data[3:0];
      11: if(!locked) if(edit_bank) colors1[31:24]<=bus_data; else colors0[31:24]<=bus_data;
      12: if(!locked && bus_data<16) if(edit_bank) colors1[35:32]<=bus_data[3:0]; else colors0[35:32]<=bus_data[3:0];
      14: image_offset<={1'b0,bus_data};
      15: if(bus_data<=1) begin edit_bank<=bus_data[0];image_offset[8]<=0;end
      16: if(image_error==0) begin
       image_offset<=image_offset+1'b1;loaded[edit_bank]<=image_offset+1'b1;
       if(image_offset==0) shape_complete[edit_bank]<=0;
       if(image_offset==255) shape_complete[edit_bank]<=1;
      end
      18: if(bus_data==64) completed<=0;
      21: last_error<=0;
      default: begin end
     endcase
    end else case(bus_addr)
     18:rsp_data<={1'b0,completed,shape_complete,queued_valid,active_visible_sys,active_bank_sys,pending};
     19:begin rsp_data<=generation[7:0];generation_high<=generation[15:8];end
     20:rsp_data<=generation_high;
     21:rsp_data<=last_error;
     default:rsp_data<=0;
    endcase
   end
   if(commit) begin
    if(pending) begin queued<=staged;queued_valid<=1;end
    else begin held<=staged;held_colors<=staged_colors;request_toggle<=~request_toggle;pending<=1;end
   end
   // A simultaneous ack and new commit retains the newest complete position.
   if(acked) begin
    active_bank_sys<=held[25];active_visible_sys<=held[24];generation<=generation+1'b1;completed<=1;
    if(commit || queued_valid) begin
     held<=commit ? staged : queued;held_colors<=commit ? staged_colors : (queued[25] ? colors1 : colors0);request_toggle<=~request_toggle;pending<=1;queued_valid<=0;
    end else pending<=0;
   end
  end
 end
 reg signed [11:0] position_x,position_y;
 // The held bundle remains stable until the acknowledgement returns. The
 // two request synchronizer stages leave a complete PIX edge to sample data
 // before its qualified vblank commit. This adds a data-path stage without
 // delaying the mailbox application/ack edge or changing bundle coherence.
 wire [25:0] apply_bundle;
 wire [35:0] apply_colors;
 generate if(PIPELINE_MAILBOX) begin: sample_mailbox
  reg [61:0] value;
  always @(posedge pix_clk)
   if(pix_reset) value<=0;
   else value<={held_colors,held};
  assign {apply_colors,apply_bundle}=value;
 end else begin: direct_mailbox
  assign apply_bundle=held;
  assign apply_colors=held_colors;
 end endgenerate
 reg active_bank,visible,vblank;
 reg [35:0] pixel_colors;
 always @(posedge pix_clk) begin
  if(pix_reset) begin
   request_sync<=0;seen<=0;ack<=0;vblank<=0;position_x<=0;position_y<=0;active_bank<=0;visible<=0;
   pixel_colors<=0;
  end else begin
   request_sync<={request_sync[0],request_toggle};
   vblank<=cx==1649 && cy==719;
   if(vblank && request_sync[1]!=seen) begin
    position_x<=apply_bundle[11:0];position_y<=apply_bundle[23:12];active_bank<=apply_bundle[25];visible<=apply_bundle[24];
    // Palette is snapshotted with the SYS mailbox. Its selection must
    // not share the 10 ns bundled-data crossing with a 36-bit pixel mux.
    pixel_colors<=apply_colors;
    seen<=request_sync[1];ack<=request_sync[1];
   end
  end
 end
 // Four-cycle cursor lookahead. The final output register replaces the
 // pre-existing HDMI RGB register, so background/sync latency is unchanged.
 wire [9:0] ahead_y=cx>=1646 ? (cy==749 ? 10'd0 : cy+10'd1) : cy;
 reg [9:0] logical_x;
 reg [8:0] logical_y;
 reg look_active,delta_active;
 reg signed [11:0] dx,dy;
 always @(posedge pix_clk) begin
  // Fixed 1650-pixel raster, 2x logical scale. Equivalent to
  // ((cx+4)%1650)/2, without a cx-driven wide add/mux path.
  // cx==0 resynchronizes every line, including reset release.
  if(pix_reset || cx==0) logical_x<=10'd2;
  else if(!cx[0]) logical_x<=logical_x==824 ? 10'd0 : logical_x+1'b1;
  logical_y<=ahead_y[9:1];
  look_active<=!pix_reset && ((cx<1276 && cy<720) || (cx>=1646 && (cy==749 || cy<719)));
  dx<=$signed({2'd0,logical_x})-position_x;
  dy<=$signed({3'd0,logical_y})-position_y;
  delta_active<=!pix_reset && look_active && visible;
 end
 wire read_enable=delta_active && dx[11:5]==0 && dy[11:5]==0;
 wire [7:0] bitmap_byte;
 wire [7:0] unused_read;
 kagura_ram_tdp #(.DEPTH(512),.WIDTH(8)) bitmap(
  .clk_a(sys_clk),.enable_a(write_ram),.write_a(write_ram),.addr_a({edit_bank,image_offset[7:0]}),.wdata_a(bus_data),.rdata_a(unused_read),
  .clk_b(pix_clk),.enable_b(read_enable && !pix_reset),.addr_b({active_bank,dy[4:0],dx[4:2]}),.rdata_b(bitmap_byte));
 reg ram_valid,index_valid;
 reg [1:0] lane,index;
 reg [11:0] color;
 always @* case(index)
  1:color=pixel_colors[11:0];2:color=pixel_colors[23:12];3:color=pixel_colors[35:24];default:color=0;
 endcase
 always @(posedge pix_clk) begin
  ram_valid<=!pix_reset && read_enable;lane<=dx[1:0];
  index<=2'(bitmap_byte >> {~lane,1'b0});index_valid<=!pix_reset && ram_valid;
  if(pix_reset) rgb_out<=0;
  else if(index_valid && index!=0) rgb_out<={color[11:8],color[11:8],color[7:4],color[7:4],color[3:0],color[3:0]};
  else rgb_out<=background;
 end
endmodule
