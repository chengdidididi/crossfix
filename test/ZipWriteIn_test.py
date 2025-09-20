import os
import zipfile
import hashlib
import io
import shutil
import re
import copy
from pathlib import Path
from PIL import Image

UTF8_FLAG= 0x800

def natural_sort_key(s):#生成自然排序键
    split_list = re.split(r'(\d+)', s)#匹配连续数字作为分隔符，以捕获组模式分割（保留分隔符）
    result_key = []
    for text_part in split_list:#分流数字和字母部分
        if text_part.isdigit():
            result_key.append(int(text_part))
        else:
            result_key.append(text_part.lower())
    return result_key
    
def find_all_zip_files(paths):
    print(f"--- 正在执行 find_all_zip_files ---")
    zip_files = set() #建立集合，可以自动去重
    for path_str in paths:
        path = Path(path_str) #转换为path对象
        if not path.exists():
            print(f"警告: 路径不存在，已跳过: {path_str}")
            continue
        if path.is_dir():
            print(f"正在扫描目录: {path_str}...")
            for root, _, files in os.walk(path): #os自带的遍历方法
                for file in files:
                    if file.lower().endswith('.zip'): #判断是否是zip结尾
                        zip_files.add(os.path.join(root, file))
        elif path.is_file():
            if path.name.lower().endswith('.zip'):
                zip_files.add(str(path))
    return list(zip_files)

def deduplicate_files_by_hash(file_paths):
    print(f"--- 正在执行 deduplicate_files_by_hash ---")
    unique_files = {}
    for file_path in file_paths:
        try:
            print(f"  -> 计算哈希值: {os.path.basename(file_path)}")
            hasher = hashlib.sha256() #sha256算法
            with open(file_path, 'rb') as f: #以原始字节流形式打开
                while chunk := f.read(8192): #python3.8特性：一次读取8192字节，直到停止
                    hasher.update(chunk) #每读一块就更新一次计算状态
            file_hash = hasher.hexdigest()
            if file_hash not in unique_files:
                unique_files[file_hash] = file_path
        except Exception as e:
            print(f"错误: 计算哈希值失败 {file_path}, 原因: {e}")
    return list(unique_files.values())

def _decode_zip_filename(filename_bytes):
    encodings_to_try = ['utf-8', 'gbk', 'shift-jis', 'big5']
    for encoding in encodings_to_try:
        try:
            return filename_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue # 如果当前编码失败，就尝试下一个
    return f"DECODE_ERROR_{filename_bytes.hex()}"# 如果所有常见编码都失败了，再返回一个安全的错误文件名

