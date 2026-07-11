import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
RUNTIMES_DIR = PROJECT_ROOT / ".runtimes"
RUNTIMES_DIR.mkdir(parents=True, exist_ok=True)


def _download_file(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {url.split('/')[-1]}...")
    urllib.request.urlretrieve(url, dest)


def _download_and_extract_zip(url: str, target: Path):
    target.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {url.split('/')[-1]}...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpfile = Path(tmpdir) / "archive.zip"
        urllib.request.urlretrieve(url, tmpfile)
        with zipfile.ZipFile(tmpfile) as zf:
            zf.extractall(target)


def _download_and_extract_targz(url: str, target: Path):
    target.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {url.split('/')[-1]}...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpfile = Path(tmpdir) / "archive.tar.gz"
        urllib.request.urlretrieve(url, tmpfile)
        with tarfile.open(tmpfile, "r:gz") as tf:
            tf.extractall(target)


def setup_go() -> bool:
    target = RUNTIMES_DIR / "go"
    check = target / "go" / "bin" / "go.exe"
    if check.exists():
        return False
    url = "https://go.dev/dl/go1.26.5.windows-amd64.zip"
    _download_and_extract_zip(url, target)
    return True


def setup_rust() -> bool:
    target = RUNTIMES_DIR / "rust_standalone"
    check = target / "rust-1.97.0-x86_64-pc-windows-msvc" / "rustc" / "bin" / "rustc.exe"
    if check.exists():
        return False
    url = "https://static.rust-lang.org/dist/rust-1.97.0-x86_64-pc-windows-msvc.tar.gz"
    _download_and_extract_targz(url, target)
    return True


def setup_w64devkit() -> bool:
    target = RUNTIMES_DIR / "w64devkit"
    check = target / "bin" / "gcc.exe"
    if check.exists():
        return False
    seven_zr = RUNTIMES_DIR / "7zr.exe"
    if not seven_zr.exists():
        _download_file("https://www.7-zip.org/a/7zr.exe", seven_zr)
    url = "https://github.com/skeeto/w64devkit/releases/download/v2.8.0/w64devkit-x64-2.8.0.7z.exe"
    archive_path = RUNTIMES_DIR / "w64devkit-x64-2.8.0.7z.exe"
    _download_file(url, archive_path)
    print("  Extracting...")
    subprocess.run(
        [str(seven_zr), "x", str(archive_path), f"-o{target}", "-y"],
        check=True,
        capture_output=True,
    )
    archive_path.unlink()
    return True


def setup_junit() -> bool:
    target = RUNTIMES_DIR / "jars"
    target.mkdir(parents=True, exist_ok=True)
    dest = target / "junit-platform-console-standalone-1.11.4.jar"
    if dest.exists():
        return False
    url = "https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.11.4/junit-platform-console-standalone-1.11.4.jar"
    _download_file(url, dest)
    return True


def setup_assertj() -> bool:
    target = RUNTIMES_DIR / "jars"
    target.mkdir(parents=True, exist_ok=True)
    dest = target / "assertj-core-3.27.3.jar"
    if dest.exists():
        return False
    url = "https://repo1.maven.org/maven2/org/assertj/assertj-core/3.27.3/assertj-core-3.27.3.jar"
    _download_file(url, dest)
    return True


def setup_node_packages() -> bool:
    target = RUNTIMES_DIR / "node_pkg"
    jest_check = target / "node_modules" / ".bin" / "jest.cmd"
    if jest_check.exists():
        return False
    target.mkdir(parents=True, exist_ok=True)
    pkg_json = target / "package.json"
    pkg_content = {
        "name": "benchmax-js",
        "private": True,
        "dependencies": {
            "@babel/core": "^8.0.1",
            "@babel/preset-env": "^8.0.2",
            "babel-jest": "^30.4.1",
            "jest": "^30.4.2",
        },
    }
    with open(pkg_json, "w") as f:
        json.dump(pkg_content, f, indent=2)
    print("  Running npm install...")
    subprocess.run(
        ["npm", "install", "--production", "--no-optional"],
        check=True,
        cwd=str(target),
        capture_output=True,
    )
    return True


SETUP_TASKS = [
    ("Go 1.26.5", setup_go),
    ("Rust 1.97.0", setup_rust),
    ("w64devkit (GCC)", setup_w64devkit),
    ("JUnit Console Standalone", setup_junit),
    ("AssertJ Core", setup_assertj),
    ("Node packages (Jest, Babel)", setup_node_packages),
]


def main():
    print("Setting up portable runtimes...")
    print()
    installed = 0
    skipped = 0
    for name, fn in SETUP_TASKS:
        try:
            result = fn()
            if result:
                print(f"  [OK] {name}")
                installed += 1
            else:
                print(f"  [SKIP] {name} - already installed")
                skipped += 1
        except Exception as e:
            print(f"  [FAIL] {name} - {e}")
        print()
    print(f"Installed: {installed} runtimes")
    print(f"Skipped: {skipped} already installed")


if __name__ == "__main__":
    main()
