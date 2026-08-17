#!/usr/bin/env python3
"""Fix the OpenClash release 'ipk' for OpenWrt ImageBuilder.

The GitHub asset is actually: gzip( tar{ ./debian-binary, ./data.tar.gz, ./control.tar.gz } )
Its control.tar.gz carries a postinst that fails inside the ImageBuilder rootfs
(baked host paths, missing default_postinst). This script:
  1. gunzips the wrapper if needed
  2. parses the tar container manually (non-standard, no ustar magic)
  3. neutralizes ./postinst inside control.tar.gz
  4. rebuilds a standard ar-format .ipk (debian-binary / control.tar.gz / data.tar.gz)
"""
import gzip, io, os, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else 'luci-app-openclash_0.47.156_all.ipk'
data = open(SRC, 'rb').read()

# 1) gunzip wrapper
if data[:2] == b'\x1f\x8b':
    data = gzip.decompress(data)

def parse_tar(buf):
    entries = []
    off = 0
    while off + 512 <= len(buf):
        name = buf[off:off+100].split(b'\x00')[0].decode('utf-8', 'replace')
        size = int(buf[off+124:off+136].strip() or b'0', 8)
        if not name:
            break
        typ = chr(buf[off+156] or 48)
        entries.append((name, typ, buf[off+512:off+512+size]))
        off += 512 + ((size + 511) // 512) * 512
    return entries

def write_tar(entries):
    out = io.BytesIO()
    for name, typ, body in entries:
        h = bytearray(512)
        h[0:100] = name.encode('utf-8')[:100].ljust(100, b'\x00')
        h[100:108] = b'0000644\x00'
        h[108:116] = b'0000000\x00'
        h[116:124] = b'0000000\x00'
        h[124:136] = ('%011o' % len(body)).encode() + b'\x00'
        h[136:148] = b'00000000000\x00'
        h[148:156] = b' ' * 8
        h[156] = ord(typ)
        h[257:263] = b'ustar\x00'
        h[263:265] = b'00'
        h[265:269] = b'root'
        h[297:301] = b'root'
        chk = sum(h)
        h[148:156] = ('%06o' % chk).encode() + b'\x00 '
        out.write(bytes(h))
        pad = ((len(body) + 511) // 512) * 512
        out.write(body + b'\x00' * (pad - len(body)))
    out.write(b'\x00' * 1024)
    return out.getvalue()

# 2) parse tar container
container = parse_tar(data)
print('container:', [(n, t) for n, t, _ in container])
by_name = {n: (t, b) for n, t, b in container}
debian = by_name['./debian-binary'][1]
data_tar = by_name['./data.tar.gz'][1]
ctrl_tar = by_name['./control.tar.gz'][1]

# 3) neutralize postinst inside control.tar.gz
ctrl_entries = parse_tar(gzip.decompress(ctrl_tar))
fixed = []
for name, typ, body in ctrl_entries:
    if name.endswith('postinst'):
        body = b'#!/bin/sh\nexit 0\n'
        typ = '0'
    fixed.append((name, typ, body))
new_ctrl = gzip.compress(write_tar(fixed))
print('control.tar.gz:', len(ctrl_tar), '->', len(new_ctrl))

# 4) rebuild standard ar ipk
def ar_member(name, body):
    nm = (name + '/').encode()[:16].ljust(16, b' ')
    hdr = nm + b'0'*12 + b'0'*6 + b'0'*6 + b'100644  '
    hdr += str(len(body)).encode().rjust(10, b' ')
    hdr += b'`\n'
    assert len(hdr) == 60, len(hdr)
    out = hdr + body
    if len(body) % 2:
        out += b'\n'
    return out

ipk = b'!<arch>\n' + ar_member('debian-binary', debian) + ar_member('control.tar.gz', new_ctrl) + ar_member('data.tar.gz', data_tar)
open(SRC, 'wb').write(ipk)
print('fixed ipk written:', os.path.getsize(SRC), 'bytes')
