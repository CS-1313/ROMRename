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
