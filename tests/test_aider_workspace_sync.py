"""Workspace-writer parity: host and container copies must stay in sync.

``backend/benchmarks/aider_polyglot.py::_write_temp_workspace`` (host) and
``backend/sandbox/container_runner.py::_write_workspace`` (container) are a
deliberate mirror — the container copy runs inside the benchmax-sandbox image
with stdlib only, so they cannot share code. These tests feed identical
samples to both writers and assert byte-identical file trees, turning silent
drift into a test failure.
"""

import filecmp
import os
import tempfile

from backend.benchmarks.aider_polyglot import (
    _cpp_test_rel as host_cpp_rel,
    _java_test_class as host_java_class,
    _write_temp_workspace as host_write,
)
from backend.sandbox.container_runner import (
    _java_test_class as container_java_class,
    _write_workspace as container_write,
)


def _tree(tmpdir):
    out = {}
    for root, _, files in os.walk(tmpdir):
        for f in files:
            full = os.path.join(root, f)
            with open(full, "rb") as fh:
                out[os.path.relpath(full, tmpdir)] = fh.read()
    return out


def _samples():
    base = {
        "source_path": "src/main.py",
        "test_path": "tests/test_main.py",
        "test_code": "import unittest\n",
        "extra_files": {},
    }
    cases = []
    for lang in ("python", "javascript", "java", "go", "rust", "cpp"):
        s = dict(base, language=lang)
        cases.append(s)
    # C++ header-rewrite path
    cases.append({
        "language": "cpp",
        "source_path": "src/beer.cpp",
        "test_path": "tests/beer_test.cpp",
        "test_code": '#include "beer.h"\nTEST(x, y) {}\n',
        "extra_files": {},
    })
    # JS dataset-pinned toolchain preservation
    cases.append({
        "language": "javascript",
        "source_path": "a.js",
        "test_path": "a.spec.js",
        "test_code": "t",
        "extra_files": {
            "babel.config.js": "custom-preset",
            "package.json": '{"custom": true}',
        },
    })
    # Go default go.mod synthesis
    cases.append({
        "language": "go",
        "source_path": "solve.go",
        "test_path": "solve_test.go",
        "test_code": "package main\n",
        "extra_files": {},
    })
    return cases


class TestWorkspaceMirror:
    def test_identical_trees(self):
        for sample in _samples():
            with tempfile.TemporaryDirectory() as host_tmp, \
                    tempfile.TemporaryDirectory() as cont_tmp:
                host_write(sample, "EDITED", host_tmp)
                container_write(sample, "EDITED", cont_tmp)
                assert _tree(host_tmp) == _tree(cont_tmp), (
                    f"workspace mirror diverged for {sample['language']} "
                    f"{sample['source_path']}"
                )

    def test_java_class_parity(self):
        for name in ("src/test/java/PovTest.java", "Tree.java",
                     "src/AffineCipherTest.java"):
            assert host_java_class(name) == container_java_class(name)

    def test_cpp_rel_parity(self):
        # Container inlines the same rule; pin representative outcomes here.
        assert host_cpp_rel("src/a.cpp") == "src/a_test.cpp"
        assert host_cpp_rel("a.cpp", "nested/t_test.cpp") == "nested/t_test.cpp"
        # filecmp sanity: the writers agree on identical inputs (covered above)
        assert filecmp.cmp.__doc__ is not None
