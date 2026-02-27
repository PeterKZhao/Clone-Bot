import os
from pathlib import Path

REPLACEMENTS = {
    "yudao": "future",
    "Yudao": "Future",
    "ruoyi": "future",
    "Ruoyi": "Future",
    "RuoYi": "Future",
}

SKIP_DIRS = {".git", ".idea", "target", "node_modules", "__pycache__"}


def replace_content(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
        new_text = text
        for old, new in REPLACEMENTS.items():
            new_text = new_text.replace(old, new)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"✅ 内容替换: {path}")
    except UnicodeDecodeError:
        print(f"⚠️  跳过二进制文件: {path}")
    except Exception as e:
        print(f"❌ 处理失败 {path}: {e}")


def rename_path(path: Path) -> Path:
    new_name = path.name
    for old, new in REPLACEMENTS.items():
        new_name = new_name.replace(old, new)
    if new_name == path.name:
        return path
    new_path = path.parent / new_name
    if new_path.exists():
        print(f"⚠️  跳过重命名，目标已存在: {path}")
        return path
    path.rename(new_path)
    print(f"✅ 重命名: {path} -> {new_path}")
    return new_path


def process(root: Path):
    # 先替换文件内容（深度优先收集，避免目录改名后路径失效）
    all_files = sorted(
        (p for p in root.rglob("*") if p.is_file()
         and not any(part in SKIP_DIRS for part in p.parts)),
        key=lambda p: len(p.parts),
    )
    for f in all_files:
        replace_content(f)

    # 从最深层开始重命名（避免父目录改名后子路径失效）
    all_paths = sorted(
        (p for p in root.rglob("*")
         if not any(part in SKIP_DIRS for part in p.parts)),
        key=lambda p: -len(p.parts),
    )
    for p in all_paths:
        rename_path(p)


def main():
    root = Path(".")
    print(f"🚀 开始处理: {root.resolve()}")
    print("📋 替换规则:")
    for old, new in REPLACEMENTS.items():
        print(f"   {old} -> {new}")
    process(root)
    print("🎉 处理完成！")


if __name__ == "__main__":
    main()
