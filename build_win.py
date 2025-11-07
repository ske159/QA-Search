#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path


def check_and_remove_conflicts():
    """检查并移除冲突的包"""
    print("检查可能冲突的包...")

    conflicts = ['pathlib']
    for pkg in conflicts:
        try:
            result = subprocess.run([
                sys.executable, "-m", "pip", "show", pkg
            ], capture_output=True, text=True)

            if result.returncode == 0:
                print(f"发现冲突包: {pkg}，正在卸载...")
                subprocess.run([
                    sys.executable, "-m", "pip", "uninstall", "-y", pkg
                ], check=True)
                print(f"✅ 已卸载 {pkg}")
        except Exception as e:
            print(f"处理 {pkg} 时出错: {e}")


def build_windows_app():
    """构建 Windows 可执行文件"""

    # 检查并移除冲突包
    check_and_remove_conflicts()

    # 项目主入口文件
    main_script = "main.py"  # 请修改为您的实际入口文件

    # 优化的 PyInstaller 配置
    pyinstaller_cmd = [
        "pyinstaller",
        "--onefile",  # 单文件打包
        "--console",  # 控制台应用
        "--clean",  # 清理缓存
        "--name=DocSearchAssistant",
        # "--icon=assets/icon.ico",  # 如果有图标取消注释

        # 添加必要的数据文件
        "--add-data=models:models",
        "--add-data=core:core",

        # 排除不必要的模块（根据您的项目调整）
        "--exclude-module=tkinter",
        "--exclude-module=matplotlib",
        "--exclude-module=pandas",
        "--exclude-module=scipy",
        "--exclude-module=sklearn",
        "--exclude-module=PIL",

        # 显式包含必要的模块
        "--hidden-import=sentence_transformers",
        "--hidden-import=transformers.models",
        "--hidden-import=torch",
        "--hidden-import=chromadb",
        "--hidden-import=langchain",

        # 如果使用 UPX 压缩，取消下面的注释
        # "--upx-dir=/path/to/upx",

        main_script
    ]

    # 执行打包命令
    print("开始构建 Windows 可执行文件...")
    try:
        result = subprocess.run(pyinstaller_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ 构建成功！")

            # 显示输出文件信息
            dist_dir = Path("dist")
            if dist_dir.exists():
                exe_files = list(dist_dir.glob("*.exe"))
                if exe_files:
                    print(f"📁 输出文件位置: {dist_dir.absolute()}/")
                    for exe in exe_files:
                        size_mb = exe.stat().st_size / (1024 * 1024)
                        print(f"📦 生成文件: {exe.name} ({size_mb:.2f} MB)")
                else:
                    print("❌ 未找到可执行文件")
            else:
                print("❌ dist 目录不存在")
        else:
            print("❌ 构建失败！")
            print("错误输出:")
            print(result.stderr)

    except Exception as e:
        print(f"❌ 构建过程出错: {e}")


def create_requirements_check():
    """创建依赖检查脚本"""
    requirements_content = """# 最小化依赖列表
torch==2.0.1+cpu --index-url https://download.pytorch.org/whl/cpu
sentence-transformers==2.2.2
transformers==4.35.2
chromadb==0.4.22
langchain==0.0.347
pypdf2==3.0.1
python-docx==1.1.0
numpy==1.24.3
tqdm==4.66.1
"""

    with open("requirements-minimal.txt", "w") as f:
        f.write(requirements_content)
    print("✅ 已创建最小依赖文件: requirements-minimal.txt")


if __name__ == "__main__":
    print("=" * 50)
    print("DocSearch Assistant - Windows 构建工具")
    print("=" * 50)

    # 创建最小依赖文件
    create_requirements_check()

    # 构建应用
    build_windows_app()

    print("\n" + "=" * 50)
    print("构建完成！")
    print("=" * 50)