#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Generates cover art files for the SuperFW carousel tab.
#
# Scans an SD card (or any folder) for game ROMs and writes one cover file per
# ROM at <sd>/.superfw/covers/<rom file name>.cov (ie. "Metroid Fusion.gba.cov").
#
# Cover images come from (in this order):
#  1. --images DIR: an image named like the ROM, with or without the ROM
#     extension (ie. "Metroid Fusion.png" or "Metroid Fusion.gba.png").
#  2. The libretro-thumbnails box art collection (downloaded, matched by name).
#
# Cover file format (all little endian):
#   uint32  magic "SFCV"
#   uint8   version (1)
#   uint8   big size (80): selected cover, square
#   uint8   small size (48): neighbour covers, square
#   uint8   palette (0): fixed 6x6x6 color cube at palette index 20
#   8 bytes reserved (zero)
#   big*big bytes, then small*small bytes: 8bpp palette indices, row-major.
#   Index 17 is the menu background color (used for letterboxing).
#
# Usage:
#   python make-covers.py E:\
#   python make-covers.py E:\ --images C:\my-covers --force
#
# Requires Pillow (pip install pillow).

import argparse, difflib, io, json, os, re, struct, sys, time
import urllib.parse, urllib.request

try:
  from PIL import Image
except ImportError:
  sys.exit("Pillow is required: pip install pillow")

COVER_MAGIC = 0x56434653
COVER_VERSION = 1
BIG, SMALL = 80, 48
PAL_BASE = 20
BG_INDEX = 17

COVERS_DIR = os.path.join(".superfw", "covers")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")

# ROM extension -> libretro-thumbnails repository. Keep in sync with the
# firmware's supported extensions (gba + emulator extensions in src/emu.c).
SYSTEMS = {
  "gba": "Nintendo_-_Game_Boy_Advance",
  "gb":  "Nintendo_-_Game_Boy",
  "gbc": "Nintendo_-_Game_Boy_Color",
  "nes": "Nintendo_-_Nintendo_Entertainment_System",
  "sms": "Sega_-_Master_System_-_Mark_III",
  "gg":  "Sega_-_Game_Gear",
  "sg":  "Sega_-_SG-1000",
  "sv":  "Watara_-_Supervision",
  "ngc": "SNK_-_Neo_Geo_Pocket_Color",
  "pce": "NEC_-_PC_Engine_-_TurboGrafx_16",
}

THUMBS_API = "https://api.github.com/repos/libretro-thumbnails/%s/git/trees/master?recursive=1"
THUMBS_RAW = "https://raw.githubusercontent.com/libretro-thumbnails/%s/master/%s"
USER_AGENT = "superfw-make-covers/1"

# Region preference when several box arts match the same game.
REGION_ORDER = ["usa", "world", "europe", "japan"]