def process_single_zip(zip_path):
    print(f"--- 正在执行 process_single_zip, 处理: {os.path.basename(zip_path)} ---")
    temp_zip_path = ""
    try:
        temp_zip_path = zip_path + ".tmp" #建立临时文件
        with zipfile.ZipFile(zip_path, 'r') as zin: #只读模式打开zip文件
            filename_to_info_map = {}
            for info in zin.infolist():
                if info.flag_bits & UTF8_FLAG:
                    filename = info.filename
                else:
                    filename = _decode_zip_filename(info.filename.encode('cp437', 'replace'))
                
                if not info.is_dir():# 将解码后的文件名和原始info对象存入字典
                    filename_to_info_map[filename] = info
            correct_file_list = list(filename_to_info_map.keys())
            if not correct_file_list:
                print(f"跳过: '{os.path.basename(zip_path)}' 是空的压缩包。")
                return
            deepest_dir = os.path.dirname(max(correct_file_list, key=lambda p: p.count('/'))) #通过lambda对'/'数排序得到最深目录
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
            images_in_deepest_dir = sorted(
                [f for f in correct_file_list 
                 if os.path.dirname(f) == deepest_dir and Path(f).suffix.lower() in image_extensions], #最深目录、且符合图片后缀
                key=natural_sort_key #对筛得的图片列表进行自然排序
            )
            original_images = [img for img in images_in_deepest_dir if not Path(img).stem.endswith('-1')] #去除带-1的图片
            if len(original_images) < 2:
                print(f"跳过: '{os.path.basename(zip_path)}' 在最深层目录 '{deepest_dir}' 中原始图片不足2张。")
                return
            
            img1_name = original_images[0]
            img2_name = original_images[1]
            new_image_name = f"{Path(img1_name).stem}-1{Path(img1_name).suffix}" #新图片使用图1的名字加-1，格式与图1相同
            if new_image_name in images_in_deepest_dir:
                print(f"跳过: 文件 '{new_image_name}' 已存在，无需重复处理。") #避免重复建立跨页文件
                return
            img2_info = filename_to_info_map[img2_name]
            
            with zin.open(img2_info) as f_img2: #通过img2的元数据打开img2获得其大小信息
                img2_data = io.BytesIO(f_img2.read())
                with Image.open(img2_data) as img:
                    img2_size = img.size
            new_image_path_in_zip = os.path.join(deepest_dir, new_image_name).replace("\\", "/")
            white_image = Image.new('RGB', img2_size, 'white')
            new_image_bytes = io.BytesIO()
            image_format = 'JPEG' if Path(img1_name).suffix.lower() in ['.jpg', '.jpeg'] else Path(img1_name).suffix.lstrip('.').upper() #非jpeg格式直接取snffix去掉点
            white_image.save(new_image_bytes, format=image_format) #将白色的数据写入新建的图片字节流里
            new_image_data = new_image_bytes.getvalue() #重新提取出来稍后写入zip
            
            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zout: #以写入模式把数据写进temp文件
                for info in zin.infolist():
                    info_copy = copy.copy(info)# 为每个 info 对象创建一个副本，以安全地修改它
                    file_data = zin.read(info.filename)
                    if info.flag_bits & UTF8_FLAG:
                        correct_filename_str = info.filename
                    else:
                        correct_filename_str = _decode_zip_filename(info.filename.encode('cp437', 'replace'))
                    info_copy.filename = correct_filename_str# 清空继承来的扩展字段，让 zipfile 模块根据新文件名自动重新生成
                    info_copy.extra = b'' 
                    zout.writestr(info_copy, file_data)
                    if correct_filename_str == img1_name:
                        new_img_info = copy.copy(info_copy) 
                        new_img_info.filename = new_image_path_in_zip
                        zout.writestr(new_img_info, new_image_data)
            shutil.move(temp_zip_path, zip_path)
            print(f"成功: 已处理 '{os.path.basename(zip_path)}'。")

    except Exception as e:
        print(f"错误: 处理 '{os.path.basename(zip_path)}' 失败, 原因: {e}")
        import traceback
        traceback.print_exc()
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)

def process_entry_point(initial_paths):
    if not initial_paths:
        print("任务中止: 没有提供任何文件或文件夹路径。")
        return

    print("步骤 1/4: 开始查找所有ZIP文件...")
    all_zips = find_all_zip_files(initial_paths)
    if not all_zips:
        print("任务完成: 未在指定路径下找到任何ZIP文件。")
        return
    print(f"查找到 {len(all_zips)} 个ZIP文件。")

    print("\n步骤 2/4: 开始计算哈希值以去重...")
    unique_zips = deduplicate_files_by_hash(all_zips)
    print(f"去重后剩余 {len(unique_zips)} 个独立文件。")

    print("\n步骤 3/4: 开始逐一处理ZIP文件...")
    for i, zip_file in enumerate(unique_zips):
        print(f"\n--- ({i+1}/{len(unique_zips)}) 开始处理文件 ---")
        process_single_zip(zip_file)
    
    print("\n步骤 4/4: 所有任务已完成！")
        
if __name__ == "__main__":
    paths_to_test = []
    print("="*50)
    print("      开始执行逻辑测试脚本")
    print("="*50)
    process_entry_point(paths_to_test)
    print("\n" + "="*50)
    print("      脚本执行完毕")
    print("="*50)