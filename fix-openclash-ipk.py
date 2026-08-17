#!/usr/bin/env python3
"""Extract the OpenClash release 'ipk' contents into an overlay directory.

The GitHub asset is: gzip( tar{ ./debian-binary, ./data.tar.gz, ./control.tar.gz } )
We extract ./data.tar.gz and write its entries into ./openclash-files/ so the
OpenWrt ImageBuilder FILES= overlay can bake them directly into the rootfs
(no opkg package install, no postinst, no package index needed).
"""
import gzip, io, os, sys, shutil

SRC = sys.argv[1] if len(sys.argv) > 1 else 'luci-app-openclash_0.47.156_all.ipk'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'openclash-files'
data = open(SRC, 'rb').read()

if data[:2] == b'\x1f\x8b':
    data = gzip.decompress(data)

def parse_tar(buf):
    entries = []
    off = 0
    while off + 512 <= len(buf):
        name = buf[off:off+100].split(b'\x00')[0].decode('utf-8', 'replace')
        size = int(buf[off+124:off+136].split(b'\x00')[0].strip() or b'0', 8)
        if not name:
            break
        typ = chr(buf[off+156] or 48)
        entries.append((name, typ, buf[off+512:off+512+size]))
        off += 512 + ((size + 511) // 512) * 512
    return entries

container = parse_tar(data)
print('container:', [(n, t) for n, t, _ in container])
data_tar = next(b for n, t, b in container if 'data.tar.gz' in n)

# 解出 data.tar.gz 的条目
entries = parse_tar(gzip.decompress(data_tar))
print('data entries:', len(entries), 'e.g.', [n for n, _, _ in entries[:6]])

if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)

for name, typ, body in entries:
    rel = name.lstrip('./')
    if not rel:
        continue
    dst = os.path.join(OUT, rel)
    if typ == '5' or name.endswith('/'):  # directory
        os.makedirs(dst, exist_ok=True)
        continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'wb') as f:
        f.write(body)
    # 可执行文件保持可执行
    if typ == '2':  # symlink
        try:
            target = body.decode('utf-8')
            if os.path.lexists(dst):
                os.remove(dst)
            os.symlink(target, dst)
        except OSError as e:
            print('symlink skip:', rel, e)

# 确保 /etc/openclash 存在
os.makedirs(os.path.join(OUT, 'etc', 'openclash'), exist_ok=True)
open(os.path.join(OUT, 'etc', 'openclash', '.keep'), 'w').close()

total = sum(len(b) for _, _, b in entries)
print('extracted to', OUT, '| total bytes:', total)
