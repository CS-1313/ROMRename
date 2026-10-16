import os
import sys
import time
import argparse
import csv
import datetime
import file_ops
from engine import MatchEngine

def run_cli():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="ROMRename Command Line Interface")
    parser.add_argument("-s", "--source", required=True, help="Source directory containing ROMs")
    parser.add_argument("-o", "--output", help="Output directory for renamed ROMs")
    parser.add_argument("-d", "--datpack", default="DATPACK", help="Directory containing DAT files")
    parser.add_argument("-t", "--threshold", type=int, default=90, help="Fuzzy match confidence threshold (1-100)")
    parser.add_argument("-r", "--region", default="None (Raw Math)", help="Region preference (e.g., 'USA', 'Japan', or 'None (Raw Math)')")
    parser.add_argument("--no-strip-nums", action="store_true", help="Do NOT strip number prefixes from files before matching")
    parser.add_argument("--no-base-only", action="store_true", help="Do NOT prefer base versions (allow Rev/Beta)")
    parser.add_argument("--max-items", type=int, default=0, help="Maximum number of items to process (0 = infinite)")
    parser.add_argument("--execute", action="store_true", help="Actually rename and move files (Default is Dry-Run)")
    parser.add_argument("--inplace", action="store_true", help="Overwrite original files in the source directory")
    parser.add_argument("--keep-tree", action="store_true", help="Preserve and mirror the source directory structure in the output folder")
    parser.add_argument("--keep-tree-empty", action="store_true", help="Same as --keep-tree, and also recreate source subfolders that end up empty in the output")
    parser.add_argument("--multithread", action="store_true", help="Use multiple CPU cores for fuzzy matching (worker count auto-scales to your CPU threads and free RAM)")
    parser.add_argument("--workers", type=int, default=0, help="Max worker processes for --multithread (0 = auto)")
    parser.add_argument("-f", "--force", action="store_true", help="Bypass safety prompts (e.g., for --inplace)")

    args = parser.parse_args()
    if args.keep_tree_empty:
        args.keep_tree = True

    source = os.path.abspath(args.source)
    if not os.path.exists(source):
        print(f"Error: Source directory '{source}' does not exist.")
        return

    output = os.path.abspath(args.output) if args.output else source

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
    csv_writer.writerow([f"# Threshold: {args.threshold} | Region: {args.region} | Strip Nums: {not args.no_strip_nums} | Base: {not args.no_base_only}"])
    csv_writer.writerow([f"# Execute Mode: {args.execute} | In-Place: {args.inplace} | Keep Tree: {args.keep_tree} | Keep Empty Folders: {args.keep_tree_empty} | Max Items: {args.max_items}"])
    csv_writer.writerow([f"# Multithread: {args.multithread} | Workers: {args.workers or 'auto'}"])
    csv_writer.writerow(["# ---------------------------------------------------------"])
    csv_writer.writerow(["Original File", "Proposed Name", "Confidence", "Match Type", "Action Taken", "Alternatives"])

    print("\nStarting scan...")
    start_time = time.time()
    
    items_processed = 0
    hash_hits = 0
    fuzzy_hits = 0
    skipped = 0

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
                except: pass
        else:
            try:
                crc = file_ops.calc_crc(filepath)
                if crc in eng.hash_db:
                    matched_name = eng.hash_db[crc]
                    confidence = 100
                    is_hash_hit = True
            except: pass
        return matched_name, confidence, is_zip, is_hash_hit

    def finalize(rel_dir, f, rel_path, filepath, ext, is_zip, is_hash_hit, matched_name, confidence, alts, item_time):
        nonlocal items_processed, hash_hits, fuzzy_hits, skipped
        alts_str = ", ".join([f"{a[0]} ({a[1]}%)" for a in alts])
        
        items_processed += 1
        
        if confidence >= args.threshold:
            if is_hash_hit:
                hash_hits += 1
                match_type = "Hash Hit"
            else:
                fuzzy_hits += 1
                match_type = "Fuzzy"
                
            final_name = matched_name + (ext if not is_zip else ".zip")
            is_mirrored = args.inplace or args.keep_tree
            dest_rel = os.path.join(rel_dir, final_name) if (is_mirrored and rel_dir) else final_name
            print(f"[{items_processed}] {rel_path} -> {dest_rel} | {match_type} ({confidence}%) | {item_time:.2f}s")
            
            csv_action = "Renamed" if args.execute else "Simulated Rename (Dry-Run)"
            csv_writer.writerow([rel_path, matched_name, f"{confidence}%", match_type, csv_action, alts_str])

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
                    print(f"  [!] Error processing {rel_path}: {e}")
        else:
            skipped += 1
            csv_writer.writerow([rel_path, matched_name, f"{confidence}%", match_type if is_hash_hit else "Fuzzy", "Skipped (Below Threshold)", alts_str])
            print(f"[{items_processed}] {rel_path} -> Skipped (Below Threshold: {confidence}%) | {item_time:.2f}s")

    def process_completed(payload, result):
        rel_dir, f, rel_path, filepath, ext, is_zip, is_hash_hit, p_matched, p_conf, p_start = payload
        if result is not None:
            matched_name, confidence, alts = result
        else:
            alts = []
            matched_name, confidence = p_matched, p_conf
        item_time = time.time() - p_start
        finalize(rel_dir, f, rel_path, filepath, ext, is_zip, is_hash_hit, matched_name, confidence, alts, item_time)

    if args.multithread:
        import parallel
        print(parallel.describe_system())
        pipeline = parallel.OrderedMatchPipeline(eng, args.workers, print)
        print(f"Multi-Core mode: {pipeline.workers} worker process(es)")

    try:
        if args.multithread:
            submitted = 0
            for root_dir, dirs, files in os.walk(source):
                rel_dir = os.path.relpath(root_dir, source)
                if rel_dir == '.': rel_dir = ""
                for f in files:
                    if args.max_items > 0 and submitted >= args.max_items:
                        max_reached = True
                        raise KeyboardInterrupt

                    filepath = os.path.join(source, rel_dir, f) if rel_dir else os.path.join(source, f)
                    rel_path = os.path.join(rel_dir, f) if rel_dir else f
                    ext = os.path.splitext(f)[1].lower()

                    item_start = time.time()
                    matched_name, confidence, is_zip, is_hash_hit = hash_lookup(filepath, ext)
                    clean_name = os.path.splitext(f)[0]
                    match_args = None
                    if not matched_name:
                        match_args = (clean_name, clean_name, 1, args.region)
                    payload = (rel_dir, f, rel_path, filepath, ext, is_zip, is_hash_hit, matched_name, confidence, item_start)
                    submitted += 1
                    for p, result in pipeline.submit(payload, match_args):
                        process_completed(p, result)
            for p, result in pipeline.drain():
                process_completed(p, result)
        else:
            for root_dir, dirs, files in os.walk(source):
                rel_dir = os.path.relpath(root_dir, source)
                if rel_dir == '.': rel_dir = ""
                for f in files:
                    if args.max_items > 0 and items_processed >= args.max_items:
                        max_reached = True
                        raise KeyboardInterrupt  # trigger graceful exit

                    filepath = os.path.join(source, rel_dir, f) if rel_dir else os.path.join(source, f)
                    rel_path = os.path.join(rel_dir, f) if rel_dir else f
                    ext = os.path.splitext(f)[1].lower()

                    item_start = time.time()
                    matched_name, confidence, is_zip, is_hash_hit = hash_lookup(filepath, ext)
                    alts = []
                    if not matched_name:
                        clean_name = os.path.splitext(f)[0]
                        matched_name, confidence, alts = eng.find_match(clean_name, clean_name, 1, args.region)

                    item_time = time.time() - item_start
                    finalize(rel_dir, f, rel_path, filepath, ext, is_zip, is_hash_hit, matched_name, confidence, alts, item_time)

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
        else:
            folders_created = file_ops.transfer_empty_folders(source, output)
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
    if folders_created is not None:
        print(f" Empty Folders Created : {folders_created}")
    print(f" Job Receipt Saved To  : {csv_path}")
    print("="*50 + "\n")
    
    try:
        csv_file.close()
    except: pass

if __name__ == "__main__":
    run_cli()
