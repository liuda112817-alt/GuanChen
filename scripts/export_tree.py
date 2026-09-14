from pathlib import Path

# 配置导出选项
OUTPUT_FILE = "project_directory_tree.txt"
ROOT_DIR = "."

# 需要忽略的目录（保持画面整洁）
EXCLUDE_DIRS = {
    ".venv",
    "venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    ".idea",
    "build",
    "dist",
    ".mypy_cache",
}


def generate_tree(dir_path: Path, prefix: str, outfile):
    """
    递归生成树状结构
    """
    # 获取当前目录下的所有内容
    items = list(dir_path.iterdir())

    # 过滤掉黑名单中的文件/文件夹
    items = [item for item in items if item.name not in EXCLUDE_DIRS]

    # 排序：文件夹在前，文件在后，同类按名称字母排序
    items.sort(key=lambda x: (x.is_file(), x.name.lower()))

    count = len(items)
    for index, item in enumerate(items):
        is_last = index == count - 1
        # 连接符判断
        connector = "└── " if is_last else "├── "

        # 写入文件
        outfile.write(f"{prefix}{connector}{item.name}\n")

        # 如果是文件夹，继续往下一层递归
        if item.is_dir():
            extension = "    " if is_last else "│   "
            generate_tree(item, prefix + extension, outfile)


def export_tree():
    root = Path(ROOT_DIR)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        # 写入根目录名称
        outfile.write(f"{root.resolve().name}/\n")
        generate_tree(root, "", outfile)


if __name__ == "__main__":
    print("开始导出项目目录树...")
    export_tree()
    print(f"导出完成！目录树已保存至当前目录下的 {OUTPUT_FILE}")
