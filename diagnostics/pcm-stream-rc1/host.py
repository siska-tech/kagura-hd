"""Reference host for the RC1 trial, with one 64-byte staging buffer.

The two sources implement readinto() and supply planar signed PCM8 at 48 kHz.
The caller serializes this helper and drawing on the same device.
"""

HALF = 4096
CONTROL = 0xE3
TOKEN = 0xE4
STATUS = 0xE5


class StereoStream:
    def __init__(self, audio, left, right, base=0x40000):
        if base < 0x40000 or base % (2 * HALF) or base + 4 * HALF >= 0x400000:
            raise ValueError('reserve four aligned halves in PSRAM')
        self.audio = audio
        self.device = audio.device
        self.sources = (left, right)
        self.bases = (base, base + 2 * HALF)
        self.buffer = memoryview(bytearray(64))

    def _fill(self, half):
        for source, base in zip(self.sources, self.bases):
            address = base + half * HALF
            for offset in range(0, HALF, len(self.buffer)):
                used = 0
                while used < len(self.buffer):
                    size = source.readinto(self.buffer[used:])
                    if not size:
                        raise EOFError('PCM source ended mid-stream')
                    used += size
                self.device.write_bytes(address + offset, self.buffer)

    def stop(self):
        self.audio.write(CONTROL, 0)
        started = self.device._now()
        while self.audio.read(STATUS) & 6:
            if self.device._expired(started):
                raise OSError(110, 'PCM stop drain timed out')

    def start(self, gain=255, master=255):
        if self.audio.read(CONTROL) != 0x51:
            raise ValueError('RC1 streaming trial required')
        self.stop()
        for channel, base in enumerate(self.bases):
            self.audio.pcm_stop(channel)
            self.audio.pcm_clear(channel)
            self.audio.pcm_configure(channel, base, base + 2 * HALF, loop=base,
                                     gain_left=gain if channel == 0 else 0,
                                     gain_right=gain if channel == 1 else 0,
                                     enabled=True)
        self._fill(0)
        self._fill(1)
        self.device.fence()
        self.audio.master(master)
        self.audio.write(CONTROL, 1)
        if not self.audio.read(STATUS) & 2:
            raise OSError(1, 'PCM stream arm rejected')
        self.audio.pcm_prepare(0, wait=False)
        self.audio.pcm_prepare(1, wait=False)
        started = self.device._now()
        while True:
            left = self.audio.pcm_status(0)
            right = self.audio.pcm_status(1)
            if (left | right) & 0x38:
                raise OSError(1, 'PCM stream prepare fault')
            if left & right & 1:
                break
            if self.device._expired(started):
                raise OSError(110, 'PCM stream prepare timed out')
        self.audio.commit()

    def refill(self):
        """Refill one returned half. Call ahead of drawing work."""
        status = self.audio.read(STATUS)
        if not status & 2:
            raise OSError(1, 'PCM stream stopped or faulted')
        if not status & 1:
            return False
        token = self.audio.read(TOKEN)
        self._fill(token & 1)
        self.audio.write(TOKEN, token)
        if not self.audio.read(STATUS) & 2 or self.audio.read(TOKEN) == token:
            raise OSError(1, 'PCM refill publication rejected')
        return True
