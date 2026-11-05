"""PC-side readback planning/validation. Importing this never opens a device."""
import json
import zlib

PAGE_BYTES = 115200
SEGMENT_BYTES = 512
TRANSFER_BYTES = 64
JOB_SECONDS = 120


def segments(page):
    if page not in (0, 1):
        raise ValueError('framebuffer page')
    return [(page * PAGE_BYTES + offset, min(SEGMENT_BYTES, PAGE_BYTES-offset))
            for offset in range(0, PAGE_BYTES, SEGMENT_BYTES)]


def source(test_id, address, length):
    if length <= 0 or length > SEGMENT_BYTES or address % 64 or length % 64:
        raise ValueError('aligned finite segment required')
    if address < 0 or address + length > 2 * PAGE_BYTES:
        raise ValueError('framebuffer range')
    # Only 64B receive storage plus <=512B evidence, no new full host framebuffer.
    return '''_seg_buf=bytearray(64)
_seg_hex=[]
_seg_t0=time.ticks_us()
for _seg_addr in range(%d,%d,64):
 _dev.read_into(_seg_addr,_seg_buf)
 _seg_hex.append(binascii.hexlify(_seg_buf).decode())
_sc({'event':'readback_segment','id':%r,'address':%d,'length':%d,
 'actual':''.join(_seg_hex),'elapsed_us':time.ticks_diff(time.ticks_us(),_seg_t0)})
del _seg_hex,_seg_buf
''' % (address, address+length, test_id, address, length)


class Validator:
    """Strict ordered transcript; independent expected bytes, first error latches."""
    def __init__(self, test_id, page, expected):
        if len(expected) != PAGE_BYTES:
            raise ValueError('complete PC oracle page required')
        self.test_id, self.page, self.expected = test_id, page, expected
        self.next = 0
        self.crc = 0
        self.failed = False
        self.records = []

    def accept(self, record):
        if self.failed:
            raise RuntimeError('failure latched; no further readback accepted')
        try:
            if self.next >= PAGE_BYTES:
                raise ValueError('duplicate after completion')
            address = self.page * PAGE_BYTES + self.next
            length = min(SEGMENT_BYTES, PAGE_BYTES-self.next)
            if (record['event'], record['id'], record['address'], record['length']) != (
                    'readback_segment', self.test_id, address, length):
                raise ValueError('missing, duplicate or out-of-order segment')
            actual = bytes.fromhex(record['actual'])
            if len(actual) != length or record['elapsed_us'] < 0:
                raise ValueError('malformed measurement')
            expected = self.expected[self.next:self.next+length]
            xor = bytes(a ^ b for a, b in zip(expected, actual))
            result = dict(record, expected=expected.hex(), xor=xor.hex(),
                          error_byte_positions=[address+i for i, x in enumerate(xor) if x],
                          crc32=zlib.crc32(actual) & 0xffffffff)
            self.records.append(result)  # Preserve the failing data before raising.
            if actual != expected:
                raise ValueError('framebuffer byte mismatch')
            self.crc = zlib.crc32(actual, self.crc) & 0xffffffff
            self.next += length
            return result
        except Exception:
            self.failed = True
            raise

    def finish(self):
        if self.failed or self.next != PAGE_BYTES:
            raise ValueError('incomplete or failed readback')
        assert self.crc == zlib.crc32(self.expected) & 0xffffffff
        return self.crc


def write_jobs(directory, test_id, page, expected):
    validator = Validator(test_id, page, expected)
    del validator
    directory.mkdir(parents=True, exist_ok=False)
    manifest = []
    for index, (address, length) in enumerate(segments(page)):
        filename = '%s-p%d-%03d.py' % (test_id, page, index)
        (directory/filename).write_text(source(test_id, address, length), encoding='utf-8')
        offset = address-page*PAGE_BYTES
        manifest.append(dict(job=filename, address=address, length=length,
                             timeout_seconds=JOB_SECONDS,
                             expected=expected[offset:offset+length].hex()))
    (directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest
