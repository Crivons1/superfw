#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Tests for tools/make-covers.py and tools/carousel-preview.py (no network).
# Run: python3 tests/make_covers_test.py

import importlib.util, json, os, struct, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")

def load(name, fn):
  spec = importlib.util.spec_from_file_location(name, os.path.join(TOOLS, fn))
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  return mod

mc = load("make_covers", "make-covers.py")
pv = load("carousel_preview", "carousel-preview.py")

from PIL import Image

def gba_rom(path, code, title="TEST", good_checksum=True):
  h = bytearray(0xC0)
  h[0:4] = b"\x2e\x00\x00\xea"
  h[0xA0:0xAC] = title.encode().ljust(12, b"\0")
  h[0xAC:0xB0] = code.encode()
  h[0xB2] = 0x96
  h[0xBD] = (-(sum(h[0xA0:0xBD]) + 0x19)) & 0xFF
  if not good_checksum:
    h[0xBD] ^= 0xFF
  with open(path, "wb") as fd:
    fd.write(h)

BOXARTS = [
  "Pokemon - Emerald Version (USA, Europe)",
  "Pokemon - Ruby Version (USA)",
  "Pokemon - Ruby Version (Europe)",
  "Metroid Fusion (USA)",
  "Metroid Fusion (Japan)",
  "Legend of Zelda, The - The Minish Cap (USA)",
  "Dragon Ball Z - The Legacy of Goku II International (Japan)",
  "2 Games in 1 - Dragon Ball Z - The Legacy of Goku I _ II (USA)",
  "Dragon Ball GT - Transformation (USA)",
  "Super Mario Advance 4 - Super Mario Bros. 3 (USA)",
]

