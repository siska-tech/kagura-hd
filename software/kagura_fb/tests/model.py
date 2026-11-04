# SPDX-License-Identifier: Apache-2.0
class Model:
    def __init__(self):
        self.memory = bytearray(b"\xa5" * 4194304)
        self.stage = bytearray(16)
        self.data = bytearray(64)
        self.pointer = 0
        self.tag = 65535
        self.error = 0
        self.sticky = 0
        self.completed = False
        self.pending = None
        self.polls = 0
        self.clock = 0xfffffffe
        self.commands = []
        self.palette = list(range(16))
        self.active_palette = None
        self.page = None
        self.identity = b"KFB1\x01\x00\x1f"
        self.hold = False
        self.lost_done = False
        self.late = False
        self.force_error = 0
        self.fail_submit = False

    def now(self):
        value = self.clock
        self.clock = (value + 1) & 0xffffffff
        return value

    def finish(self):
        command, data = self.pending
        self.pending = None
        op, argument = command[:2]
        self.tag = int.from_bytes(command[2:4], "little")
        self.error = self.force_error
        self.force_error = 0
        if not self.error:
            if op == 1:
                x, y, width, height = [int.from_bytes(command[i:i + 2], "little") for i in (4, 6, 8, 10)]
                assert argument <= 1 and x + width <= 640 and y + height <= 360
                for row in range(y, y + height):
                    for col in range(x, x + width):
                        address = argument * 115200 + row * 320 + col // 2
                        shift = 4 if col % 2 == 0 else 0
                        self.memory[address] = (self.memory[address] & ~(15 << shift)) | (command[12] << shift)
            elif op == 6:
                assert self.identity[6] & 64 and argument <= 3
                sx, sy, dx, dy, width, height = [int.from_bytes(command[i:i + 2], "little") for i in (4, 6, 8, 10, 12, 14)]
                assert sx < 640 and dx < 640 and sy < 360 and dy < 360
                assert max(sx, dx) + width <= 640 and max(sy, dy) + height <= 360
                assert not ((sx | dx | width) & 1) and not ((sx ^ dx) & 7)
                original = bytes(self.memory[:230400])
                for row in range(height):
                    for col in range(width):
                        src = (argument & 1) * 115200 + (sy + row) * 320 + (sx + col) // 2
                        dst = ((argument >> 1) & 1) * 115200 + (dy + row) * 320 + (dx + col) // 2
                        shift = 4 if (dx + col) % 2 == 0 else 0
                        value = (original[src] >> (4 if (sx + col) % 2 == 0 else 0)) & 15
                        self.memory[dst] = (self.memory[dst] & ~(15 << shift)) | (value << shift)
            elif op == 2:
                self.palette[argument] = int.from_bytes(command[4:6], "little")
            elif op == 3:
                self.page = argument
                self.active_palette = list(self.palette)
            elif op in (4, 5):
                address = int.from_bytes(command[4:8], "little")
                assert address % 4 == 0 and 1 <= argument <= 16
                size = argument * 4
                if op == 4:
                    mask = int.from_bytes(command[8:16], "little")
                    for offset in range(size):
                        if not (mask >> offset) & 1:
                            self.memory[address + offset] = data[offset]
                else:
                    self.data[:] = bytes(64)
                    self.data[:size] = self.memory[address:address + size]
                    self.pointer = 0
            else:
                assert op == 0
        self.sticky = self.error
        self.completed = not self.lost_done

    def read(self, address, increment, length):
        result = bytearray()
        for _ in range(length):
            if address == 27:
                if self.pending and not self.hold:
                    self.polls -= 1
                    if self.polls == 0:
                        self.finish()
                # lost_done models a reset/stale tag without a completion flag.
                value = 2 | (1 if self.pending else 0) | (16 if self.completed else 0) | (128 if self.late else 0)
            elif address < 7:
                value = self.identity[address]
            elif address == 7:
                value = self.sticky
            elif address == 24:
                assert not self.pending and self.pointer < 64
                value = self.data[self.pointer]
                self.pointer += 1
            elif address == 28:
                value = self.tag & 255
            elif address == 29:
                value = self.tag >> 8
            elif address == 30:
                value = self.error
            else:
                raise AssertionError((address, length))
            result.append(value)
            if increment:
                address += 1
        return result

    def write(self, address, increment, data):
        for value in data:
            if address == 7:
                self.sticky = 0
            elif address == 31:
                self.completed = False
            else:
                assert self.pending is None, "driver staged data while command busy"
                if 8 <= address < 24:
                    self.stage[address - 8] = value
                elif address == 24:
                    assert self.pointer < 64
                    self.data[self.pointer] = value
                    self.pointer += 1
                elif address == 25:
                    self.pointer = value
                elif address == 26:
                    assert value == 1
                    command = bytes(self.stage)
                    self.commands.append(command)
                    self.pending = (command, bytes(self.data))
                    self.polls = 3
                    self.completed = False
                    if self.fail_submit:
                        self.fail_submit = False
                        raise OSError("submission acknowledgement lost")
                else:
                    raise AssertionError(address)
            if increment:
                address += 1



