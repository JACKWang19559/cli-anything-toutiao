"""Install the CLI-Anything Toutiao harness."""

from pathlib import Path

from setuptools import find_namespace_packages, setup


ROOT = Path(__file__).resolve().parent

setup(
    name="cli-anything-toutiao",
    version="0.1.0",
    description="今日头条资讯读取与本地创作草稿 CLI",
    long_description=(ROOT / "cli_anything" / "toutiao" / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    license_files=["LICENSE", "THIRD_PARTY_NOTICES.md"],
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=["click>=8.1,<9", "prompt-toolkit>=3,<4"],
    extras_require={"dev": ["pytest>=8,<10"]},
    entry_points={
        "console_scripts": [
            "cli-anything-toutiao=cli_anything.toutiao.toutiao_cli:main",
            "toutiao=cli_anything.toutiao.toutiao_cli:main",
        ]
    },
    package_data={"cli_anything.toutiao": ["README.md", "skills/*.md", "utils/*.mjs", "tests/*.mjs", "tests/*.md"]},
    include_package_data=True,
    zip_safe=False,
)
