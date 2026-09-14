from pathlib import Path

# 配置导出选项
OUTPUT_FILE = "project_source_code.txt"
ROOT_DIR = "."

# 需要导出的文件后缀
INCLUDE_EXTENSIONS = {".py", ".toml", ".yaml", ".yml", ".md", ".json"}

# 需要忽略的目录（避免导出依赖库、缓存和隐藏文件夹）
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
    "data",
    "docs",
    "scripts",
    "项目规划",
    "README",
    "pyproject",
}


def is_valid_file(file_path: Path) -> bool:
    # 检查后缀名
    if file_path.suffix not in INCLUDE_EXTENSIONS:
        return False

    # 检查路径中是否包含被忽略的文件夹
    for parent in file_path.parents:
        if parent.name in EXCLUDE_DIRS:
            return False

    return True


def generate_export():
    root = Path(ROOT_DIR)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        # 遍历当前目录及所有子目录
        for file_path in root.rglob("*"):
            if file_path.is_file() and is_valid_file(file_path):
                try:
                    # 读取文件内容
                    content = file_path.read_text(encoding="utf-8")

                    # 写入显眼的文件分割线和相对路径
                    relative_path = file_path.relative_to(root)
                    outfile.write(f"{'=' * 80}\n")
                    outfile.write(f"FILE: {relative_path}\n")
                    outfile.write(f"{'=' * 80}\n\n")

                    # 写入代码
                    outfile.write(content)
                    outfile.write("\n\n")

                except Exception as e:
                    print(f"Skipping {file_path}: {e}")


if __name__ == "__main__":
    print("开始导出项目代码...")
    generate_export()
    print(f"导出完成！代码已保存至当前目录下的 {OUTPUT_FILE}")
