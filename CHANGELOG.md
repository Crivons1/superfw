Changelog of the carousel fork
==============================

Versions are `v<upstream version>-carousel.<n>`. Each one lists what the fork
adds on top of upstream SuperFW; the upstream changes it includes are named
by their commit. Every release has the firmware for the three boards
(`superfw-sd.fw`, `superfw-lite.fw`, `superfw-chis.fw`) and the cover maker
for Windows, macOS and Linux.

## Unreleased

- **Cover maker adds cheats:** it downloads the SuperFW cheat database and
  copies the cheats of the GBA games on the card to `/.superfw/cheats/`
  (existing files are kept; `--no-cheats` skips it). Games the database does
  not have (Pokemon Emerald, for one) get libretro's Code Breaker cheats,
  converted to SuperFW's format (same game, region and revision only; master
  and patch codes left out).
- **Guide reader** (SuperChis and Lite): a `.txt` named like the ROM adds a
  Guide option to the in-game menu, with word wrap, page keys and the
  position remembered in `/.superfw/guide.pos`.
- **Cover maker copies the firmware:** `--firmware chis|sd|lite` (or the
  window's Firmware option) puts the latest release's firmware on the card.

## v0.21-carousel.3

Same upstream base as v0.21-carousel.1.

- **Carousel view (Start):** show all games, the favourites or one system
  (GBA, GB/GBC, NES, SMS...), sorted by name, by system (Up/Down jump between
  systems) or by recently played. Remembered in `ui-settings.txt`.
- **Favourites:** Select > Add to / Remove from favourites, kept in
  `/.superfw/favorites.txt` (one full path per line), shown in the info line.
- The menu's key handlers are compiled for size: the SD board's firmware has
  very little flash left (about 360 bytes).

## v0.21-carousel.2

Same upstream base as v0.21-carousel.1.

- **Folders with short Chinese names** (or other names a non-US Windows
  stored as 8.3 only) showed as "?" and could not be opened (upstream
  issue #84). They open now; their names still show as symbols, the font
  has no glyphs for those bytes read as code page 437.
- **"Show extensions" setting** (UI settings, upstream issue #51): off hides
  the file extensions in the SD browser, recent and flash lists.
- **Save files have the game's save size** (32 KiB for SRAM games, 64/128
  KiB for flash, 512 B / 8 KiB for EEPROM) instead of always 128 KiB, so they
  work with emulators and other tools (upstream issue #39). Emulated games
  and "write SRAM to this .sav" still write the whole 128 KiB.
- The stack check is accurate now: it knows which functions the printf,
  settings parser and sort callbacks can reach. The worst case is 12.6 KB
  of the 16 KB stack (it showed 15.1 KB by over-counting).
- The emulator path buffer is 64 bytes again (it sits on the deepest stack
  path), with a length check.
- README: example pictures of the carousel tab (`docs/images/`).

## v0.21-carousel.1

Based on upstream `master` at 1c9ff09 (v0.21 plus the fixes after it: RTC
year/day of week, safer save writing, SD card info, key repetition...).

### New

- **Carousel tab**: the games of the current folder (and its subfolders) as
  cover art. Smooth zoom, background tinted with the cover's color, info
  line (system, size, save, last played, in flash), letter jump with Up/Down,
  position bar, last game remembered, game list cached on the card so it
  shows at once and is checked in the background. Games written to flash
  start from flash.
- **Carousel file menu (Select)**: delete, hide, write to flash; for games in
  flash, remove from flash or load from the SD card instead, with the flash
  usage shown. Same actions as the SD card and flash tabs.
- **Start tab setting** (UI settings): start on the carousel (default) or on
  the browser as before.
- **Cover maker** (`tools/make-covers.py`, also as programs that need no
  Python): finds the box art of every game on the card, identifying ROMs
  exactly by checksum or GBA game code (No-Intro lists) before falling back
  to the file name. Double-clicked it opens a window: pick the SD card, see
  the progress, the box art picked for each game and a preview of each
  cover. Command line options for own images, dry runs and redoing covers.
- **Faster boot**: the chosen language is cached on the card and only its
  strings are kept in memory (all languages stay in one compressed pack).

### Fixes

- Damaged or hand-edited files on the card can no longer crash the menu or
  write past buffers: cheats (8-bit length overflows, unbounded codes),
  pending save info, patches, the patch database (offsets checked against
  its 1 MiB area), NOR flash metadata, UI settings (a short `langcode`), the
  recent list and malformed UTF-8 file names.
- Every save, save state, config, patch, cheat and emulator path is built
  with a size check; too long paths give an error instead of an overflow.
- A failed ROM load no longer leaves the menu in an unsafe state.
- Folder read errors are reported instead of showing an empty folder.
- Tools > SD benchmark: no divide by zero on a zero time.
- The carousel cover scaling could read one byte past its table.
- Two old compiler warnings.

### Development

- Fuzz tests (libFuzzer, address and undefined behaviour sanitizers) for all
  the parsers of files read from the SD card, run by CI on every push.
- CI checks the worst case stack depth of the menu against the 16 KB stack.
- CI runs cppcheck on the firmware sources.
- Tests for the carousel helpers, the language pack and the cover maker.
- Code signing of the Windows cover maker through the SignPath Foundation is
  prepared (`docs/SIGNING.md`).
