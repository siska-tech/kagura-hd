"""Optional KFB ABI 1.4 PCM2-only facade. One caller; never replay uncertain writes."""

class Audio:
    def __init__(self, device):
        self.device = device
        identity = device.transport.read(0, True, 7)
        if identity[:4] != b'KFB1' or identity[4] != 1 or identity[5] < 4 or not identity[6] & 128:
            raise ValueError('audio CSR requires KFB ABI 1.4 PCM2 and AUDIO_CSR capability')

    @staticmethod
    def _byte(value):
        if not isinstance(value, int) or not 0 <= value <= 255:
            raise ValueError('audio value must be a byte')
        return value

    def _check(self):
        error = self.device._read(7)
        if error:
            raise OSError(error, 'device error; no automatic retry')

    def clear_error(self):
        self.device._write(7, 0)

    def _index(self, value):
        value = self._byte(value)
        if value < 0x60:
            raise ValueError('synthesized-voice indices are unsupported in PCM2-only profile')
        return value

    def read(self, index):
        self.device._write(54, self._index(index))
        value = self.device._read(55)
        self._check()
        return value

    def write(self, index, value):
        index, value = self._index(index), self._byte(value)
        self._check()
        self.device.transport.write(54, True, bytes((index, value)))
        self._check()

    def status(self):
        return self.read(0xe1)

    def commit(self, wait=True):
        self._check()
        command = bytearray(16)
        command[0] = 7
        tag = self.device.submit(command)
        if wait:
            self.wait(tag)
        return tag

    def wait(self, tag):
        self.device.wait(tag)

    def channel(self, *args, **kwargs):
        raise NotImplementedError('PCM2-only profile has no synthesized voices')

    def master(self, gain):
        self.write(224, self._byte(gain))

    @staticmethod
    def _pcm_base(channel):
        if not isinstance(channel, int) or channel not in (0, 1):
            raise ValueError('PCM channel must be 0 or 1')
        return 0x60 + channel*0x20

    def pcm_status(self, channel):
        return self.read(self._pcm_base(channel)+15)

    def pcm_configure(self, channel, start, end, loop=None, gain_left=0, gain_right=0, enabled=False):
        base = self._pcm_base(channel)
        if not all(isinstance(x, int) for x in (start, end)) or not 0 <= start < end <= 0x3fffff:
            raise ValueError('PCM range is byte-addressed; exclusive 0x400000 is not representable')
        if loop is not None and (not isinstance(loop, int) or not start <= loop < end):
            raise ValueError('PCM loop outside range')
        gain_left, gain_right = self._byte(gain_left), self._byte(gain_right)
        if self.pcm_status(channel) & 0x42:
            raise OSError(1, 'stop PCM and wait before changing its configuration')
        for offset, address in ((0, start), (4, end), (8, start if loop is None else loop)):
            for i in range(3):
                self.write(base+offset+i, address >> (i*8) & 255)
        self.write(base+12, gain_left)
        self.write(base+13, gain_right)
        self.write(base+14, int(bool(enabled)) | (2 if loop is not None else 0))

    def pcm_prepare(self, channel, wait=True):
        self.write(self._pcm_base(channel)+15, 1)
        if wait:
            started = self.device._now()
            while True:
                status = self.pcm_status(channel)
                if status & 0x38:
                    raise OSError(status, 'PCM prepare fault')
                if status & 1:
                    return status
                if self.device._expired(started):
                    raise OSError(110, 'PCM prepare timeout; no automatic retry')

    def pcm_stop(self, channel):
        self.write(self._pcm_base(channel)+15, 2)

    def pcm_enable(self, channel, enabled=True):
        index = self._pcm_base(channel)+14
        control = self.read(index)
        self.write(index, (control & 2) | int(bool(enabled)))

    def pcm_clear(self, channel):
        self.write(self._pcm_base(channel)+15, 4)
