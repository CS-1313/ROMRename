<div align="center">
  <img src="media/logo/ROMRename_logo.png" alt="ROMRename Logo" width="100%">
</div>

# ROMRename

ROMRename is a powerful, GUI and CLI-driven utility for batch renaming, organizing, and matching ROM files against official standard DAT files (.dat/.xml). It eliminates the hassle of manually renaming poorly labeled ROMs so they can be seamlessly scraped by frontends like [Daijishō](https://github.com/TapiocaFox/Daijishou).

## Installation & Download Options

There are two ways to get ROMRename up and running:

### Option 1: The One-Stop Shop (Recommended)
Head over to the **[Releases](../../releases)** tab on the right side of this page and download the latest `ROMRename_vX.zip`. This is a complete, ready-to-run package that includes the application AND a pre-configured `DATPACK` folder containing all the official hashes you need. Just extract the ZIP, and double-click `main.py` (or run `python main.py` in your terminal).

*Included DATPACK Version: **No-Intro Love Pack (DAT) (2026-09-30)**. Special thanks and full credit to the [No-Intro Dat-O-Matic](https://datomatic.no-intro.org/) project for this daily version package!*

### Option 2: Source Code Only (Bring Your Own DATs)
If you prefer to use your own custom database files (like specific No-Intro or ReDump sets), grab the source code:

- **Direct Download (No Git required)**: Click **[Download Source (.zip)](https://github.com/CS-1313/ROMRename/archive/refs/heads/main.zip)** (or use the green **`<> Code`** button at the top of this page).
- **Or via Terminal**:
  ```bash
  git clone https://github.com/CS-1313/ROMRename.git
  ```

**Then:**
1. Open or navigate into the folder (`cd ROMRename` if in terminal).
2. Drop your `.dat` or `.xml` files directly into the included `DATPACK/` folder.
3. Launch the app by **double-clicking `main.py`** (Windows) or running `python main.py` / `python3 main.py` in your terminal. *(See [Usage & OS Compatibility](#usage--os-compatibility) below for details).*

## Features

- **Dual-Engine Matching (Hash + Math)**: Ingests massive XML/DAT databases to build a master index. Scanned files are first checked for perfect CRC32 hash hits. If unknown, the "Ghost Math Engine" strips away junk metadata and uses advanced fuzzy string comparison to predict the correct official title.
- **Interactive Safe-Preview UI**: Review a complete virtual plan before a single file is touched. You can manually override matches, dynamically hide low-confidence items, or tweak Region biases and watch the list recalculate instantly in RAM without re-reading your hard drive.
- **Granular Library Control (1G1R)**: Dial in your exact preferences to build the perfect clean library. Prioritize specific regions to break ties, automatically strip numbered prefixes, prefer retail "Base" versions over Beta/Proto/Demo/LodgeNet/Unl/Pirate/Rev releases, and explicitly exclude junk file types (like `.nfo` or `.txt`).
- **Bulletproof Execution & QA**: Choose to safely copy files to a new folder or overwrite them in-place. The app natively extracts `.zip` and `.7z` archives in an isolated sandbox, generates highly detailed `.csv` Job Receipts for every run, and includes a full headless CLI for automation.

## How It Works

1. **Load DATs**: Point the application to your DATPACK folder. It will parse the XML/DAT files and cache the official names and CRC32 hashes.
2. **Scan**: Point the application to your Source directory containing your ROMs. The app calculates the CRC32 hash of each file for perfect matches. If the hash is unknown, it falls back to the Fuzzy/Ghost Math Engine to predict the correct official title.
3. **Review**: Check the proposed matches in the UI.
4. **Execute**: The app automatically renames your files to perfectly match the DAT specifications.

## Requirements
- Python 3.8 or higher.
- **Zero Dependencies** This application is built strictly using Python's standard libraries (`tkinter`, `zlib`, `difflib`, `shutil`, etc.). No `pip install` required - it runs straight out of the box.

## Usage & OS Compatibility
ROMRename is 100% cross-platform compatible and runs entirely on built-in Python standard libraries!

First, open your terminal or command prompt and navigate to the extracted folder (e.g., `cd path/to/ROMRename`). Then run the command for your OS:

### Windows
```powershell
python main.py
```

### macOS
Mac natively supports the app via Python 3:
```bash
python3 main.py
```
*(Note: If you install Python via Homebrew instead of the official Mac installer, you may need to run `brew install python-tk` first).*

### Linux (Ubuntu/Debian)
Linux distributions often separate the Python graphical libraries to save space. Simply install the `python3-tk` package before running:
```bash
sudo apt-get update
sudo apt-get install python3-tk
python3 main.py
```

### Processing Mode (Single-Thread vs Multi-Core)

The Settings & Engine tab includes a **Processing Mode** toggle. **Single-Thread** is the default and is completely unchanged — Python's GIL limits a single process to one core, which is why single-thread mode shows only ~1/N of total CPU. **Multi-Core** spawns worker processes to parallelize fuzzy matching; the worker count equals your logical CPU threads minus one, further capped so workers use at most ~50% of your free RAM. The **Worker Processes** spin box defaults to the recommended count for your computer and can be lowered if you want to leave more CPU free. Workers run at below-normal priority, keeping your PC responsive during large jobs. If the workers cannot start, ROMRename falls back to single-thread matching automatically.



## ⚡ Command Line Interface (CLI)

ROMRename includes a powerful, headless CLI tailored for server admins, power users, and automated scripting. By default, the CLI is completely safe and runs in **Dry-Run Mode**, meaning it will only print a preview to your terminal and will *not* modify any files on your hard drive.

Subfolders are always scanned recursively (use `--no-recursive` to scan only the top-level folder). Run `python main.py --help` at any time to see every flag grouped by category.

> **Defaults that differ from the GUI:** the GUI mirrors the source folder tree and transfers empty folders by default, and only scans subfolders when its checkbox is ticked. The CLI scans subfolders by default but writes files to the top level of the output unless you pass `--keep-tree` or `--keep-tree-empty`.

### Basic Usage
**1. Test a folder (Dry-Run):**
```bash
python main.py --source "E:\Games"
```

**2. Execute and copy renamed files to a new folder:**
```bash
python main.py --source "E:\Games" --output "E:\Games_Renamed" --execute
```

**3. Execute and overwrite the original files (DANGEROUS):**
```bash
python main.py --source "E:\Games" --execute --inplace
```
*(Note: Using `--inplace` will instantly trigger a safety prompt. To bypass this prompt in automated scripts, simply append `-f` or `--force`).*

**4. Execute, copy to a new folder, and mirror subfolder structure:**
```bash
python main.py --source "E:\Games" --output "E:\Games_Renamed" --keep-tree --execute
```

**5. Mirror the subfolder structure AND keep empty folders:**
```bash
python main.py --source "E:\Games" --output "E:\Games_Renamed" --keep-tree-empty --execute
```
*(Note: `--keep-tree-empty` already includes `--keep-tree`, so you don't need both. After the files are copied, every source subfolder still missing from the output is recreated, including folders whose files were all skipped. It is ignored with `--inplace` (the folders are already there) and skipped if you interrupt the run with Ctrl+C. This matches the GUI's **Transfer Empty Folders** option.)*

**6. Use all available CPU cores (Multi-Core mode):**
```bash
python main.py --source "E:\Games" --output "E:\Games_Renamed" --multithread --execute
```

**7. Also copy the "Rejects" (files below the threshold) under their original names:**
```bash
python main.py --source "E:\Games" --output "E:\Games_Renamed" --keep-tree --keep-rejects --execute
```
*(Note: Without `--keep-rejects`, files below the confidence threshold are skipped and left only in the source. With it, they are copied to the output unchanged, so the output becomes a complete copy of your library with only the matched files renamed. Combine it with `--keep-tree` or `--keep-tree-empty` to place rejects in their original subfolders; otherwise they go to the top level of the output. It is ignored with `--inplace`, where rejects are already in place. This matches the GUI's **Transfer 'Rejects' (Keeping Original Name)** option.)*

**8. Handle duplicate names and exclude junk:**
```bash
python main.py --source "E:\Games" --output "E:\Games_Renamed" --keep-tree --duplicates skip --exclude-folder "arcade" --exclude-folder "anbernic/saves" --exclude-ext .txt --exclude-ext .nfo --execute
```
*(Note: When two files match the same official name, `--duplicates append` (the default) keeps both by adding ` (1)`, ` (2)`, and so on, while `--duplicates skip` keeps only the first one. Excluded folders and extensions are not matched or copied and are logged as "Skipped (Excluded)" in the Job Receipt. `--exclude-folder` takes a path relative to the source (an absolute path inside the source also works) and excludes everything below it. Both flags can be repeated. These match the GUI's duplicate options and **Exclusions** tab.)*

**9. Pick a region, list more alternatives, and print full error details:**
```bash
python main.py --source "E:\Games" --region eu --alternatives 8 --debug
```
*(Note: `--region` accepts `"USA / English"`, `"Europe"`, `"Japan"`, `"World"` or `"None (Raw Math)"`, plus the shortcuts `usa`/`us`/`en`, `eu`, `jp` and `none`/`raw`. Any other value is rejected with an error. The default, `"USA / English"`, matches the GUI; use `--region none` to match without any region tie-breaking.)*

### CLI Flags Reference

**Paths**
| Flag | Description | Default |
|---|---|---|
| `-s`, `--source` | **(Required)** Path to the source directory containing ROMs | |
| `-o`, `--output` | Path to the output directory (if copying) | Same as source |
| `-d`, `--datpack` | Directory containing your DAT files | `DATPACK` |

**Matching**
| Flag | Description | Default |
|---|---|---|
| `-t`, `--threshold` | Minimum confidence score to rename a file (1-100) | `90` |
| `-r`, `--region` | Region used to break ties: `"USA / English"`, `"Europe"`, `"Japan"`, `"World"`, `"None (Raw Math)"` (shortcuts: `usa`, `eu`, `jp`, `none`) | `"USA / English"` |
| `--alternatives` | Number of alternative matches to calculate and list in the Job Receipt (1-50) | `4` |
| `--no-strip-nums` | Do NOT strip prefix numbers (e.g., `01 - Mario`) before math | `False` |
| `--no-base-only` | Do NOT prefer base versions. By default, when several versions of a game match equally well, the plain retail release wins over Beta, Proto, Demo, LodgeNet, Kiosk, Unl, Pirate, Hack, Addon/Update, Rev and Alt versions (unless your filename itself contains that tag, e.g. `(Beta)`). Same as unticking the GUI's **Prefer Base Versions** | `False` |

**Scanning & Exclusions**
| Flag | Description | Default |
|---|---|---|
| `--no-recursive` | Only scan files directly inside the source folder | `False` (Recursive) |
| `--exclude-folder` | Exclude a subfolder (relative to the source) and everything below it. Repeatable | None |
| `--exclude-ext` | Exclude a file extension (e.g., `.txt`). Repeatable | None |
| `--max-items` | Limit the number of items to scan (useful for quick tests) | `0` (Infinite) |

**Output**
| Flag | Description | Default |
|---|---|---|
| `--execute` | Actually rename and copy/move the files | `False` (Dry-Run) |
| `--inplace` | Overwrite original files directly in the source folder | `False` |
| `--keep-tree` | Preserve and mirror the source directory structure in the output folder | `False` |
| `--keep-tree-empty` | Same as `--keep-tree`, and also recreate source subfolders that end up empty in the output | `False` |
| `--keep-rejects` | Copy files below the confidence threshold to the output under their original names (ignored with `--inplace`) | `False` |
| `--duplicates` | What to do when two files get the same name: `append` (keep both, add ` (1)`) or `skip` (keep the first) | `append` |

**Performance**
| Flag | Description | Default |
|---|---|---|
| `--multithread` | Use multiple CPU cores for fuzzy matching. Worker count auto-scales to your CPU threads (leaving one free) and available RAM | `False` |
| `--workers` | Cap the number of worker processes used by `--multithread` | `0` (Auto) |

**Safety & Debugging**
| Flag | Description | Default |
|---|---|---|
| `-f`, `--force` | Bypass the safety confirmation prompt for `--inplace` | `False` |
| `--debug` | Print full error details (tracebacks), including normally ignored errors such as unreadable files | `False` |

*All CLI runs (including Dry-Runs) automatically generate a `Job_Receipt_YYYYMMDD_HHMMSS.csv` in ROMRename's `Logs/Job Receipts/` folder, listing every setting used and the action taken for each file.*
