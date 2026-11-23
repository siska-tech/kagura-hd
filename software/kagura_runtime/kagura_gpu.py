# SPDX-License-Identifier: Apache-2.0
"""Application-independent GPU ownership, framebuffer operations and REPL handoff."""


class Device:
    def __init__(self, backend=None):
        if backend is None:
            import _kagura
            backend = _kagura
        self.backend = backend
        self._opened = False
        self._previous_frequency = self._console = None
        self.cleanup_error = None

    def _open_backend(self):
        self.backend.display_open()

    def __enter__(self):
        import gc
        import machine
        import sys
        if self._previous_frequency is not None:
            raise RuntimeError('device already entered')
        self._previous_frequency = machine.freq()
        try:
            repl = sys.modules.get('kagura_repl')
            active = getattr(repl, 'console', None) if repl is not None else None
            if active is not None and not active._closed and active._display_owned:
                self._console = active
                active.suspend()
            gc.collect()
            machine.freq(120000000)
            self._open_backend()
            self._opened = True
            return self
        except BaseException:
            try:
                self.close()
            except Exception as error:
                self.cleanup_error = error
            raise

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.close()
        except Exception as error:
            self.cleanup_error = error
            if exc_type is None:
                raise
        return False

    def close(self):
        import machine
        try:
            if self._opened:
                self._opened = False
                self.backend.close()
        finally:
            if self._previous_frequency is not None:
                previous, self._previous_frequency = self._previous_frequency, None
                machine.freq(previous)
            if self._console is not None:
                console, self._console = self._console, None
                console.resume()

    def _require_open(self):
        if not self._opened:
            raise RuntimeError('use the device in a with block')

    def fill_rect(self, *args): self._require_open(); return self.backend.fill(*args)
    def copy_rect(self, *args): self._require_open(); return self.backend.copy(*args)
    def write_bytes(self, *args): self._require_open(); return self.backend.write(*args)
    def read_into(self, *args): self._require_open(); return self.backend.read_into(*args)
    def palette(self, *args): self._require_open(); return self.backend.palette(*args)
    def present(self, *args): self._require_open(); return self.backend.present(*args)
    def fence(self): self._require_open(); return self.backend.fence()
    def bitmap(self, *args): self._require_open(); return self.backend.bitmap(*args)
    def copy_bytes(self, *args): self._require_open(); return self.backend.copy_bytes(*args)
    def glyph_run(self, *args): self._require_open(); return self.backend.glyph_run(*args)
    def service(self): self._require_open(); return self.backend.service()

    fill = fill_rect
    copy = copy_rect
    write = write_bytes
