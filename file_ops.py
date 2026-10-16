import os
import zlib
import zipfile
import shutil

def calc_crc(filepath):
    prev = 0
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            prev = zlib.crc32(chunk, prev)
    return "%08X".lower() % (prev & 0xFFFFFFFF)

def process_zip_rename(src_path, out_path, final_zip_name, temp_workspace_dir):
    os.makedirs(temp_workspace_dir, exist_ok=True)
    with zipfile.ZipFile(src_path, 'r') as zf:
        inner_file = zf.namelist()[0]
        zf.extract(inner_file, temp_workspace_dir)
        
        inner_ext = os.path.splitext(inner_file)[1]
        clean_inner_name = os.path.splitext(final_zip_name)[0] + inner_ext
        clean_inner_path = os.path.join(temp_workspace_dir, clean_inner_name)
        
        os.rename(os.path.join(temp_workspace_dir, inner_file), clean_inner_path)
        
        with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as new_zf:
            new_zf.write(clean_inner_path, clean_inner_name)
            
    shutil.rmtree(temp_workspace_dir)

def copy_standard_file(src_path, out_path):
    shutil.copy2(src_path, out_path)

def transfer_empty_folders(src, out, is_excluded=None, log=print):
    """Recreate every source subfolder missing from out. Returns the number created."""
    if not out or os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(out)):
        return 0
    out_abs = os.path.normcase(os.path.abspath(out))
    created = 0
    for root_dir, dirs, _ in os.walk(src):
        rel_dir = os.path.relpath(root_dir, src)
        kept = []
        for d in dirs:
            d_rel = os.path.join(rel_dir, d) if rel_dir != '.' else d
            d_abs = os.path.normcase(os.path.abspath(os.path.join(root_dir, d)))
            if d_abs == out_abs or (is_excluded and is_excluded(d_rel)):
                continue
            kept.append(d)
            target = os.path.join(out, d_rel)
            if not os.path.isdir(target):
                try:
                    os.makedirs(target, exist_ok=True)
                    created += 1
                except Exception as e:
                    log(f"Error creating folder {d_rel}: {e}")
        dirs[:] = kept
    return created