# Fixed palette, must match menu_init() in src/menu.c:
#   value5 = c * 31 / 5 (integer division), index = r + 6*g + 36*b
def build_palette():
  pal = []
  for i in range(216):
    r, g, b = i % 6, (i // 6) % 6, i // 36
    rgb = []
    for c in (r, g, b):
      v5 = c * 31 // 5
      rgb.append((v5 << 3) | (v5 >> 2))   # What the GBA actually shows
    pal.append(tuple(rgb))
  return pal

PALETTE = build_palette()

def palette_image():
  flat = []
  for c in PALETTE:
    flat.extend(c)
  # Pad with copies of color 0, so any index >= 216 is the same color as 0.
  flat.extend(PALETTE[0] * (256 - len(PALETTE)))
  img = Image.new("P", (1, 1))
  img.putpalette(flat)
  return img

PAL_IMG = palette_image()

def convert(img, size):
  # Fit the image in a size x size square (keeping the aspect ratio), then
  # map it to the fixed palette with dithering. Uncovered area -> BG_INDEX.
  img = img.convert("RGBA")
  scale = min(size / img.width, size / img.height)
  w = max(1, round(img.width * scale))
  h = max(1, round(img.height * scale))
  img = img.resize((w, h), Image.LANCZOS)

  canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
  canvas.paste(img, ((size - w) // 2, (size - h) // 2))

  rgb = Image.new("RGB", (size, size), (0, 0, 0))
  rgb.paste(canvas, mask=canvas.getchannel("A"))
  q = rgb.quantize(palette=PAL_IMG, dither=Image.Dither.FLOYDSTEINBERG)

  idx = q.tobytes()
  alpha = canvas.getchannel("A").tobytes()
  out = bytearray(size * size)
  for i in range(size * size):
    if alpha[i] < 128:
      out[i] = BG_INDEX
    else:
      p = idx[i]
      out[i] = PAL_BASE + (p if p < 216 else 0)
  return bytes(out)

def cover_bytes(img):
  hdr = struct.pack("<IBBBB8x", COVER_MAGIC, COVER_VERSION, BIG, SMALL, 0)
  return hdr + convert(img, BIG) + convert(img, SMALL)

def read_cover(data):
  # Decodes a .cov file back into (big, small) RGB images (for previews/tests).
  magic, ver, big, small, pal = struct.unpack_from("<IBBBB8x", data)
  if magic != COVER_MAGIC or ver != COVER_VERSION or (big, small, pal) != (BIG, SMALL, 0):
    raise ValueError("not a valid cover file")
  if len(data) != 16 + big * big + small * small:
    raise ValueError("bad cover file size")
  imgs = []
  off = 16
  for sz in (big, small):
    imgs.append(data[off:off + sz * sz])
    off += sz * sz
  return imgs

# ---- Name matching -------------------------------------------------------

def norm(name):
  # "1234 - Legend of Zelda, The - The Minish Cap (U)(Trashman)" -> "legendofzeldaminishcap"
  n = name.lower()
  n = re.sub(r"^\d{3,4}\s*-\s*", "", n)          # Scene release numbers
  n = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", n)     # (Region) [tags]
  n = re.sub(r"\bthe\b", " ", n)
  n = n.replace("&", " and ").replace("_", " ")   # libretro uses _ for &
  n = re.sub(r"\band\b", " ", n)
  return re.sub(r"[^a-z0-9]", "", n)

def region_rank(name):
  tags = " ".join(re.findall(r"\(([^)]*)\)", name)).lower()
  for i, r in enumerate(REGION_ORDER):
    if r in tags:
      return i
  return len(REGION_ORDER)

def libretro_name(name):
  # libretro-thumbnails replaces these characters with "_" in file names.
  return re.sub(r'[&*/:`<>?\\|"]', "_", name)

def http_get(url, retries=3):
  req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
  for attempt in range(retries):
    try:
      with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()
    except Exception:
      if attempt == retries - 1:
        raise
      time.sleep(2)

class ThumbIndex:
  def __init__(self, cache_dir):
    self.cache_dir = cache_dir
    self.repos = {}

  def boxarts(self, repo):
    # Returns {normalized name: [(full name, path, is_symlink)]} for a repo.
    if repo in self.repos:
      return self.repos[repo]

    cachefn = os.path.join(self.cache_dir, repo + ".json")
    tree = None
    if os.path.exists(cachefn) and time.time() - os.path.getmtime(cachefn) < 7 * 86400:
      with open(cachefn, "r", encoding="utf-8") as fd:
        tree = json.load(fd)
    else:
      print("Downloading box art index for %s ..." % repo)
      data = json.loads(http_get(THUMBS_API % repo))
      if data.get("truncated"):
        print("  warning: index is truncated, some games may not be found")
      tree = [[e["path"], e["mode"]] for e in data["tree"]
              if e["path"].startswith("Named_Boxarts/") and e["path"].endswith(".png")]
      os.makedirs(self.cache_dir, exist_ok=True)
      with open(cachefn, "w", encoding="utf-8") as fd:
        json.dump(tree, fd)

    idx = {}
    for path, mode in tree:
      full = path[len("Named_Boxarts/"):-len(".png")]
      idx.setdefault(norm(full), []).append((full, path, mode == "120000"))
    for k in idx:
      idx[k].sort(key=lambda e: (region_rank(e[0]), e[0]))
    self.repos[repo] = idx
    return idx

  def find(self, repo, romname):
    # Returns (box art name, path, is_symlink, score) or None
    idx = self.boxarts(repo)
    base = os.path.splitext(romname)[0]

    # Exact No-Intro name first, then normalized, then fuzzy.
    exact = libretro_name(base)
    for entries in idx.values():
      for e in entries:
        if e[0] == exact:
          return e + (1.0,)

    key = norm(base)
    if not key:
      return None
    if key in idx:
      return idx[key][0] + (1.0,)

    # "Pokemon Ruby" -> "Pokemon - Ruby Version": shortest name that starts with it.
    # "Legacy of Goku I & II" -> "2 Games in 1 - Legacy of Goku I & II": shortest that ends with it.
    # Both kinds compete, the closest (shortest) name wins.
    longer = [k for k in idx if len(k) - len(key) <= max(8, len(key) // 2) and
              ((len(key) >= 6 and k.startswith(key)) or (len(key) >= 10 and k.endswith(key)))]
    if longer:
      best = min(longer, key=len)
      return idx[best][0] + (len(key) / len(best),)

    close = difflib.get_close_matches(key, list(idx.keys()), n=1, cutoff=0.82)
    if close:
      score = difflib.SequenceMatcher(None, key, close[0]).ratio()
      return idx[close[0]][0] + (score,)
    return None

  def download(self, repo, path, is_symlink):
    data = http_get(THUMBS_RAW % (repo, urllib.parse.quote(path)))
    # Symlinks are served as a text file containing the relative target.
    for _ in range(4):
      if data[:8] == b"\x89PNG\r\n\x1a\n" or not is_symlink:
        break
      target = data.decode("utf-8").strip()
      path = os.path.normpath(os.path.join(os.path.dirname(path), target)).replace("\\", "/")
      data = http_get(THUMBS_RAW % (repo, urllib.parse.quote(path)))
    return Image.open(io.BytesIO(data))

# ---- Main ----------------------------------------------------------------

def find_roms(root):
  for dirpath, dirnames, filenames in os.walk(root):
    # Skip SuperFW's own dir and system/hidden dirs
    dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "System Volume Information"]
    for fn in sorted(filenames):
      ext = os.path.splitext(fn)[1][1:].lower()
      if ext in SYSTEMS and not fn.startswith("."):
        yield os.path.join(dirpath, fn), fn, ext

def gba_gamecode(path):
  # 4 character game code from a valid GBA ROM header (ie. "BPEE"), or None.
  # Must match the checks in carousel_open_cover() (src/menu.c).
  try:
    with open(path, "rb") as fd:
      h = fd.read(0xC0)
  except OSError:
    return None
  if len(h) < 0xC0 or h[0xB2] != 0x96:
    return None
  if (-(sum(h[0xA0:0xBD]) + 0x19)) & 0xFF != h[0xBD]:
    return None        # Bad header checksum
  code = h[0xAC:0xB0].decode("ascii", "replace")
  return code if re.fullmatch(r"[A-Z0-9]{4}", code) else None

def find_local_image(images_dir, romname):
  if not images_dir:
    return None
  base = os.path.splitext(romname)[0]
  for stem in (romname, base):
    for ext in IMAGE_EXTS:
      p = os.path.join(images_dir, stem + ext)
      if os.path.isfile(p):
        return p
  return None

def default_sdroot():
  # Packaged as an .exe (PyInstaller): use the folder the .exe sits in, so it
  # can be copied to the SD card root and double-clicked.
  if getattr(sys, "frozen", False):
    return os.path.dirname(os.path.abspath(sys.executable))
  return None

def main():
  parser = argparse.ArgumentParser(description="Generate SuperFW carousel cover art")
  parser.add_argument("sdroot", nargs="?", default=default_sdroot(),
                      help="SD card root (ie. E:\\) or a folder with ROMs (default for the .exe: its own folder)")
  parser.add_argument("--output", default=None, help="Covers output dir (default: <sdroot>/.superfw/covers)")
  parser.add_argument("--images", default=None, help="Folder with your own cover images, named like the ROMs")
  parser.add_argument("--no-download", action="store_true", help="Only use --images, do not download box art")
  parser.add_argument("--force", action="store_true", help="Regenerate covers that already exist")
  parser.add_argument("--dry-run", action="store_true", help="Only show what would be done")
  parser.add_argument("--cache", default=os.path.join(os.path.expanduser("~"), ".superfw-covers-cache"),
                      help="Where to cache the downloaded box art index")
  args = parser.parse_args()

  if not args.sdroot:
    parser.error("the SD card root is required, ie. make-covers.py E:\\")
  if not os.path.isdir(args.sdroot):
    sys.exit("Not a directory: %s" % args.sdroot)

  outdir = args.output or os.path.join(args.sdroot, COVERS_DIR)
  thumbs = ThumbIndex(args.cache)

  made, skipped, missing = 0, 0, []
  done = set()
  codes_used = set()      # Game codes that got a cover file in this run
  for path, romname, ext in find_roms(args.sdroot):
    if romname in done:
      continue      # Same file name in another folder shares the cover
    done.add(romname)

    local = find_local_image(args.images, romname)
    namefn = os.path.join(outdir, romname + ".cov")
    code = gba_gamecode(path) if ext == "gba" else None
    codefn = os.path.join(outdir, code + ".cov") if code else None

    if not args.force and (os.path.exists(namefn) or (codefn and not local and os.path.exists(codefn))):
      skipped += 1
      continue

    # GBA covers are named after the game code (ie. BPEE.cov), so they keep
    # working if the ROM is renamed. Your own images, and a second ROM with the
    # same code (ie. a ROM hack), use the ROM file name instead.
    use_code = bool(codefn) and not local and code not in codes_used
    outfn = codefn if use_code else namefn

    img, source = None, None
    try:
      if local:
        img, source = Image.open(local), local
      elif not args.no_download:
        m = thumbs.find(SYSTEMS[ext], romname)
        if m:
          name, tpath, islink, score = m
          source = "%s (match %d%%)" % (name, round(score * 100))
          if not args.dry_run:
            img = thumbs.download(SYSTEMS[ext], tpath, islink)
    except Exception as e:
      print("  error getting cover for %s: %s" % (romname, e))
      img, source = None, None

    if not source:
      missing.append(romname)
      print("NO COVER   %s" % romname)
      continue

    print("%s %s  <-  %s  [%s]" % ("WOULD MAKE" if args.dry_run else "MADE      ", romname, source,
                                    os.path.basename(outfn)))
    if not args.dry_run:
      os.makedirs(outdir, exist_ok=True)
      data = cover_bytes(img)
      with open(outfn, "wb") as fd:
        fd.write(data)
    if use_code:
      codes_used.add(code)
    made += 1

  print()
  print("Covers %s: %d, already present: %d, not found: %d" %
        ("to make" if args.dry_run else "made", made, skipped, len(missing)))
  if missing:
    print("For games without a cover, put an image named like the ROM in a folder")
    print("and run again with --images <folder>.")

if __name__ == "__main__":
  # When double-clicked (.exe without arguments) keep the window open at the end.
  pause = getattr(sys, "frozen", False) and len(sys.argv) == 1
  code = 0
  try:
    main()
  except SystemExit as e:
    if isinstance(e.code, str):
      print(e.code)
    code = 0 if e.code in (None, 0) else 1
  except Exception as e:
    print("Error: %s" % e)
    code = 1
  if pause:
    input("\nPress Enter to close...")
  sys.exit(code)
