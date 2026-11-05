"""Fail-closed raw REPL transaction helper; caller establishes the session.

Recovery must open a separate session after this instance has closed. Never
replay a sent key, including after exceptions or a device-side traceback.
"""
import time


class RawSession:
    def __init__(self, port, clock=time.monotonic, pause=time.sleep, should_abort=lambda: False):
        self.port, self.clock, self.pause = port, clock, pause
        self.should_abort = should_abort
        self.failed = False
        self.sent = set()
        self.raw = bytearray()

    def _until(self, marker, deadline):
        data=bytearray()
        while not data.endswith(marker):
            if self.should_abort():
                raise TimeoutError('external stop; no replay')
            if self.clock() >= deadline:
                raise TimeoutError('raw receive deadline; session closed; no replay')
            value=self.port.read(1)
            data.extend(value)
            self.raw.extend(value)  # Includes partial stdout if the deadline expires.
        return bytes(data)

    def transfer(self, key, source, seconds=120):
        if self.failed:
            raise RuntimeError('failed session: recovery requires a fresh connection')
        if key in self.sent:
            raise RuntimeError('no replay')
        if b'\x04' in source or seconds <= 0:
            raise ValueError('invalid source or timeout')
        self.sent.add(key)
        self.raw=bytearray()
        deadline=self.clock()+seconds
        try:
            for offset in range(0,len(source),192):
                if self.should_abort():
                    raise TimeoutError('external stop during send')
                if self.clock() >= deadline:
                    raise TimeoutError('raw send deadline')
                block=source[offset:offset+192]
                if self.port.write(block) != len(block):
                    raise OSError('short serial write')
                self.pause(.01)
            if self.port.write(b'\x04') != 1:
                raise OSError('short delimiter write')
            ack=self._until(b'OK',deadline)
            if ack!=b'OK':
                raise ValueError('unexpected raw acknowledgement')
            stdout=self._until(b'\x04',deadline)[:-1]
            stderr=self._until(b'\x04',deadline)[:-1]
            if self._until(b'>',deadline)!=b'>':
                raise ValueError('unexpected raw prompt')
            if stderr:
                raise RuntimeError(stderr.decode(errors='replace'))
            return stdout
        except BaseException:
            self.failed=True
            try:
                self.port.write(b'\x03\x03')  # Interrupt once; never send another job.
            except Exception:
                pass
            finally:
                self.port.close()
            raise
