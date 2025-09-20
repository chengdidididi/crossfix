import os
import zipfile
import hashlib
import io
import shutil
import re
import copy
from pathlib import Path
from PIL import Image
import traceback

UTF8_FLAG = 0x800

def natural_sort_key(s):
    split_list = re.split(r'(\d+)', s)
    result_key = []
    for text_part in split_list:
        if text_part.isdigit():
            result_key.append(int(text_part))
        else:
            result_key.append(text_part.lower())
    return result_key

def find_all_zip_files(paths, logger=print):
    logger(f"--- 正在执行 find_all_zip_files ---")
    zip_files = set()
    for path_str in paths:
        path = Path(path_str)
        if not path.exists():
            logger(f"警告: 路径不存在，已跳过: {path_str}")
            continue
        if path.is_dir():
            logger(f"正在扫描目录: {path_str}...")
            for root, _, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.zip'):
                        zip_files.add(os.path.join(root, file))
        elif path.is_file():
            if path.name.lower().endswith('.zip'):
                zip_files.add(str(path))
    return list(zip_files)

def deduplicate_files_by_hash(file_paths, logger=print):
    logger(f"--- 正在执行 deduplicate_files_by_hash ---")
    unique_files = {}
    for file_path in file_paths:
        try:
            logger(f"  -> 计算哈希值: {os.path.basename(file_path)}")
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            file_hash = hasher.hexdigest()
            if file_hash not in unique_files:
                unique_files[file_hash] = file_path
        except Exception as e:
            logger(f"错误: 计算哈希值失败 {file_path}, 原因: {e}")
    return list(unique_files.values())

def _decode_zip_filename(filename_bytes):
    encodings_to_try = ['utf-8', 'gbk', 'shift-jis', 'big5']
    for encoding in encodings_to_try:
        try:
            return filename_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return f"DECODE_ERROR_{filename_bytes.hex()}"

def process_single_zip(zip_path, logger=print):
    logger(f"--- 正在执行 process_single_zip, 处理: {os.path.basename(zip_path)} ---")
    temp_zip_path = ""
    try:
        temp_zip_path = zip_path + ".tmp"
        with zipfile.ZipFile(zip_path, 'r') as zin:
            filename_to_info_map = {}
            for info in zin.infolist():
                if info.flag_bits & UTF8_FLAG:
                    filename = info.filename
                else:
                    filename = _decode_zip_filename(info.filename.encode('cp437', 'replace'))
                
                if not info.is_dir():
                    filename_to_info_map[filename] = info
            
            correct_file_list = list(filename_to_info_map.keys())
            if not correct_file_list:
                logger(f"跳过: '{os.path.basename(zip_path)}' 是空的压缩包。")
                return

            deepest_dir = os.path.dirname(max(correct_file_list, key=lambda p: p.count('/')))
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
            images_in_deepest_dir = sorted(
                [f for f in correct_file_list 
                 if os.path.dirname(f) == deepest_dir and Path(f).suffix.lower() in image_extensions],
                key=natural_sort_key
            )
            
            original_images = [img for img in images_in_deepest_dir if not Path(img).stem.endswith('-1')]
            if len(original_images) < 2:
                logger(f"跳过: '{os.path.basename(zip_path)}' 在最深层目录 '{deepest_dir}' 中原始图片不足2张。")
                return
            
            img1_name = original_images[0]
            img2_name = original_images[1]
            new_image_name = f"{Path(img1_name).stem}-1{Path(img1_name).suffix}"
            
            if new_image_name in images_in_deepest_dir:
                logger(f"跳过: 文件 '{new_image_name}' 已存在，无需重复处理。")
                return
            
            img2_info = filename_to_info_map[img2_name]
            
            with zin.open(img2_info) as f_img2:
                img2_data = io.BytesIO(f_img2.read())
                with Image.open(img2_data) as img:
                    img2_size = img.size
            
            new_image_path_in_zip = os.path.join(deepest_dir, new_image_name).replace("\\", "/")
            white_image = Image.new('RGB', img2_size, 'white')
            new_image_bytes = io.BytesIO()
            image_format = 'JPEG' if Path(img1_name).suffix.lower() in ['.jpg', '.jpeg'] else Path(img1_name).suffix.lstrip('.').upper()
            white_image.save(new_image_bytes, format=image_format)
            new_image_data = new_image_bytes.getvalue()
            
            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for info in zin.infolist():
                    info_copy = copy.copy(info)
                    file_data = zin.read(info.filename)
                    if info.flag_bits & UTF8_FLAG:
                        correct_filename_str = info.filename
                    else:
                        correct_filename_str = _decode_zip_filename(info.filename.encode('cp437', 'replace'))
                    
                    info_copy.filename = correct_filename_str
                    info_copy.extra = b''
                    zout.writestr(info_copy, file_data)
                    
                    if correct_filename_str == img1_name:
                        new_img_info = copy.copy(info_copy)
                        new_img_info.filename = new_image_path_in_zip
                        zout.writestr(new_img_info, new_image_data)
                        
            shutil.move(temp_zip_path, zip_path)
            logger(f"成功: 已处理 '{os.path.basename(zip_path)}'。")

    except Exception as e:
        logger(f"错误: 处理 '{os.path.basename(zip_path)}' 失败, 原因: {e}")
        # 捕获traceback信息并将其记录
        error_details = traceback.format_exc()
        logger(error_details)
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)

def process_entry_point(initial_paths, logger=print):
    if not initial_paths:
        logger("任务中止: 没有提供任何文件或文件夹路径。")
        return

    logger("步骤 1/4: 开始查找所有ZIP文件...")
    all_zips = find_all_zip_files(initial_paths, logger=logger)
    if not all_zips:
        logger("任务完成: 未在指定路径下找到任何ZIP文件。")
        return
    logger(f"查找到 {len(all_zips)} 个ZIP文件。")

    logger("\n步骤 2/4: 开始计算哈希值以去重...")
    unique_zips = deduplicate_files_by_hash(all_zips, logger=logger)
    logger(f"去重后剩余 {len(unique_zips)} 个独立文件。")

    logger("\n步骤 3/4: 开始逐一处理ZIP文件...")
    for i, zip_file in enumerate(unique_zips):
        logger(f"\n--- ({i+1}/{len(unique_zips)}) 开始处理文件 ---")
        process_single_zip(zip_file, logger=logger)
    
    logger("\n步骤 4/4: 所有任务已完成！")