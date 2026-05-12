from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
ENTRY_SCRIPT = PROJECT_ROOT / "app.py"
ICON_FILE = PROJECT_ROOT / "gui" / "resource" / "icons8-boule-de-cristal-magique-100.ico"
DIST_PATH = PROJECT_ROOT / "build"
WORK_PATH = DIST_PATH / "pyinstaller-work"
SPEC_PATH = DIST_PATH / "pyinstaller-spec"
DATA_ITEMS: list[tuple[Path, str]] = [
    (PROJECT_ROOT / "mtg", "mtg"),
    (PROJECT_ROOT / "gui", "gui"),
    (PROJECT_ROOT / "data", "data"),
    (PROJECT_ROOT / "LICENSE", "."),
    (PROJECT_ROOT / "README.md", "."),
]


def ensure_paths_exist() -> None:
    required_paths = [ENTRY_SCRIPT, ICON_FILE, *[source for source, _ in DATA_ITEMS]]
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing_list = "\n".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"Fichiers ou dossiers introuvables :\n{missing_list}")


def build_pyinstaller_args(onefile: bool, console: bool, clean: bool) -> list[str]:
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 5000))

    args: list[str] = ["--noconfirm"]

    args.append("--onefile" if onefile else "--onedir")
    args.append("--console" if console else "--windowed")

    if clean:
        args.append("--clean")

    args.extend([
        "--icon",
        str(ICON_FILE),
        "--distpath",
        str(DIST_PATH),
        "--workpath",
        str(WORK_PATH),
        "--specpath",
        str(SPEC_PATH),
    ])

    for source, target in DATA_ITEMS:
        args.extend(["--add-data", f"{source};{target}"])

    args.append(str(ENTRY_SCRIPT))
    return args


def run_subprocess(command: list[str], cwd: Path) -> None:
    printable = subprocess.list2cmdline(command)
    print(f"> {printable}")
    completed = subprocess.run(command, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def build_executable(onefile: bool, console: bool, clean: bool) -> None:
    ensure_paths_exist()
    args = build_pyinstaller_args(onefile=onefile, console=console, clean=clean)
    command = [sys.executable, "-m", "PyInstaller", *args]
    run_subprocess(command, PROJECT_ROOT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onefile", action="store_true")
    parser.add_argument("--console", action="store_true")
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_executable(onefile=args.onefile, console=args.console, clean=args.clean)


if __name__ == "__main__":
    main()
