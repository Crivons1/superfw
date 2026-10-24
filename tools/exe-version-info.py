#!/usr/bin/env python3
# Writes the Windows version resource for make-covers.exe (PyInstaller
# --version-file). Code signing (SignPath) requires the product name and
# version in the signed file. The version comes from VERSION in make-covers.py.
#
# Usage: exe-version-info.py <output file>

import os, re, sys

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "make-covers.py"), encoding="utf-8").read()
ver = re.search(r'^VERSION = "(\d+)\.(\d+)\.(\d+)"', src, re.M).groups()
nums = tuple(int(v) for v in ver) + (0,)
text = ".".join(str(n) for n in nums)

open(sys.argv[1], "w", encoding="utf-8").write("""VSVersionInfo(
  ffi=FixedFileInfo(filevers=%(nums)r, prodvers=%(nums)r, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'SuperFW carousel fork'),
      StringStruct('FileDescription', 'SuperFW cover maker'),
      StringStruct('FileVersion', '%(text)s'),
      StringStruct('InternalName', 'make-covers'),
      StringStruct('LegalCopyright', 'GPL-3.0-or-later'),
      StringStruct('OriginalFilename', 'make-covers.exe'),
      StringStruct('ProductName', 'SuperFW cover maker'),
      StringStruct('ProductVersion', '%(text)s')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""" % {"nums": nums, "text": text})
print("version", text)
