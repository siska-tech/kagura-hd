"""Host-owned patterns/absolute chunk plan. Offline only, no transport."""
import random

FIXED = ('00000000', 'ffffffff', 'aa55aa55', '55aa55aa',
         'ed0f2143', '43210fed', '12345678')

def pattern(name, address, length, seed=0x4B414755):
    if name in FIXED:
        return (bytes.fromhex(name) * ((length+3)//4))[:length]
    if name == 'walking1':
        return bytes(1 << (i % 8) for i in range(length))
    if name == 'walking0':
        return bytes(255 ^ (1 << (i % 8)) for i in range(length))
    if name == 'address':
        return bytes(((address+i)*37+((address+i)>>8)*17+29) & 255 for i in range(length))
    if name == 'random':
        rng = random.Random(seed)
        return bytes(rng.randrange(256) for _ in range(length))
    raise ValueError(name)

def chunks(address, length):
    if length not in (4, 8, 16, 32, 64) or address % 4 or address < 0 or address+length > 4194304:
        raise ValueError('invalid diagnostic range')
    result = []
    while length:
        size = min(length, 32-address % 32)
        # Independent CA construction: rd is selected by the caller, CA45 is
        # observed production behavior, not a claim about the unknown die.
        halfword = address//2
        ca_write = (1 << 45) | ((halfword >> 3) << 16) | (halfword & 7)
        result.append(dict(address=address, length=size, ca_write=f'{ca_write:012x}',
                           ca_read=f'{ca_write | (1 << 47):012x}'))
        address += size
        length -= size
    return result

def guards(address, length):
    # Physically distinct 32B blocks, never the target's wrap alias.
    before = address//32*32-32
    after = (address+length+31)//32*32
    return [a for a in (before, after) if 0 <= a <= 4194300]

if __name__ == '__main__':
    import json
    addresses = [300032+4*i for i in range(8)] + [300064, 300092, 1048576, 4194240]
    cases = []
    for address in addresses:
        for length in (4, 8, 16, 32, 64):
            if address+length > 4194304:
                continue
            for name in (*FIXED, 'walking1', 'walking0', 'address', 'random'):
                cases.append(dict(test_id=f'ISO-{address}-{length}-{name}', address=address,
                    length=length, expected=pattern(name,address,length).hex(),
                    chunks=chunks(address,length), guards=[dict(address=g,
                    expected=pattern('address',g,4).hex()) for g in guards(address,length)]))
    print(json.dumps(dict(executable=False, release_ready=False, cases=cases), indent=2))
