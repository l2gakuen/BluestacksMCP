"""Build an offline Windows bundle: dist/bluestacks-automation.zip

    python scripts/package.py [--python 3.11] [--with-python] [--with-adb]

The zip holds the source, all dependency wheels (win_amd64, for the given Python minor
version) and install.ps1. On the Windows host: unzip, run `powershell -ExecutionPolicy Bypass -File install.ps1`.
--with-adb also downloads Google's official platform-tools (adb) into the bundle.
"""
import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_VER = "3.11.9"  # last 3.11 release with a Windows installer; must match --python 3.11
PY_URL = f"https://www.python.org/ftp/python/{PY_VER}/python-{PY_VER}-amd64.exe"
ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
# Windows-only deps that pip can't see when resolving on another OS (marker: sys_platform == 'win32')
WIN_ONLY = ["pywin32>=311", "colorama>=0.4"]
COPY = ["src", "README.md", "spec.md", "TODO.md", "pyproject.toml",
        ".env.example", "config.example.yaml"]




def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default="3.11", help="target Windows Python minor version (wheels are per-version)")
    ap.add_argument("--with-python", action="store_true", help=f"bundle the official Python {PY_VER} installer")
    ap.add_argument("--with-adb", action="store_true", help="bundle Google platform-tools (adb.exe)")
    a = ap.parse_args()

    out = ROOT / "dist"
    stage = out / "bluestacks-automation"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)

    for name in COPY:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, stage / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, stage / name)
    (stage / "logs").mkdir()
    req = (ROOT / "requirements.txt").read_text().rstrip() + "\n" + "\n".join(WIN_ONLY) + "\n"
    (stage / "requirements.txt").write_text(req)
    (stage / "install.ps1").write_text((ROOT / "install.ps1").read_text().replace("3.11", a.python), encoding="utf-8")

    subprocess.run([sys.executable, "-m", "pip", "download", "-r", str(stage / "requirements.txt"),
                    "-d", str(stage / "wheels"), "--platform", "win_amd64",
                    "--python-version", a.python, "--only-binary=:all:", "--implementation", "cp"],
                   check=True)

    if a.with_python:
        if not a.python.startswith("3.11"):
            sys.exit("--with-python bundles 3.11.x; use --python 3.11")
        urllib.request.urlretrieve(PY_URL, stage / "python-installer.exe")

    if a.with_adb:
        tmp = out / "platform-tools.zip"
        urllib.request.urlretrieve(ADB_URL, tmp)
        zipfile.ZipFile(tmp).extractall(stage)
        tmp.unlink()

    archive = shutil.make_archive(str(out / "bluestacks-automation"), "zip", out, "bluestacks-automation")
    print(f"\nBundle: {archive} ({Path(archive).stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
