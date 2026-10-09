"""从源码打包 Windows 单文件 GUI；打包工具版本由 requirements-build.txt 固定。"""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
                    "--name", "TargetedDatasetGen", str(root / "app.py")], cwd=root, check=True)
