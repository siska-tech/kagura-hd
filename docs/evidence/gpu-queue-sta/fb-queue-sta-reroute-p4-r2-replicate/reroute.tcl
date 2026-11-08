set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
add_file -type netlist [file join [pwd] impl gwsynthesis kagura_fb.vg]
add_file -type cst [file join [pwd] kagura_fb.cst]
add_file -type sdc [file join [pwd] kagura-fb.sdc]
set_option -top_module kagura_fb_top
set_option -output_base_name kagura_fb
set_option -timing_driven 1
set_option -place_option 4
set_option -route_option 2
set_option -replicate_resources 1
set_option -retiming_resource none
foreach feature {sspi mspi ready done cpu} { set_option -use_${feature}_as_gpio 1 }
run pnr
