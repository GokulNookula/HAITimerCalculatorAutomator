from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

APP_NAME = "HAITimerCalculatorAutomator"
ROOT_DIR = Path(__file__).resolve().parent
VENV_DIR = ROOT_DIR / ".venv-build"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"
SPEC_FILE = ROOT_DIR / f"{APP_NAME}.spec"


def getVenvPython() -> Path:
    if platform.system().lower() == "windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def runCommand(command: list[str], description: str) -> None:
    print(f"\n==> {description}")
    print(" ".join(command))
    subprocess.check_call(command, cwd=ROOT_DIR)


def removePath(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def main() -> None:
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required to build this app.")

    if not REQUIREMENTS_FILE.exists():
        raise SystemExit(f"Missing {REQUIREMENTS_FILE.name}. Run this script from the project folder.")

    if not SPEC_FILE.exists():
        raise SystemExit(f"Missing {SPEC_FILE.name}. Run this script from the project folder.")

    print(f"Building {APP_NAME} for {platform.system()} {platform.machine()} using Python {sys.version.split()[0]}")

    if not VENV_DIR.exists():
        print("\n==> Creating local build virtual environment")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)

    venvPython = getVenvPython()

    runCommand(
        [str(venvPython), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        "Updating pip/setuptools/wheel",
    )

    runCommand(
        [str(venvPython), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
        "Installing project dependencies automatically",
    )

    removePath(ROOT_DIR / "build")
    outputExecutable = ROOT_DIR / "dist" / (f"{APP_NAME}.exe" if platform.system().lower() == "windows" else APP_NAME)
    removePath(outputExecutable)

    runCommand(
        [str(venvPython), "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)],
        "Creating the PyInstaller executable",
    )

    if not outputExecutable.exists():
        raise SystemExit(f"Build finished, but the expected executable was not found: {outputExecutable}")

    if platform.system().lower() != "windows":
        outputExecutable.chmod(outputExecutable.stat().st_mode | 0o111)

    print("\nBuild complete.")
    print(f"Executable created here: {outputExecutable}")
    print("\nImportant: build separately on Windows, macOS, and Linux. PyInstaller does not cross-compile.")
    print("End users still need Google Chrome installed. Python packages are bundled into the executable.")


if __name__ == "__main__":
    main()
