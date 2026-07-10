#!/usr/bin/env python3
"""BenchMax Local Docker Image Builder (Python, cross-platform).

Usage:  python build_docker_images.py [--rebuild]

Builds benchmax-python (REQUIRED) and optional benchmax-* images.
By default skips images that already exist locally. Use --rebuild to force.
"""

import subprocess
import sys
from pathlib import Path


def run(cmd: str, cwd=None) -> tuple[bool, str, str]:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)


def image_exists(name: str) -> bool:
    ok, _, _ = run(f'docker image inspect {name}:latest 2>nul')
    return ok


def main():
    force_rebuild = "--rebuild" in sys.argv

    print("=" * 60)
    print("  BenchMax - Local Docker Image Builder")
    if force_rebuild:
        print("  [--rebuild mode: forcing full rebuild]")
    print("=" * 60)

    ok, out, err = run("docker --version")
    if not ok:
        print("\n[ERROR] Docker is not installed or not on PATH.\n")
        sys.exit(1)

    ok, _, _ = run("docker info")
    if not ok:
        print("\n[ERROR] Docker daemon is not running.\n")
        sys.exit(1)

    print("[OK] Docker available\n")

    docker_dir = Path(__file__).parent.parent / "backend" / "docker"
    images = [
        ("benchmax-python", "Dockerfile.python", "REQUIRED - HumanEval, BigCodeBench, LiveBench"),
        ("benchmax-node",   "Dockerfile.node",   "Aider Polyglot JavaScript"),
        ("benchmax-java",   "Dockerfile.java",   "Aider Polyglot Java"),
        ("benchmax-gcc",    "Dockerfile.gcc",    "Aider Polyglot C++"),
        ("benchmax-go",     "Dockerfile.go",     "Aider Polyglot Go"),
        ("benchmax-rust",   "Dockerfile.rust",   "Aider Polyglot Rust"),
    ]

    skipped = []
    successful = []
    failed = []

    for name, dockerfile, desc in images:
        print(f"\n{'-' * 60}")
        print(f"  {name}:latest - {desc}")
        print(f"  Dockerfile: {docker_dir / dockerfile}")

        df_path = str(docker_dir / dockerfile)
        if not Path(df_path).exists():
            print(f"  [SKIP] Dockerfile not found: {df_path}")
            continue

        if not force_rebuild and image_exists(name):
            try:
                _, size_out, _ = run(
                    f'docker image inspect {name}:latest --format "{{{{.Size}}}}"',
                )
                mb = int(size_out) / (1024 * 1024) if size_out else 0
                print(f"  [SKIP] already exists - {mb:.1f} MB (use --rebuild to force)")
            except Exception:
                print(f"  [SKIP] already exists (use --rebuild to force)")
            skipped.append(name)
            successful.append(name)
            continue

        ok, stdout, stderr = run(
            f'docker build -f "{df_path}" -t {name}:latest .',
            cwd=str(docker_dir.parent),
        )
        print(stdout[:2000] if ok else stdout)
        if not ok:
            print(f"[ERROR] Build failed for {name}:\n{stderr[:1000]}")
            failed.append(name)
            continue

        try:
            _, size_out, _ = run(
                f'docker image inspect {name}:latest --format "{{{{.Size}}}}"',
            )
            if size_out:
                mb = int(size_out) / (1024 * 1024)
                print(f"  [OK] {name}:latest - {mb:.1f} MB")
        except Exception:
            pass

        successful.append(name)

    print(f"\n{'=' * 60}")
    if successful:
        print(f"[SUCCESS] {len(successful)} image(s) ready:")
        for n in successful:
            print(f"  [OK] {n}:latest")
    else:
        print("[FAIL] No images built.")

    if skipped:
        print(f"\n  ({len(skipped)} skipped - already present)")

    if failed:
        print(f"\n[WARN] {len(failed)} image(s) failed:")
        for n in failed:
            print(f"  [FAIL] {n}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