class NameMatching(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    # A cached (fresh) index, so ThumbIndex never touches the network.
    cls.tmp = tempfile.TemporaryDirectory()
    tree = [["Named_Boxarts/%s.png" % n, "100644"] for n in BOXARTS]
    with open(os.path.join(cls.tmp.name, "REPO.json"), "w", encoding="utf-8") as fd:
      json.dump(tree, fd)
    cls.idx = mc.ThumbIndex(cls.tmp.name)

  @classmethod
  def tearDownClass(cls):
    cls.tmp.cleanup()

  def match(self, romname):
    m = self.idx.find("REPO", romname)
    return m[0] if m else None

  def test_norm(self):
    self.assertEqual(mc.norm("1234 - Legend of Zelda, The - The Minish Cap (U)(Trashman)"),
                     "legendofzeldaminishcap")
    self.assertEqual(mc.norm("Lilo & Stitch"), mc.norm("Lilo _ Stitch (USA)"))

  def test_exact_and_normalized(self):
    self.assertEqual(self.match("Metroid Fusion (USA).gba"), "Metroid Fusion (USA)")
    self.assertEqual(self.match("Metroid Fusion (U).gba"), "Metroid Fusion (USA)")
    self.assertEqual(self.match("1190 - Super Mario Advance 4 - Super Mario Bros 3 (E)(Menace).gba"),
                     "Super Mario Advance 4 - Super Mario Bros. 3 (USA)")

  def test_region_preference(self):
    self.assertEqual(self.match("Pokemon Ruby.gba"), "Pokemon - Ruby Version (USA)")

  def test_prefix_and_suffix(self):
    # The suffix match (closer) must win over "Goku II International".
    self.assertEqual(self.match("Dragon Ball Z - The Legacy of Goku I & II (USA).gba"),
                     "2 Games in 1 - Dragon Ball Z - The Legacy of Goku I _ II (USA)")

  def test_fuzzy(self):
    self.assertEqual(self.match("Dragonball GT - Transformation # GBA.GBA"),
                     "Dragon Ball GT - Transformation (USA)")

  def test_no_match(self):
    self.assertIsNone(self.match("My Homebrew Game.gba"))

class GameCode(unittest.TestCase):
  def test_codes(self):
    with tempfile.TemporaryDirectory() as d:
      p = os.path.join(d, "rom.gba")
      gba_rom(p, "AMTE")
      self.assertEqual(mc.gba_gamecode(p), "AMTE")
      gba_rom(p, "AMTE", good_checksum=False)
      self.assertIsNone(mc.gba_gamecode(p))
      gba_rom(p, "amte")
      self.assertIsNone(mc.gba_gamecode(p))
      with open(p, "wb") as fd:
        fd.write(b"\0" * 100)            # Too short
      self.assertIsNone(mc.gba_gamecode(p))

class CoverFormat(unittest.TestCase):
  def test_roundtrip(self):
    # A wide red image: letterboxed top/bottom, red tint.
    img = Image.new("RGB", (160, 80), (220, 30, 30))
    data = mc.cover_bytes(img)
    self.assertEqual(len(data), 16 + mc.BIG * mc.BIG + mc.SMALL * mc.SMALL)
    magic, ver, big, small, pal, tint = struct.unpack_from("<IBBBBH6x", data)
    self.assertEqual((magic, ver, big, small, pal), (mc.COVER_MAGIC, 2, 80, 48, 0))
    self.assertTrue(tint & mc.TINT_VALID)

    bigimg, smallimg, t = mc.read_cover(data)
    r, g, b = t & 31, (t >> 5) & 31, (t >> 10) & 31
    self.assertGreater(r, 20)
    self.assertLess(g, 10)
    self.assertLess(b, 10)

    # Letterbox rows use the carousel background, the image the color cube.
    self.assertTrue(all(p == mc.BG_INDEX for p in bigimg[:mc.BIG * 10]))
    middle = bigimg[mc.BIG * 40:mc.BIG * 41]
    self.assertTrue(all(mc.PAL_BASE <= p < mc.PAL_BASE + 216 for p in middle))

  def test_v1_files(self):
    data = struct.pack("<IBBBB8x", mc.COVER_MAGIC, 1, 80, 48, 0) + bytes(80 * 80 + 48 * 48)
    self.assertIsNone(mc.read_cover(data)[2])

  def test_bad_files(self):
    good = mc.cover_bytes(Image.new("RGB", (10, 10), (0, 0, 255)))
    with self.assertRaises(ValueError):
      mc.read_cover(good[:-1])
    with self.assertRaises(ValueError):
      mc.read_cover(b"XXXX" + good[4:])

  def test_palette(self):
    # Must match menu_init(): 6 levels per channel, r + 6g + 36b.
    self.assertEqual(len(mc.PALETTE), 216)
    self.assertEqual(mc.PALETTE[0], (0, 0, 0))
    self.assertEqual(mc.PALETTE[215], (255, 255, 255))
    self.assertEqual(mc.PALETTE[5], (255, 0, 0))
    self.assertEqual(mc.PALETTE[30], (0, 255, 0))

class PreviewParity(unittest.TestCase):
  # Same expectations as tests/carousel_util_test.c
  def test_titles(self):
    cases = {
      "Pokemon - Emerald Version (USA, Europe).gba": "Pokemon - Emerald Version",
      "1190 - Super Mario Advance 4 - Super Mario Bros 3 (E)(Menace).gba":
        "Super Mario Advance 4 - Super Mario Bros 3",
      "007 - NightFire (USA, Europe).gba": "007 - NightFire",
      "(Hack) My Game.gba": "(Hack) My Game",
    }
    for fn, title in cases.items():
      self.assertEqual(pv.carousel_title(fn), title)

  def test_sizes_and_mix(self):
    self.assertEqual(pv.cover_size_at(0), 80)
    self.assertEqual(pv.cover_size_at(76), 48)
    self.assertTrue(all(pv.cover_size_at(d) % 4 == 0 for d in range(100)))
    self.assertEqual(pv.rgb555_mix(0, 0x7FFF, 8), 16 | (16 << 5) | (16 << 10))

if __name__ == "__main__":
  unittest.main(verbosity=2)
