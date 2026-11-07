# NIGHT-RUNNERS REDUX Patcher

NIGHT-RUNNERS REDUX is a set of fixes, new content and gameplay changes for **NIGHT-RUNNERS PRIVATE ALPHA**. This repository holds the source of the patcher that applies all of them to a **stock 3.2.7 or 3.2.8** install.

The repository contains no game files and no prebuilt patcher. It holds the patcher code, plus patch data made of the bytes REDUX adds or changes. Everything else is copied at patch time from the player's own game files.

## Contents

- [Supported game versions](#supported-game-versions)
- [Using the patcher](#using-the-patcher)
- [Changes](#changes)
- [Files the patcher touches](#files-the-patcher-touches)
- [Known limitations](#known-limitations)
- [Building](#building)
- [How the patcher works](#how-the-patcher-works)
- [Regenerating the patch data](#regenerating-the-patch-data)
- [Credits](#credits)

## Supported game versions

The patcher identifies the build from `GameAssembly.dll` and refuses anything it does not recognise.

| Version | Stock `GameAssembly.dll` SHA-256 | Patched `GameAssembly.dll` SHA-256 |
|---|---|---|
| 3.2.7 | `63d0258940797d14abc49192b130afdaecb2eb3eb54e6c48ef49219dbfed660f` | see `patches/3.2.7/GameAssembly.json` |
| 3.2.8 | `9f918e73ac505805079519ad6c2730449ab01ccdd742282356191771039759f4` | `706971afcd73c015a841cb9ec21c997958877e7b512c3645ece2ea35f9aa0ac5` |

On 3.2.8 the output is identical to the REDUX development install. `GameAssembly.dll` and `catalog.bin` are byte-identical, and every asset bundle and `sharedassets0.assets` has identical object contents. The 3.2.7 output is a port. It is checked against the 3.2.8 output, but it has not been played yet.

## Using the patcher

1. Close the game.
2. Run `NIGHT-RUNNERS REDUX Patcher.exe`.
3. Select the game folder: the one that contains `NIGHT-RUNNERS PRIVATE ALPHA.exe`.
4. Press **Install REDUX**.

Before writing anything, the patcher copies every file it changes into `_redux_backup` inside the game folder. **Restore stock** puts those files back and deletes the files REDUX added.

The same actions are available from the command line:

```bash
python -m nrredux "C:\path\to\NIGHT-RUNNERS PRIVATE ALPHA" --check
```

```bash
python -m nrredux "C:\path\to\NIGHT-RUNNERS PRIVATE ALPHA"
```

```bash
python -m nrredux "C:\path\to\NIGHT-RUNNERS PRIVATE ALPHA" --restore
```

Before restoring stock, sell any **BMW E36 M3**. A save that still holds model 72 points at a car that no longer exists once the files are restored.

## Changes

### Auction house and purchasing

- **Larger auction pool.** Auctions can offer every car origin that has a chassis reference and engine data and is not flagged `NOT_A_PLAYER_CAR`. That is 55 models, excluding the FC3S (model 55) and the non-player starter car (model 23). Generation, selection and the saved-listing check all use the same allowlist.
- **Purchase gate.** The private-alpha purchase check uses the auction allowlist, so every car that can be listed can also be bought.
- **BMW E36 M3 (model 72).** Added to the allowlist, the saved-listing check and the purchase check.

### Names and labels

- **Blank model names filled in:** 47 Korschen 911 Carrera, 48 Korschen 911 Turbo, 51 Sannis Sykina C10 GTE, 52 Sannis Sykina C10 GTS, 53 Sannis Sykina C10 GTS-R, 54 Mazda RX-7 FD3S, 56 Honda NSX NA1, 57 Honda NSX NA2, 58 Sannis Z33, 66 Honda NSX NA1 Mugen, 67 Honda NSX NA1 SOR360, 68 Honda NSX NA1 THREAT, 69 Honda NSX NA2 VSF, 72 BMW E36 M3 3.0 Euro.
- **Korschen K6 variants.** Models 18–22 read **K6 TURBO GEM / STR / KOE / SLA / FLA** on the auction sheet, and **Korschen K6 TURBO …** in the purchase text.
- **K6 TURBO SLA.** The SLA is catalogued under model 15, so it is recognised by chassis type 14 and labelled SLA.
- **Engine names.** Type 17 shows **S50B30** (inline-6 layout). Type 18 shows **VQ35DE** (V6 layout).
- **Bodykit labels.** The new RX-7 and R33 kits show their own names in the bodykit menu: VEILSIDE FORTUNE, SDF, SUPERGREDDY3, GENKI7, AC987, SB7, SCOOT RACING, GREDDY8 and VILLAIN.

### Engine swaps

- **Cross-car engine list.** The garage engine list shows the car's stock engines first, then every distinct engine type from other cars that has a loadable prefab. You don't need to own the donor car.
- **Preview parts.** Engine customisation parts load for the expanded list. Foreign stock parts resolve against their source car.
- **Saved engines.** A saved foreign engine is looked up by its saved type. If no match exists, the original stock fallback is kept.
- **Free, repeatable swaps.** Swap prices are zero, free-reward use is bypassed, and both "already swapped" checks are skipped. Confirmation, installation and saving are still handled by the game.

### Forced-induction swap menu

The forced-induction entries in the Mods hub and in the engine-swap browser open a selector with four choices. These work on every car and every engine:

| Choice | Price | `inductionType` |
|---|---:|---:|
| Naturally aspirated | 150,000 | 0 |
| Single turbo | 290,000 | 2 |
| Twin turbo | 400,000 | 3 |
| Supercharger | 340,000 | 1 |

- **Buying.** Select an option, then select it again at **CONFIRM PURCHASE?**. Back cancels the confirmation.
- **Status labels.** The installed option shows **INSTALLED** and **ALREADY INSTALLED**, and is not charged. The other options show their price and **PURCHASE**.
- **After a purchase.** The menu returns to the Mods hub or to the categories, whichever it was opened from. Power is recalculated straight away (`CarData.setCar_power`), and the choice is saved under the game's own `inductionType<carID>` key.
- **Supercharger.** It uses the game's dormant supercharger code and its existing `supercharger_` sound. Before charging, the menu checks that the RCC supercharger curves exist. If they don't, it shows **UNAVAILABLE** and charges nothing.
- **Saved forced induction is kept.** The car loader now bases forced-induction part stripping on the saved choice, not on the engine's stock spec. Turbo or supercharger stays on cars whose stock engine is NA.

### New car: BMW E36 M3 3.0 Euro (model 72)

- **A car of its own.** Model 72, 1992. It is built from the Sannis Sykina GTE 1989 ZENKI bundle, which stays untouched.
  - New bundle `catalog_carorigins_assets_carorigin_bmw_e36_m3_92_677070ff253ff1a72eb56ad122893370.bundle`, with its own CAB, AssetBundle name and prefab path `Assets/PlanetJem/__Legacy/_OBJECTS/_CARS/_BMW_E36/carorigin_BMW_E36_M3.prefab`.
  - Registered in `catalog.bin` with an append-only edit.
  - Row 86 of `Catalog_CarOrigin` in `sharedassets0.assets`.
- **Body.** 19 E36 meshes (body, doors, bumpers, lights, glass, badges, wipers, exhaust) are baked into one `E36_BODY` group under the RCC chassis. The donor's combined exterior, R32 shell, LOD and sunroof renderers are disabled.
- **Materials and paint.** Materials are cloned from the game's own car materials. The E36 light, misc and rim textures are embedded. The paint is a fixed Estoril blue.
- **Chassis.**
  - Wheelbase 2.737 m: colliders at z ±1.368, with the wheel anchors moved to match.
  - The track stays at the donor's ±0.72 m.
  - `chassis_weight` is 1,315 kg.
- **Engine: S50B30 (type 17).** 286 PS, 7,600 rpm limiter, naturally aspirated, 200 kg, 3.0 L inline-6. It keeps the RB20 mesh and parts list, so RB20 aftermarket parts fit.
- **Sound.** Seven recorded E36 clips are mapped to four rpm bands: idle, low, medium and high, each with on- and off-throttle clips.
- **Parts compatibility.** `CarPart.isCompatibleWithCarModel` treats model 72 as model 71, so the R32 interior, wheels and parts load.

### New engine: VQ35DE for the Sannis Z33 (type 18)

- **What changed.** The Z33 (model 58) carried the VQ35 engine mesh but a 1JZGTE_VVTI definition. That definition is now the **VQ35DE**:
  - 280 PS at 6,200 rpm, 363 Nm (torque modifier 1.25), 6,600 rpm limiter
  - NA stock, with NA, single and twin turbo offered
  - 3.5 L V6, 165 kg
- **Swaps.** The VQ35DE is the Z33's stock engine and, through the engine-swap list, available to every car.
- **Sound.** VQ35DE loops built from rev sweeps: idle plus six bands recorded at 1,500 to 6,300 rpm, as 13 clips in the Z33 bundle. Start, limiter, intake, reverse and turbo sounds are unchanged.
- **Catalog.** The Z33 row in `sharedassets0.assets` lists engine type 18.

### Bodykits

- **Mazda RX-7 FD3S: 11 bodykits.** VEILSIDE FORTUNE plus seven aftermarket sets that shipped unused in the game files: SDF, SUPERGREDDY3, GENKI7, AC987, SB7, SCOOT RACING and GREDDY8.
  - Each kit is cloned from a working kit and hides the stock panels it replaces.
  - Each gets its own `PartName_Aftermarket` ID (20–26).
  - **GENKI7.** The front clam goes in the front-bumper slot and hides the stock fenders.
  - **GREDDY8.** It is a roadster body. It hides the stock fenders, rear fender (roof) and trunk, and registers its own number-plate and exhaust anchors.
  - **SDF.** It is a convertible and hides the stock trunk hatch.
- **VEILSIDE FORTUNE fixes.**
  - The rear indicators are wired left/right correctly.
  - The number plate and exhaust anchors are corrected.
  - The rear-light lens UVs point at the red lens area, so the lights are no longer white.
  - The rear wheels and colliders sit 50 mm further out per side.
- **RX-7 shell.**
  - The body-colour lip under the hatch is moved to the dark trim submesh, so it no longer shows through GENKI7, SUPERGREDDY3 and SCOOT RACING.
  - The coupe greenhouse is moved off the shell into a `FD3S STOCK CABIN TOP` mesh carried by every RX-7 door part except GREDDY8's. GREDDY8 therefore shows only its own windshield.
- **Sannis Sykina R33 GTR: VILLAIN.** A complete bodykit built from the unused DLV set: headlights, front bumper, fenders, side skirts, rear bumper, rear fenders, trunk, spoiler and doors. With VILLAIN fitted, all four wheels and colliders sit 30 mm further out per side.

### Bug fixes

- **Korschen K6 auction freeze (FLA, Narrow, Narrow Cabrio, SLA, Wide, Wide Cabrio).**
  - The interior parts list, interior customisation and engine customisation pointed at Sannis parts. They now use Korschen donors: the Carrera '89 for the Narrow variants, the Turbo '91 for the rest.
  - The matching catalog rows are updated too.
- **Korschen K6 door and mirror freeze.** 64 missing `door_Left` / `door_Right` references on 32 customisation parts now point at their matching meshes.
- **K6 TURBO FLA storage freeze.** The FLA headlight is no longer a pop-up, because the FLA has no headlight joint.
- **K6 TURBO GEM '89 purchase softlock.**
  - The GEM '89 origin and catalog row now use the Korschen Turbo '91 interior and engine parts.
  - Its six mirrors and the GEMBALLA doors got their 14 missing door references.
- **Silent or misplaced engine audio.** `EngineSoundAnchor` is moved onto the engine for these cars:
  - Korschen Turbo '91, KOE '91, STR '91 and GEM '91
  - Ferrari 360 Spyder
- **K6 TURBO GEM '91.** The rear track is 50 mm wider per side.
- **Honda NSX.** An unresolved interior asset key (`1cee9cdb…`) is redirected to the working one (`72e82596…`).

## Files the patcher touches

| File | Change |
|---|---|
| `GameAssembly.dll` | 45 code patch sites and four new sections (`.nrmod`, `.swcode`, `.swdata`, `.fdwheel`) |
| `NIGHT-RUNNERS PRIVATE ALPHA_Data/sharedassets0.assets` | `Catalog_CarOrigin`: K6 and GEM rows, the Z33 engine record, the new E36 M3 row |
| `…/StreamingAssets/aa/catalog.bin` | E36 M3 bundle and asset locations appended |
| `…/StandaloneWindows64/catalog_carorigins_assets_carorigin_bmw_e36_m3_92_….bundle` | New file |
| `…carorigin_korschenk6_{fla,narrow,narrow_cabrio,sla,wide,wide_cabrio,gem}_89_93_….bundle` | K6 interior and engine donors |
| `…carorigin_korschen_{turbo,koe,str,gem}_91_….bundle`, `…carorigin_fer_360_00_spyder_….bundle` | Engine sound anchor; GEM '91 rear track |
| `…carorigin_z33_02_….bundle` | VQ35DE definition and sound |
| `…carorigin_fd3s_91_….bundle` | RX-7 shell lip and greenhouse |
| `…customization_fd3s_91_02_assets_all_0833….bundle` | RX-7 bodykits, Fortune fixes, cabin top |
| `…customization_sannissykina_93-98_assets_all_d791….bundle` | VILLAIN bodykit |
| `…customization_korschen_89-94_assets_all_e1ab….bundle` | K6 door and mirror references, FLA headlight |

## Known limitations

- **3.2.7 has not been played.** The port is checked offline only.
- **Not yet confirmed in game on 3.2.8:**
  - the supercharger's feel and sound
- **BMW E36 M3.**
  - The paint colour is fixed, and exterior parts changed in the garage are not visible on it.
  - It has the R32 interior, and its doors don't open visually.
  - Its lamps use the donor's light sources.
  - AI or race spawners may pick it, since it is a normal player car.
- **Z33 bought before patching.** It keeps engine type 3 (1JZ) in the save until it is swapped to the VQ35DE in the garage.
- **Supercharger.** No supercharger meshes exist, so the engine bay shows no blower.
- **RX-7 roadster kits.** Shop previews of RX-7 door parts include the windshield that now lives on them.

## Building

Requirements: Windows, Python 3.12 (64-bit) and an internet connection for `pip`.

```bash
powershell -ExecutionPolicy Bypass -File build.ps1
```

`build.ps1` creates `.venv`, installs `requirements.txt` and PyInstaller, and writes `dist\NIGHT-RUNNERS REDUX Patcher.exe`. The patch data in `patches\` is embedded in the exe. To use a specific interpreter, pass `-Python C:\path\to\python.exe`.

To run from source without building:

```bash
pip install -r requirements.txt
```

```bash
python -m nrredux
```

## How the patcher works

| Part | What it does |
|---|---|
| `nrredux/dllpatch.py` + `patches/<version>/GameAssembly.json` | Checks every patch site against its original bytes, writes the new bytes, and appends the REDUX sections. The game's exception table is copied from the player's DLL and REDUX's unwind entries are appended to it. The result is checked against a known SHA-256. |
| `nrredux/unityfs.py` | Reads UnityFS bundles (LZ4, LZ4HC, LZMA) and writes them back with LZ4HC blocks. Unchanged blocks are reused as they are. |
| `nrredux/serialized.py` | Reads and writes Unity serialized files, versions 21–23. |
| `nrredux/assetdelta.py` + `patches/assets/*.nrd` | Object-level deltas keyed by Unity path ID. Each object is kept, rebuilt from copy ranges of the player's own objects plus REDUX bytes, or added. Because the deltas copy from the player's files, the same delta works on 3.2.7 and 3.2.8, even where those versions use different external path IDs. |
| `nrredux/catalog.py` | Appends the E36 M3 locations and keys to the Addressables binary catalog. It clones the ZENKI entry and records the real size of the new bundle. |
| `nrredux/patcher.py` | Detects the version, resolves bundles by name pattern, backs files up, writes atomically, and restores. |
| `nrredux/gui.py`, `nrredux/__main__.py` | The Tk window and the command line. |
| `payload/` | Reference C sources of the injected engine-swap, wheel-offset and forced-induction code, with the 3.2.8 addresses. Their compiled machine code is part of `patches/3.2.8/GameAssembly.json`. |

## Regenerating the patch data

The tools in `tools/` need `requirements-dev.txt`. They take a stock game folder and a folder with REDUX installed by other means, such as the development install.

| Tool | Purpose |
|---|---|
| `tools/make_dll_spec.py <stock dll> <modded dll> <out json>` | Builds a DLL spec from a stock/modded pair, and checks that applying it reproduces the modded DLL byte for byte. |
| `tools/port_dll.py <stock 3.2.8 dll> <modded 3.2.8 dll> <stock 3.2.7 dll> <3.2.8 spec> <out spec> <3.2.8 metadata> <3.2.7 metadata> [out dll]` | Ports the 3.2.8 spec to 3.2.7. Functions are matched by masked machine code, with IL2CPP metadata names as a fallback. Every patch site, call, RIP-relative and image-relative reference, jump table and chained unwind record in the REDUX code is remapped, and each site's original bytes are checked in the 3.2.7 DLL. |
| `tools/methodmap.py` | IL2CPP method-to-RVA map used by `port_dll.py`. |
| `tools/make_asset_patches.py <stock game> <modded game> <out dir> tools/asset_plan.json` | Builds the `.nrd` asset deltas, and checks that each one rebuilds the modded file's objects exactly. |
| `tools/verify.py <stock 3.2.7> <stock 3.2.8> <patched 3.2.7> <patched 3.2.8> <reference>` | Compares patched 3.2.8 against the reference install. Then it checks that patched 3.2.7 differs from patched 3.2.8 only by 3.2.7's own path IDs and preload order. |

After changing `tools/asset_plan.json`, update `patches/assets.json` to match. It is the same list without `target_glob`, and with `path` renamed to `source`.

## Credits

- **NIGHT-RUNNERS** and its assets belong to their developers. This project is not affiliated with or endorsed by them. You need your own copy of the game.
- **BMW E36 M3 model, textures and sounds** come from an earlier version of NIGHT-RUNNERS.
- **VQ35DE engine sound.** The REDUX loops are derived from *Nissan 350Z (VQ35DE) Engine Sound* (`ta013vq35`) for GTA V by **TheAdmiester**. That mod credits Codemasters (DIRT 2) for the engine and exhaust recordings, Polyphony Digital (GT Sport) for the ignition and turbo sounds, and Legacy_DMC, Aquaphobic and Xenn for tools and help.