class CursorModel(Model):
    """Behavioral cursor banks and vblank events, independent of GPU commands."""
    def __init__(self):
        super().__init__()
        self.identity = b"KFB1\x01\x01\x3f"
        self.cursor_stage = bytearray(5)
        self.cursor_assets = [bytearray(256), bytearray(256)]
        self.cursor_palettes = [bytearray(6), bytearray(6)]
        self.cursor_hotspots = [bytearray(2), bytearray(2)]
        self.cursor_valid = [False, False]
        self.cursor_loaded = [0, 0]
        self.cursor_bank = 0
        self.cursor_visible = False
        self.cursor_edit = 1
        self.cursor_offset = 0
        self.cursor_pending = None
        self.cursor_queued = None
        self.cursor_position = None
        self.cursor_generation = 0
        self.cursor_high = 0
        self.cursor_error = 0
        self.cursor_completed = False
        self.cursor_auto = True
        self.cursor_polls = 0
        self.cursor_submissions = []
        self.cursor_fail_submit = False

    def cursor_locked(self):
        return (self.cursor_edit == self.cursor_bank
                or self.cursor_pending is not None and self.cursor_pending[2] == self.cursor_edit
                or self.cursor_queued is not None and self.cursor_queued[2] == self.cursor_edit)

    def cursor_vblank(self):
        if self.cursor_pending is not None:
            pose = self.cursor_pending
            self.cursor_position = pose
            self.cursor_bank, self.cursor_visible = pose[2], pose[3]
            self.cursor_generation = (self.cursor_generation + 1) & 65535
            self.cursor_completed = True
            self.cursor_pending = self.cursor_queued
            self.cursor_queued = None

    def cursor_read(self, address):
        if address == 50:
            if self.cursor_auto:
                self.cursor_polls += 1
                if self.cursor_polls % 3 == 0:
                    self.cursor_vblank()
            return (bool(self.cursor_pending) | (self.cursor_bank << 1) | (int(self.cursor_visible) << 2)
                    | (int(self.cursor_queued is not None) << 3) | (int(self.cursor_valid[0]) << 4)
                    | (int(self.cursor_valid[1]) << 5) | (int(self.cursor_completed) << 6))
        if address == 51:
            self.cursor_high = self.cursor_generation >> 8
            return self.cursor_generation & 255
        if address == 52:
            return self.cursor_high
        if address == 53:
            return self.cursor_error
        return 0

    def cursor_write(self, address, value):
        error = 0
        if 32 <= address <= 36:
            if address == 32 and value > 3:
                error = 2
            else:
                self.cursor_stage[address - 32] = value
        elif address in (37, 38) or 39 <= address <= 44 or address == 48:
            if self.cursor_locked():
                error = 1
            elif address in (37, 38):
                if value > 31:
                    error = 3
                else:
                    self.cursor_hotspots[self.cursor_edit][address - 37] = value
            elif 39 <= address <= 44:
                if address % 2 == 0 and value > 15:
                    error = 3
                else:
                    self.cursor_palettes[self.cursor_edit][address - 39] = value
            elif self.cursor_offset >= 256:
                error = 5
            elif self.cursor_offset != 0 and self.cursor_offset != self.cursor_loaded[self.cursor_edit]:
                error = 2
            else:
                if self.cursor_offset == 0:
                    self.cursor_valid[self.cursor_edit] = False
                self.cursor_assets[self.cursor_edit][self.cursor_offset] = value
                self.cursor_offset += 1
                self.cursor_loaded[self.cursor_edit] = self.cursor_offset
                self.cursor_valid[self.cursor_edit] = self.cursor_offset == 256
        elif address == 46:
            self.cursor_offset = value
        elif address == 47:
            if value > 1:
                error = 3
            else:
                self.cursor_edit = value
                self.cursor_offset &= 255
        elif address == 49:
            control = self.cursor_stage[0]
            x = self.cursor_stage[1] | (self.cursor_stage[2] << 8)
            y = self.cursor_stage[3] | (self.cursor_stage[4] << 8)
            if x >= 32768:
                x -= 65536
            if y >= 32768:
                y -= 65536
            bank, visible = control >> 1, bool(control & 1)
            if value != 1:
                error = 2
            elif not -1024 <= x <= 1023 or not -1024 <= y <= 1023:
                error = 3
            elif visible and not self.cursor_valid[bank]:
                error = 7
            else:
                pose = (x, y, bank, visible)
                self.cursor_submissions.append(pose)
                if self.cursor_pending is None:
                    self.cursor_pending = pose
                else:
                    self.cursor_queued = pose
                if self.cursor_fail_submit:
                    self.cursor_fail_submit = False
                    raise OSError("cursor acknowledgement lost")
        elif address == 50:
            if value & 64:
                self.cursor_completed = False
        elif address == 53:
            self.cursor_error = 0
        else:
            error = 2
        if error and not self.cursor_error:
            self.cursor_error = error

    def read(self, address, increment, length):
        if address < 32:
            return super().read(address, increment, length)
        result = bytearray()
        for _ in range(length):
            result.append(self.cursor_read(address))
            if increment:
                address = (address + 1) & 63
        return result

    def write(self, address, increment, data):
        if address < 32:
            return super().write(address, increment, data)
        for value in data:
            self.cursor_write(address, value)
            if increment:
                address = (address + 1) & 63


class BlitModel(CursorModel):
    def __init__(self):
        super().__init__()
        self.identity = b"KFB1\x01\x02\x7f"
