import os
import zipfile
import io
import shutil
import copy
import traceback
from pathlib import Path
from PIL import Image

from ZipWriteLogic import (
    natural_sort_key,
    find_all_zip_files,
    deduplicate_files_by_hash,
    _decode_zip_filename,
    UTF8_FLAG  
)

def is_image_completely_white(img_obj: Image.Image) -> bool:
    grayscale_img = img_obj.convert('L')
    min_val, max_val = grayscale_img.getextrema()
    return min_val == 255 and max_val == 255

def remove_white_page_from_zip(zip_path, logger=print):
    logger(f"--- 正在检查文件: {os.path.basename(zip_path)} ---")
    temp_zip_path = zip_path + ".tmp"
    file_to_delete = None

    try:
        with zipfile.ZipFile(zip_path, 'r') as zin:
            # (这里的代码与之前版本相同, 使用了从 logic.py 导入的函数)
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
                logger(f"跳过: '{os.path.basename(zip_path)}' 是空的。")
                return

            deepest_dir = os.path.dirname(max(correct_file_list, key=lambda p: p.count('/')))
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
            images_in_deepest_dir = sorted(
                [f for f in correct_file_list 
                 if os.path.dirname(f) == deepest_dir and Path(f).suffix.lower() in image_extensions],
                key=natural_sort_key
            )

            if not images_in_deepest_dir:
                logger(f"跳过: 在 '{deepest_dir}' 中未找到图片。")
                return

            for i in images_in_deepest_dir:
                if i!=images_in_deepest_dir[0]:
                    target_image=i
                    break
            target_image_name = f"{Path(target_image).stem}-1{Path(target_image).suffix}"
            target_full_path = os.path.join(deepest_dir, target_image_name).replace("\\", "/")

            if target_full_path not in filename_to_info_map:
                logger(f"信息: 未找到目标文件 '{target_image_name}'，无需操作。")
                return
                
            logger(f"  -> 发现目标文件 '{target_image_name}', 正在分析内容...")
            target_info = filename_to_info_map[target_full_path]
            with zin.open(target_info) as f_target:
                img_data = io.BytesIO(f_target.read())
                with Image.open(img_data) as img:
                    if is_image_completely_white(img):
                        logger(f"  -> 确认: '{target_image_name}' 是纯白图片，准备删除。")
                        file_to_delete = target_full_path
                    else:
                        logger(f"  -> 分析完成: '{target_image_name}' 不是纯白图片，不进行操作。")
                        return

        if file_to_delete:
            with zipfile.ZipFile(zip_path, 'r') as zin:
                with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                    for info in zin.infolist():
                        if info.flag_bits & UTF8_FLAG:
                            correct_filename_str = info.filename
                        else:
                            correct_filename_str = _decode_zip_filename(info.filename.encode('cp437', 'replace'))
                        if correct_filename_str != file_to_delete:
                            info_copy = copy.copy(info)
                            info_copy.filename = correct_filename_str
                            info_copy.extra = b''
                            zout.writestr(info_copy, zin.read(info.filename))
            
            shutil.move(temp_zip_path, zip_path)
            logger(f"成功: 已从 '{os.path.basename(zip_path)}' 中删除白色扉页。")

    except Exception as e:
        logger(f"错误: 处理 '{os.path.basename(zip_path)}' 时发生错误: {e}")
        logger(traceback.format_exc())
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)

def remove_white_pages_entry_point(initial_paths, logger=print):
    if not initial_paths:
        logger("任务中止: 没有提供任何文件或文件夹路径。")
        return

    logger("步骤 1/3: 开始查找所有ZIP文件...")
    all_zips = find_all_zip_files(initial_paths, logger=logger)
    if not all_zips:
        logger("任务完成: 未找到任何ZIP文件。")
        return
    logger(f"查找到 {len(all_zips)} 个ZIP文件。")

    logger("\n步骤 2/3: 开始计算哈希值以去重...")
    unique_zips = deduplicate_files_by_hash(all_zips, logger=logger)
    logger(f"去重后剩余 {len(unique_zips)} 个独立文件。")

    logger("\n步骤 3/3: 开始逐一检查并处理ZIP文件...")
    for i, zip_file in enumerate(unique_zips):
        logger(f"\n--- ({i+1}/{len(unique_zips)}) ---")
        remove_white_page_from_zip(zip_file, logger=logger)
    
    logger("\n所有删除任务已完成！")