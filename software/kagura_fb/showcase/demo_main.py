# SPDX-License-Identifier: Apache-2.0
"""No auto-connect or import side effects. Future qualified RAM-only Host entry."""
from .gpu_api_adapter import GPU,BITSTREAM_SHA256
from .scene_manager import Demo
from .diagnostics import Diagnostics,collect,heap_stats

def run_on_device(device, *, qualified_bitstream_sha256, hardware_qualified=False,
                  cycles=1, verify_reads=False, sink=None, interval_us=125000, should_stop=None):
    # This is an operator-provided qualification assertion, not a SHA CSR read.
    # No commands are sent if qualification is absent.
    if not hardware_qualified or qualified_bitstream_sha256!=BITSTREAM_SHA256:
        raise RuntimeError('PSRAM/hardware qualification and explicit matching Bitstream SHA required')
    collect()
    _,free=heap_stats()
    if free is not None and free<65536:raise MemoryError('need 64KiB free heap after loading; no GPU commands sent')
    from kagura_fb_audio import Audio
    if sink is None:
        try: import json
        except ImportError: import ujson as json
        sink=lambda record:print(json.dumps(record))
    gpu=GPU(device,Audio(device),Diagnostics(sink),verify=verify_reads)
    Demo(gpu,interval_us).run(cycles,should_stop=should_stop)
