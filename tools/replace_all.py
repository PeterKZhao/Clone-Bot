import os
import sys

def replace_in_file(file_path, replacements):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        for old_str, new_str in replacements.items():
            content = content.replace(old_str, new_str)
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"✅ 已处理文件内容: {file_path}")
    except UnicodeDecodeError:
        print(f"⚠️  跳过二进制文件: {file_path}")
    except Exception as e:
        print(f"❌ 处理文件时出错 {file_path}: {e}")

def rename_path(old_path, replacements):
    try:
        dir_name = os.path.dirname(old_path)
        base_name = os.path.basename(old_path)

        new_base_name = base_name
        for old_str, new_str in replacements.items():
            new_base_name = new_base_name.replace(old_str, new_str)

        if new_base_name != base_name:
            new_path = os.path.join(dir_name, new_base_name)
            if not os.path.exists(new_path):
                os.rename(old_path, new_path)
                print(f"✅ 重命名: {old_path} -> {new_path}")
                return new_path
            else:
                print(f"⚠️  跳过重命名，目标已存在: {old_path}")
    except Exception as e:
        print(f"❌ 重命名时出错 {old_path}: {e}")

    return old_path

def process_directory(root_dir, replacements):
    try:
        items = os.listdir(root_dir)
    except PermissionError:
        print(f"❌ 无权限访问目录: {root_dir}")
        return

    for item in items:
        item_path = os.path.join(root_dir, item)

        if os.path.isfile(item_path):
            replace_in_file(item_path, replacements)
            new_path = rename_path(item_path, replacements)
            if new_path != item_path:
                item_path = new_path
        elif os.path.isdir(item_path):
            new_path = rename_path(item_path, replacements)
            if new_path != item_path:
                item_path = new_path

    try:
        items = os.listdir(root_dir)
    except PermissionError:
        return

    for item in items:
        item_path = os.path.join(root_dir, item)
        if os.path.isdir(item_path):
            process_directory(item_path, replacements)

def main():
    target_directory = "."

    replacements = {
        "yudao": "future",
        "Yudao": "Future",
        "ruoyi": "future",
        "Ruoyi": "Future",
        "RuoYi": "Future"
    }

    print("🚀 开始处理文件和文件夹...")
    print(f"📋 目标目录: {os.path.abspath(target_directory)}")
    print("📋 替换规则:")
    for old_str, new_str in replacements.items():
        print(f"   {old_str} -> {new_str}")

    # 处理内容和文件/文件夹名
    process_directory(target_directory, replacements)

    print("🎉 处理完成！")

if __name__ == "__main__":
    main()
