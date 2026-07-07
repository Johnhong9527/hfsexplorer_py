#!/usr/bin/env python3
"""HFSExplorer 安装脚本"""

from setuptools import setup, find_packages

setup(
    name="hfsexplorer",
    version="1.0.0",
    description="HFS/HFS+/HFSX 文件系统浏览器 - 支持读写和 FileVault 2 加密",
    author="HFSExplorer Team",
    author_email="dev@hfsexplorer.org",
    url="https://github.com/hfsexplorer/hfsexplorer",
    license="GPL-3.0-or-later",
    packages=find_packages(where="."),
    package_dir={"": "."},
    python_requires=">=3.9",
    install_requires=[
        "PyQt6>=6.4.0",
        "pycryptodome>=3.15.0",
        "colorama>=0.4.6",
        "tqdm>=4.65.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "flake8>=6.0",
            "mypy>=1.0",
            "black>=23.0",
            "isort>=5.0",
        ],
        "docs": [
            "sphinx>=6.0",
            "sphinx-rtd-theme>=1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "hfsexplorer=src.gui.main_window:main",
            "unhfs=src.cli.unhfs:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Filesystems",
    ],
)