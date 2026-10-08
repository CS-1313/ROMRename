<div align="center">
  <img src="media/logo/ROMRename_logo.png" alt="ROMRename Logo" width="100%">
</div>

# ROMRename

ROMRename is a powerful, GUI-driven utility for batch renaming, organizing, and matching ROM files against official standard DAT files (.dat/.xml). It eliminates the hassle of manually renaming poorly labeled ROMs so they can be seamlessly scraped by frontends like Daijishō.

## Installation & Download Options

There are two ways to get ROMRename up and running:

### Option 1: The One-Stop Shop (Recommended)
Head over to the **[Releases](../../releases)** tab on the right side of this page and download the latest ROMRename_vX.zip. This is a complete, ready-to-run package that includes the application AND a pre-configured DATPACK folder containing all the official hashes you need. Just extract it and run.

*Included DATPACK Version: **No-Intro Love Pack (DAT) (2026-09-30)**. Special thanks and full credit to the [No-Intro Dat-O-Matic](https://datomatic.no-intro.org/) project for this daily version package!*

### Option 2: Source Code Only (Bring Your Own DATs)
If you prefer to use your own custom database files (like specific No-Intro or ReDump sets), you can download the source code here. Simply create a folder named DATPACK in the same directory as the script, drop your .dat or .xml files inside, and run the app.

## Features

- **DATPACK Integration**: Ingests massive `.dat` and `.xml` datasets (like No-Intro or ReDump) to build a master database of official game hashes and titles.
- **Smart Fuzzy Matching**: Uses advanced string comparison (`difflib`) to identify the closest official name for a ROM, even if the filename is messy, abbreviated, or missing words.
- **Ghost Math Engine**: Automatically strips out common release group tags, version numbers, and extraneous metadata `[!]`, `(USA)`, `(Rev A)` to find the core "ghost" name of the game, vastly improving match accuracy.
- **Interactive Preview (Master View)**: Before any files are touched, the app generates a virtual plan. You can review the Original Name, the Proposed Name, and the Confidence percentage in a sortable table.
- **Archive Extraction**: Natively handles `.zip` and `.7z` extraction in isolated sandbox environments during the execution phase.
- **Safe Execution**: Supports renaming files completely in-place, or copying them to a clean Output Directory.

- **Region Biasing**: Prioritize specific regions (USA, Europe, Japan, World) to automatically break ties when matching multiple regional releases - perfect for building 1G1R (1 Game, 1 ROM) collections.
- **Clean Naming Toggles**: Automatically strip numbered prefixes or prefer shorter "Base" names (dropping excessive language/revision tags) for a cleaner library.
- **Manual Action Overrides**: You are in complete control. Click any item in the interactive table to override the automatic decision, force a skip, or explicitly keep the original name.
- **Smart RAM-Recalculation**: Changed a setting (like Region Bias) after a long scan? The app recalculates the fuzzy math in pure RAM without needing to re-read your hard drive.
- **Exact Match Bypass**: Skips the heavy fuzzy math algorithm if the original filename already perfectly matches a title in the DAT database.
- **Diagnostic CSV Receipts**: Both the GUI and CLI generate highly detailed `.csv` Job Receipts capturing exact execution settings, matching stats, and skipped files for perfect QA transparency.
- **Custom File Exclusions**: Dedicated UI tab to explicitly ignore certain file types (like `.nfo` or `.txt`) so they are safely skipped during batch scans.
- **Dynamic Confidence Hiding**: Easily toggle visibility to hide skipped files, 100% hashes, or low-confidence matches to keep your Master Preview focused.

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



## ⚡ Command Line Interface (CLI)

ROMRename includes a powerful, headless CLI tailored for server admins, power users, and automated scripting. By default, the CLI is completely safe and runs in **Dry-Run Mode**, meaning it will only print a preview to your terminal and will *not* modify any files on your hard drive.

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

### CLI Flags Reference
| Flag | Description | Default |
|---|---|---|
| `-s`, `--source` | **(Required)** Path to the source directory containing ROMs | |
| `-o`, `--output` | Path to the output directory (if copying) | Same as source |
| `--execute` | Actually rename/move the files | `False` (Dry-Run) |
| `--inplace` | Overwrite original files directly in the source folder | `False` |
| `-f`, `--force` | Bypass the safety confirmation prompt for `--inplace` | `False` |
| `-t`, `--threshold` | Minimum confidence score to rename a file (1-100) | `90` |
| `-r`, `--region` | Prioritize a region (e.g., `"USA"`, `"Japan"`) | `"None (Raw Math)"`|
| `--max-items` | Limit the number of items to scan (useful for quick tests) | `0` (Infinite) |
| `--no-strip-nums` | Do NOT strip prefix numbers (e.g., `01 - Mario`) before math | `False` |
| `--no-base-only`  | Allow Rev/Beta/Demo tags in matches | `False` |

*All CLI executions automatically generate a `Job_Receipt_YYYYMMDD_HHMMSS.csv` in your source folder!*

## Roadmap
- **Multi-threading Support**: Implementing concurrent processing to analyze and rename multiple ROMs simultaneously, drastically improving completion time for massive libraries.

