import os
import sys
import time
import argparse
import file_ops
from engine import MatchEngine

def run_cli():
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

    args = parser.parse_args()

    source = os.path.abspath(args.source)
    if not os.path.exists(source):
        print(f"Error: Source directory '{source}' does not exist.")
        return

    output = os.path.abspath(args.output) if args.output else source

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

    print("\nStarting scan...")
    start_time = time.time()
    
    items_processed = 0
    hash_hits = 0
    fuzzy_hits = 0
    skipped = 0

    try:
        for root_dir, dirs, files in os.walk(source):
            rel_dir = os.path.relpath(root_dir, source)
            if rel_dir == '.': rel_dir = ""
            
            for f in files:
                if args.max_items > 0 and items_processed >= args.max_items:
                    raise KeyboardInterrupt  # trigger graceful exit

                filepath = os.path.join(source, rel_dir, f) if rel_dir else os.path.join(source, f)
                ext = os.path.splitext(f)[1].lower()
                
                item_start = time.time()
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
                
                if not matched_name:
                    clean_name = os.path.splitext(f)[0]
                    matched_name, confidence, _ = eng.find_match(clean_name, clean_name, 1, args.region)
                
                item_time = time.time() - item_start
                items_processed += 1
                
                if confidence >= args.threshold:
                    if is_hash_hit:
                        hash_hits += 1
                        match_type = "Hash Hit"
                    else:
                        fuzzy_hits += 1
                        match_type = "Fuzzy"
                        
                    final_name = matched_name + (ext if not is_zip else ".zip")
                    print(f"[{items_processed}] {f} -> {final_name} | {match_type} ({confidence}%) | {item_time:.2f}s")
                    
                    if args.execute:
                        out_path = os.path.join(output, final_name)
                        os.makedirs(os.path.dirname(out_path), exist_ok=True)
                        try:
                            if is_zip:
                                file_ops.process_zip_rename(filepath, out_path, final_name, "TEMP_WORKSPACE")
                                if args.inplace and f != final_name:
                                    os.remove(filepath)
                            else:
                                if args.inplace:
                                    os.rename(filepath, out_path)
                                else:
                                    file_ops.copy_standard_file(filepath, out_path)
                        except Exception as e:
                            print(f"  [!] Error processing {f}: {e}")
                else:
                    skipped += 1
                    print(f"[{items_processed}] {f} -> Skipped (Below Threshold: {confidence}%) | {item_time:.2f}s")

    except KeyboardInterrupt:
        print("\n\n[!] Process Interrupted (Graceful Shutdown).")

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
    print("="*50 + "\n")

if __name__ == "__main__":
    run_cli()
