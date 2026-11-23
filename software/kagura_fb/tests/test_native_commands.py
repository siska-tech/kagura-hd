# SPDX-License-Identifier: Apache-2.0
"""Run the exact portable runtime regression with direct-native overrides."""
import kagura_fb
from kagura_native_commands import NativeDevice
PortableDevice = kagura_fb.Device
kagura_fb.Device = NativeDevice
with open('software/kagura_fb/tests/test_micropython.py') as source:
    exec(source.read())
assert NativeDevice.accelerated
print('direct NativeDevice regression PASS')

# Exercise the NativeDevice dispatch boundary too, including errors and tags.
# The actual Viper register sequence is separately tested by test_gpu_kernel.py.
import model
fast_calls = [0]
def exchange(self, command, payload, timeout_ms):
    fast_calls[0] += 1
    proxy = PortableDevice(self, timeout_ms, self.now)
    proxy._tag = command[2] | command[3] << 8
    try:
        proxy._execute(command, payload)
    except OSError:
        if proxy.last_device_error:
            return proxy.last_device_error
        raise
    return 0
model.Model.execute_command = exchange
with open('software/kagura_fb/tests/test_micropython.py') as source:
    exec(source.read())
assert fast_calls[0] > 0
print('NativeDevice fused dispatch regression PASS')
