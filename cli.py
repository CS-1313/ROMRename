import os
import sys
import time
import argparse
import csv
import datetime
import file_ops
from engine import MatchEngine

REGIONS = ["USA / English", "Europe", "Japan", "World", "None (Raw Math)"]
REGION_ALIASES = {
    "usa / english": "USA / English", "usa": "USA / English", "us": "USA / English", "en": "USA / English", "english": "USA / English",
    "europe": "Europe", "eu": "Europe",
    "japan": "Japan", "jp": "Japan",
    "world": "World",
    "none (raw math)": "None (Raw Math)", "none": "None (Raw Math)", "raw": "None (Raw Math)",
}

def parse_region(value):
    region = REGION_ALIASES.get(value.strip().lower())
    if region is None:
        raise argparse.ArgumentTypeError(f"invalid region '{value}'. Choose from: " + ", ".join(f"'{r}'" for r in REGIONS))
    return region

def run_cli():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="ROMRename Command Line Interface. Runs in Dry-Run mode unless --execute is given. Subfolders are scanned recursively unless --no-recursive is given.",
        epilog='Example: python main.py -s "E:\\Games" -o "E:\\Games_Renamed" --keep-tree-empty --keep-rejects --multithread --execute')

    g_paths = parser.add_argument_group("Paths")
    g_paths.add_argument("-s", "--source", required=True, help="Source directory containing ROMs")
    g_paths.add_argument("-o", "--output", help="Output directory for renamed ROMs (default: same as source)")
    g_paths.add_argument("-d", "--datpack", default="DATPACK", help="Directory containing DAT files (default: DATPACK)")

    g_match = parser.add_argument_group("Matching")
    g_match.add_argument("-t", "--threshold", type=int, default=90, help="Fuzzy match confidence threshold, 1-100 (default: 90)")
    g_match.add_argument("-r", "--region", type=parse_region, default="USA / English", metavar="REGION", help="Region preference used to break ties: 'USA / English' (or usa, us, en), 'Europe' (or eu), 'Japan' (or jp), 'World', 'None (Raw Math)' (or none, raw). Default: 'USA / English'")
    g_match.add_argument("--alternatives", type=int, default=4, metavar="N", help="Number of alternative matches to calculate and list in the Job Receipt, 1-50 (default: 4)")
    g_match.add_argument("--no-strip-nums", action="store_true", help="Do NOT strip number prefixes (e.g. '01 - Mario') from files before matching")
    g_match.add_argument("--no-base-only", action="store_true", help="Do NOT prefer base versions (recorded in the Job Receipt only; currently has no effect on matching)")

    g_scan = parser.add_argument_group("Scanning & Exclusions")
    g_scan.add_argument("--no-recursive", action="store_true", help="Only scan files directly inside the source folder (subfolders are scanned by default)")
    g_scan.add_argument("--exclude-folder", action="append", default=[], metavar="FOLDER", help="Exclude a subfolder (relative to the source, e.g. 'arcade' or 'anbernic/saves'). Repeat for more")
    g_scan.add_argument("--exclude-ext", action="append", default=[], metavar="EXT", help="Exclude a file extension (e.g. '.txt' or 'nfo'). Repeat for more")
    g_scan.add_argument("--max-items", type=int, default=0, help="Maximum number of items to process (default: 0 = infinite)")

    g_out = parser.add_argument_group("Output")
    g_out.add_argument("--execute", action="store_true", help="Actually rename and copy/move files (default is Dry-Run)")
    g_out.add_argument("--inplace", action="store_true", help="Overwrite original files in the source directory")
    g_out.add_argument("--keep-tree", action="store_true", help="Preserve and mirror the source directory structure in the output folder")
    g_out.add_argument("--keep-tree-empty", action="store_true", help="Same as --keep-tree, and also recreate source subfolders that end up empty in the output")
    g_out.add_argument("--keep-rejects", action="store_true", help="Copy files below the threshold to the output folder under their original names (ignored with --inplace)")
    g_out.add_argument("--duplicates", choices=["append", "skip"], default="append", help="When two files get the same name: 'append' keeps both by adding ' (1)', ' (2)'..., 'skip' keeps only the first (default: append)")

    g_perf = parser.add_argument_group("Performance")
    g_perf.add_argument("--multithread", action="store_true", help="Use multiple CPU cores for fuzzy matching (worker count auto-scales to your CPU threads and free RAM)")
    g_perf.add_argument("--workers", type=int, default=0, help="Max worker processes for --multithread (default: 0 = auto)")

    g_misc = parser.add_argument_group("Safety & Debugging")
    g_misc.add_argument("-f", "--force", action="store_true", help="Bypass safety prompts (e.g., for --inplace)")
    g_misc.add_argument("--debug", action="store_true", help="Print full error details (tracebacks), including errors that are normally ignored such as unreadable files")

    args = parser.parse_args()
    if not 1 <= args.alternatives <= 50:
        parser.error("--alternatives must be between 1 and 50")
    if args.keep_tree_empty:
        args.keep_tree = True

    source = os.path.abspath(args.source)
    if not os.path.exists(source):
        print(f"Error: Source directory '{source}' does not exist.")
        return

    output = os.path.abspath(args.output) if args.output else source

    excluded_folders = []
    for d in args.exclude_folder:
        if os.path.isabs(d):
            d = os.path.relpath(d, source)
        d = os.path.normpath(d.strip().strip("\\/"))
        if d and d != '.':
            excluded_folders.append(os.path.normcase(d))
    excluded_exts = sorted({"." + e.strip().lower().lstrip(".") for e in args.exclude_ext if e.strip().lstrip(".")})

    def is_excluded_dir(rel_dir):
        rd = os.path.normcase(rel_dir)
        return any(rd == ef or rd.startswith(ef + os.sep) for ef in excluded_folders)

    def is_excluded(rel_dir, ext):
        return ext in excluded_exts or (bool(rel_dir) and is_excluded_dir(rel_dir))

    def iter_source_files():
        for root_dir, dirs, files in os.walk(source):
            rel_dir = os.path.relpath(root_dir, source)
            if rel_dir == '.': rel_dir = ""
            if args.no_recursive:
                dirs[:] = []
            for f in files:
                yield rel_dir, f

    def debug_log(context, e=None):
        if args.debug:
            import traceback
            print(f"  [DEBUG] {context}" + (f": {e}" if e is not None else ""))
            if e is not None:
                for line in traceback.format_exc().splitlines():
                    if line.strip(): print(f"  [DEBUG] {line}")

    def report_error(context, e):
        print(f"  [!] {context}: {e}")
        debug_log(context, e)

    if args.execute and args.inplace:
        if not args.force:
            print("\n[!!! CRITICAL WARNING !!!]")
            print("You have selected --inplace execution. This will PERMANENTLY overwrite and rename")
            print(f"files directly inside your source directory:\n-> {source}\n")
            confirm = input("Enter 'OVERWRITE' to proceed, or anything else to CANCEL: ")
            if confirm.strip() != "OVERWRITE":
                print("\nOperation cancelled by user.")
                return
        else:
            print("\n[!] WARNING: In-place execution triggered with --force. Bypassing safety prompt.")

    print("\n" + "="*50)
    print(" ROMRename CLI - " + ("EXECUTE MODE" if args.execute else "DRY-RUN MODE"))
    print("="*50)

    eng = MatchEngine()
    dat_dir = os.path.abspath(args.datpack)
    print(f"Loading DATs from: {dat_dir}")
    if not eng.load_dats(dat_dir, print):
        print("Failed to load DAT files. Exiting.")
        return

    eng.is_raw_math = (args.region == "None (Raw Math)")
    eng.strip_n = not args.no_strip_nums
    eng.update_math(eng.is_raw_math, eng.strip_n, print)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    app_dir = os.path.dirname(os.path.abspath(__file__))
    receipts_dir = os.path.join(app_dir, "Logs", "Job Receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    csv_path = os.path.join(receipts_dir, f"Job_Receipt_{ts}.csv")
    csv_file = open(csv_path, 'w', newline='', encoding='utf-8')
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow([f"# ROMRename CLI {'EXECUTE' if args.execute else 'DRY-RUN'} Log"])
    csv_writer.writerow([f"# Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
    csv_writer.writerow([f"# Source: {source}"])
    csv_writer.writerow([f"# Output: {output}"])
    csv_writer.writerow(["# --- SETTINGS ---"])
    csv_writer.writerow([f"# Threshold: {args.threshold} | Region: {args.region} | Strip Nums: {not args.no_strip_nums} | Base: {not args.no_base_only} | Alternatives: {args.alternatives}"])
    csv_writer.writerow([f"# Duplicates: {args.duplicates} | Recursive: {not args.no_recursive} | Excluded Folders: {', '.join(excluded_folders) or 'None'} | Excluded Exts: {', '.join(excluded_exts) or 'None'} | Debug: {args.debug}"])
    csv_writer.writerow([f"# Execute Mode: {args.execute} | In-Place: {args.inplace} | Keep Tree: {args.keep_tree} | Keep Empty Folders: {args.keep_tree_empty} | Keep Rejects: {args.keep_rejects} | Max Items: {args.max_items}"])
    csv_writer.writerow([f"# Multithread: {args.multithread} | Workers: {args.workers or 'auto'}"])
    csv_writer.writerow(["# ---------------------------------------------------------"])
    csv_writer.writerow(["Original File", "Proposed Name", "Confidence", "Match Type", "Action Taken", "Alternatives"])

    print("\nStarting scan...")
    start_time = time.time()
    
    items_processed = 0
    hash_hits = 0
    rejects_kept = 0
    copy_rejects = args.keep_rejects and not args.inplace and os.path.normcase(output) != os.path.normcase(source)
    fuzzy_hits = 0
    skipped = 0
    excluded_count = 0
    duplicates_appended = 0
    duplicates_skipped = 0
    seen_names = {}

    pipeline = None
    max_reached = False
    interrupted = False

    def hash_lookup(filepath, ext):
        matched_name = ""
        confidence = 0
        is_zip = False
        is_hash_hit = False
        if ext in ['.zip', '.7z']:
            is_zip = True
            if ext == '.zip':
                try:
                    import zipfile
                    with zipfile.ZipFile(filepath, 'r') as zf:
                        for info in zf.infolist():
                            crc = "%08X".lower() % (info.CRC & 0xFFFFFFFF)
                            if crc == "00000000": continue
                            if crc in eng.hash_db:
                                matched_name = eng.hash_db[crc]
                                confidence = 100
                                is_hash_hit = True
                                break
                except Exception as e:
                    debug_log(f"Could not read zip {filepath}", e)
        else:
            try:
                crc = file_ops.calc_crc(filepath)
                if crc in eng.hash_db:
                    matched_name = eng.hash_db[crc]
                    confidence = 100
                    is_hash_hit = True
            except Exception as e:
                debug_log(f"Could not hash {filepath}", e)
        return matched_name, confidence, is_zip, is_hash_hit

    def finalize(rel_dir, f, rel_path, filepath, ext, is_zip, is_hash_hit, matched_name, confidence, alts, item_time, excluded=False):
        nonlocal items_processed, hash_hits, fuzzy_hits, skipped, rejects_kept, excluded_count, duplicates_appended, duplicates_skipped
        alts_str = ", ".join([f"{a[0]} ({a[1]}%)" for a in alts])
        
        items_processed += 1
        
        if excluded:
            excluded_count += 1
            csv_writer.writerow([rel_path, "", "0%", "Excluded", "Skipped (Excluded)", ""])
            print(f"[{items_processed}] {rel_path} -> Skipped (Excluded)")
        elif confidence >= args.threshold and confidence > 0:
            if is_hash_hit:
                hash_hits += 1
                match_type = "Hash Hit"
            else:
                fuzzy_hits += 1
                match_type = "Fuzzy"
                
            out_ext = ext if not is_zip else ".zip"
            final_name = matched_name + out_ext
            is_mirrored = args.inplace or args.keep_tree
            dest_rel = os.path.join(rel_dir, final_name) if (is_mirrored and rel_dir) else final_name
            dup_key = os.path.normcase(dest_rel)
            dup_note = ""
            if dup_key in seen_names:
                if args.duplicates == "skip":
                    duplicates_skipped += 1
                    csv_action = "Skipped (Duplicate)"
                    csv_writer.writerow([rel_path, matched_name, f"{confidence}%", match_type, csv_action, alts_str])
                    print(f"[{items_processed}] {rel_path} -> Skipped (Duplicate of {dest_rel}) | {match_type} ({confidence}%) | {item_time:.2f}s")
                    return
                while True:
                    seen_names[dup_key] += 1
                    final_name = f"{matched_name} ({seen_names[dup_key]}){out_ext}"
                    dest_rel = os.path.join(rel_dir, final_name) if (is_mirrored and rel_dir) else final_name
                    if os.path.normcase(dest_rel) not in seen_names:
                        break
                seen_names[os.path.normcase(dest_rel)] = 0
                duplicates_appended += 1
                dup_note = " (Appended)"
            else:
                seen_names[dup_key] = 0
            print(f"[{items_processed}] {rel_path} -> {dest_rel} | {match_type}{dup_note} ({confidence}%) | {item_time:.2f}s")
            
            csv_action = ("Renamed" if args.execute else "Simulated Rename (Dry-Run)") + dup_note
            csv_writer.writerow([rel_path, os.path.splitext(final_name)[0] if dup_note else matched_name, f"{confidence}%", match_type, csv_action, alts_str])

            if args.execute:
                out_path = os.path.join(output, dest_rel)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                try:
                    if is_zip:
                        file_ops.process_zip_rename(filepath, out_path, os.path.basename(final_name), "TEMP_WORKSPACE")
                        if args.inplace and filepath != out_path:
                            os.remove(filepath)
                    else:
                        if args.inplace:
                            os.rename(filepath, out_path)
                        else:
                            file_ops.copy_standard_file(filepath, out_path)
                except Exception as e:
                    report_error(f"Error processing {rel_path}", e)
        elif copy_rejects:
            rejects_kept += 1
            dest_rel = rel_path if args.keep_tree else f
            csv_action = "Kept Original Name" if args.execute else "Simulated Keep Original Name (Dry-Run)"
            csv_writer.writerow([rel_path, matched_name, f"{confidence}%", "Fuzzy", csv_action, alts_str])
            print(f"[{items_processed}] {rel_path} -> {dest_rel} | Reject, Original Name Kept (Below Threshold: {confidence}%) | {item_time:.2f}s")

            if args.execute:
                out_path = os.path.join(output, dest_rel)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                try:
                    file_ops.copy_standard_file(filepath, out_path)
                except Exception as e:
                    report_error(f"Error processing {rel_path}", e)
        else:
            skipped += 1
            csv_writer.writerow([rel_path, matched_name, f"{confidence}%", "Hash Hit" if is_hash_hit else "Fuzzy", "Skipped (Below Threshold)", alts_str])
            print(f"[{items_processed}] {rel_path} -> Skipped (Below Threshold: {confidence}%) | {item_time:.2f}s")

    def process_completed(payload, result):
        rel_dir, f, rel_path, filepath, ext, is_zip, is_hash_hit, p_matched, p_conf, p_start, excluded = payload
        if result is not None:
            matched_name, confidence, alts = result
        else:
            alts = []
            matched_name, confidence = p_matched, p_conf
        item_time = time.time() - p_start
        finalize(rel_dir, f, rel_path, filepath, ext, is_zip, is_hash_hit, matched_name, confidence, alts, item_time, excluded)

    def prepare(rel_dir, f):
        filepath = os.path.join(source, rel_dir, f) if rel_dir else os.path.join(source, f)
        rel_path = os.path.join(rel_dir, f) if rel_dir else f
        ext = os.path.splitext(f)[1].lower()
        item_start = time.time()
        excluded = is_excluded(rel_dir, ext)
        matched_name, confidence, is_zip, is_hash_hit = ("", 0, ext in ['.zip', '.7z'], False) if excluded else hash_lookup(filepath, ext)
        match_args = None
        if not excluded and not matched_name:
            clean_name = os.path.splitext(f)[0]
            match_args = (clean_name, clean_name, args.alternatives, args.region)
        payload = (rel_dir, f, rel_path, filepath, ext, is_zip, is_hash_hit, matched_name, confidence, item_start, excluded)
        return payload, match_args

    if args.multithread:
        import parallel
        print(parallel.describe_system())
        pipeline = parallel.OrderedMatchPipeline(eng, args.workers, print)
        print(f"Multi-Core mode: {pipeline.workers} worker process(es)")

    try:
        submitted = 0
        for rel_dir, f in iter_source_files():
            if args.max_items > 0 and submitted >= args.max_items:
                max_reached = True
                raise KeyboardInterrupt  # trigger graceful exit
            payload, match_args = prepare(rel_dir, f)
            submitted += 1
            if pipeline is not None:
                for p, result in pipeline.submit(payload, match_args):
                    process_completed(p, result)
            else:
                process_completed(payload, eng.find_match(*match_args) if match_args else None)
        if pipeline is not None:
            for p, result in pipeline.drain():
                process_completed(p, result)

    except KeyboardInterrupt:
        interrupted = not max_reached
        print("\n\n[!] Process Interrupted (Graceful Shutdown).")
        if pipeline is not None and max_reached:
            for p, result in pipeline.drain():
                process_completed(p, result)
        elif pipeline is not None:
            pipeline.close(cancel=True)
    finally:
        if pipeline is not None:
            pipeline.close()

    folders_created = None
    if args.execute and args.keep_tree_empty and not args.inplace:
        if interrupted:
            print("[!] Skipping empty folder transfer because the run was interrupted.")
        elif args.no_recursive:
            print("[!] Skipping empty folder transfer because --no-recursive was given.")
        else:
            folders_created = file_ops.transfer_empty_folders(source, output, is_excluded_dir if excluded_folders else None)
            print(f"Transferred {folders_created} empty folder(s).")
            csv_writer.writerow([f"# Empty Folders Created: {folders_created}"])

    total_time = time.time() - start_time
    avg_time = (total_time / items_processed) if items_processed > 0 else 0

    print("\n" + "="*50)
    print(" FINAL SUMMARY")
    print("="*50)
    print(f" Total Items Processed : {items_processed}")
    print(f" Total Execution Time  : {total_time:.2f} seconds")
    print(f" Average Time per Item : {avg_time:.3f} seconds")
    print(f" 100% Hash Hits        : {hash_hits}")
    print(f" Fuzzy Math Hits       : {fuzzy_hits}")
    print(f" Items Skipped         : {skipped}")
    if excluded_count:
        print(f" Items Excluded        : {excluded_count}")
    if duplicates_appended or duplicates_skipped:
        print(f" Duplicates            : {duplicates_appended} appended, {duplicates_skipped} skipped")
    if args.keep_rejects:
        print(f" Rejects Kept (Orig.)  : {rejects_kept}")
    if folders_created is not None:
        print(f" Empty Folders Created : {folders_created}")
    print(f" Job Receipt Saved To  : {csv_path}")
    print("="*50 + "\n")
    
    try:
        csv_file.close()
    except: pass

if __name__ == "__main__":
    run_cli()
