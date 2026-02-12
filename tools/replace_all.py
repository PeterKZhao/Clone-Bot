import os
import sys

def sanitize_sql_secrets(file_path):
    """替换 SQL 文件中的假密钥"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 替换常见的假密钥模式
        secret_replacements = {
            # Alibaba Cloud AccessKey ID (以 LTAI 开头的)
            r'LTAI[A-Za-z0-9]{12,20}': 'LTAI_REDACTED_EXAMPLE',
            # Alibaba Cloud AccessKey Secret (30+ 字符的 base64)
            r'[A-Za-z0-9+/]{30,}': 'REDACTED_SECRET_EXAMPLE',
            # Tencent Cloud Secret ID (以 AKID 开头的)
            r'AKID[A-Za-z0-9]{13,40}': 'AKID_REDACTED_EXAMPLE',
            # VolcEngine Access Key
            r'AK[A-Za-z0-9]{18,40}': 'AK_REDACTED_EXAMPLE'
        }
        
        import re
        for pattern, replacement in secret_replacements.items():
            content = re.sub(pattern, replacement, content)
        
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"✅ 已清理 SQL 文件中的敏感信息: {file_path}")
    except Exception as e:
        print(f"❌ 清理 SQL 文件时出错 {file_path}: {e}")

def replace_in_file(file_path, replacements):
    try:
        if file_path.endswith('.sql'):
            sanitize_sql_secrets(file_path)
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
    # 从环境变量读取要处理的目录路径
    source_path = os.environ.get('SOURCE_PATH', '.')
    target_directory = source_path

    replacements = {
        "yudao": "future",
        "Yudao": "Future",
        "ruoyi": "future",
        "Ruoyi": "Future",
        "RuoYi": "Future"
    }

    if not os.path.exists(target_directory):
        print(f"❌ 错误: 目录 {target_directory} 不存在")
        return

    print("🚀 开始处理文件和文件夹...")
    print(f"📋 目标目录: {target_directory}")
    print("📋 替换规则:")
    for old_str, new_str in replacements.items():
        print(f"   {old_str} -> {new_str}")

    # 切换到目标目录
    os.chdir(target_directory)
    print(f"当前工作目录: {os.getcwd()}")

    # 处理内容和文件/文件夹名
    process_directory(".", replacements)

    # 重命名根目录（上级目录）
    parent_dir = os.path.dirname(os.path.abspath("."))
    base_name = os.path.basename(parent_dir)
    new_base_name = base_name.replace("ruoyi-vue-pro", "future-vue-pro") \
                             .replace("ruoyi", "future") \
                             .replace("RuoYi", "Future")
    if new_base_name != base_name:
        new_parent = os.path.dirname(parent_dir)
        new_dir_path = os.path.join(new_parent, new_base_name)
        if not os.path.exists(new_dir_path):
            os.rename(parent_dir, new_dir_path)
            print(f"✅ 根目录重命名: {parent_dir} -> {new_dir_path}")
        else:
            print(f"⚠️ 根目录重命名目标已存在: {new_dir_path}")

    print("🎉 处理完成！")

if __name__ == "__main__":
    main()
