# Python 3.6 Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the pyCANape `v0.6.2` codebase installable and importable on CPython 3.6 with deterministic compatible dependencies.

**Architecture:** Preserve the `src/pycanape` runtime API and DLL binding behavior. Replace the Python 3.7-only package metadata with a Python 3.6-compatible setuptools configuration, add executable compatibility checks, and make Windows CI install and import the package on Python 3.6.

**Tech Stack:** CPython 3.6, setuptools 59.6, wheel 0.37, unittest, ctypes, NumPy 1.19.5, psutil 5.9.8, backports.cached-property 1.0.2, GitHub Actions.

---

### Task 1: Specify Python 3.6 packaging behavior

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_python36_compatibility.py`
- Read: `pyproject.toml`

- [ ] **Step 1: Write the failing metadata tests**

Create tests that require `setup.cfg`, Python `>=3.6`, the Python 3.6 NumPy pin, cached-property backport, typing-extensions pin, and Python 3.6 CI coverage:

```python
import configparser
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class Python36PackagingTests(unittest.TestCase):
    def setUp(self):
        self.config = configparser.ConfigParser()
        self.config.read(str(ROOT / "setup.cfg"), encoding="utf-8")

    def test_package_declares_python36_support(self):
        self.assertEqual(self.config["options"]["python_requires"], ">=3.6")

    def test_python36_dependencies_are_pinned(self):
        requirements = self.config["options"]["install_requires"]
        self.assertIn('numpy==1.19.5; python_version < "3.7"', requirements)
        self.assertIn('psutil==5.9.8; python_version < "3.7"', requirements)
        self.assertIn('backports.cached-property==1.0.2; python_version < "3.8"', requirements)
        self.assertIn('typing-extensions==4.1.1; python_version < "3.8"', requirements)

    def test_ci_includes_python36(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
        self.assertIn('python-version: ["3.6", "3.10"]', workflow)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_python36_compatibility -v`

Expected: errors because `setup.cfg` does not exist and failure because CI does not include Python 3.6.

- [ ] **Step 3: Commit the failing tests**

Run:

```text
git add tests/__init__.py tests/test_python36_compatibility.py
git commit -m "test: specify Python 3.6 compatibility"
```

### Task 2: Replace incompatible packaging metadata

**Files:**
- Create: `setup.cfg`
- Modify: `pyproject.toml`
- Test: `tests/test_python36_compatibility.py`

- [ ] **Step 1: Add Python 3.6-compatible package metadata**

Create `setup.cfg` with this content:

```ini
[metadata]
name = pyCANape
version = 0.6.2
description = Pythonic wrapper around the VECTOR CANape API
long_description = file: README.md
long_description_content_type = text/markdown
license = MIT
author = Artur Drogunow
author_email = artur.drogunow@zf.com
url = https://github.com/Thri1ly/py_canape
project_urls =
    Documentation = https://pycanape.readthedocs.io
    Issues = https://github.com/Thri1ly/py_canape/issues
    Source = https://github.com/Thri1ly/py_canape
keywords = CANape, Measurement, Calibration, automotive
classifiers =
    Programming Language :: Python
    Programming Language :: Python :: 3
    Programming Language :: Python :: 3.6

[options]
package_dir =
    = src
packages = find:
python_requires = >=3.6
install_requires =
    numpy==1.19.5; python_version < "3.7"
    numpy>=1.21; python_version >= "3.7"
    psutil==5.9.8; python_version < "3.7"
    psutil>=5.9.8; python_version >= "3.7"
    backports.cached-property==1.0.2; python_version < "3.8"
    typing-extensions==4.1.1; python_version < "3.8"

[options.packages.find]
where = src

[options.package_data]
pycanape = py.typed

[options.extras_require]
dev =
    black==23.7.*; python_version >= "3.8"
    ruff==0.0.284; python_version >= "3.7"
    mypy==1.3.*; python_version >= "3.7"
    pre-commit
doc =
    furo
    sphinx==7.1.*
```

- [ ] **Step 2: Reduce `pyproject.toml` to compatible build and tool configuration**

Use this build backend:

```toml
[build-system]
build-backend = "setuptools.build_meta"
requires = ["setuptools==59.6.0", "wheel==0.37.1"]
```

Retain the existing Black, mypy, and Ruff configuration, but remove the PEP 621 `[project]` and `[tool.setuptools.dynamic]` sections that require a newer setuptools release.

- [ ] **Step 3: Run metadata tests and verify the packaging assertions pass**

Run: `python -m unittest tests.test_python36_compatibility.Python36PackagingTests.test_package_declares_python36_support tests.test_python36_compatibility.Python36PackagingTests.test_python36_dependencies_are_pinned -v`

Expected: 2 tests pass.

- [ ] **Step 4: Build wheel and source distribution**

Run: `python -m build`

Expected: exit code 0 with one `.whl` and one `.tar.gz` under `dist/`.

- [ ] **Step 5: Commit packaging changes**

Run:

```text
git add setup.cfg pyproject.toml
git commit -m "build: support Python 3.6 dependencies"
```

### Task 3: Verify runtime source and imports on Python 3.6

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_python36_compatibility.py`
- Verify unchanged: `src/pycanape/`

- [ ] **Step 1: Add a package API smoke test**

Add this test to `tests/test_python36_compatibility.py`:

```python
    def test_package_import_exposes_version_and_canape(self):
        import pycanape

        self.assertEqual(pycanape.__version__, "0.6.2")
        self.assertTrue(hasattr(pycanape, "CANape"))
```

- [ ] **Step 2: Run the smoke test and verify RED before installation**

Run in a clean environment without editable installation: `python -m unittest tests.test_python36_compatibility.Python36PackagingTests.test_package_import_exposes_version_and_canape -v`

Expected: `ModuleNotFoundError: No module named 'pycanape'`.

- [ ] **Step 3: Add Python 3.6 and Python 3.10 CI jobs**

Replace the existing `mypy` job with this compatibility job:

```yaml
  compatibility:
    runs-on: windows-latest
    strategy:
      matrix:
        python-version: ["3.6", "3.10"]
      fail-fast: false
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install package
        run: python -m pip install .
      - name: Compile runtime sources
        run: python -m compileall -q src
      - name: Run compatibility tests
        run: python -m unittest discover -s tests -v
```

Retain separate build, lint, format, and documentation jobs. Remove the automatic `upload_pypi` job so this compatibility fork cannot publish over the upstream PyPI package.

- [ ] **Step 4: Install the package and run the smoke test GREEN**

Run: `python -m pip install . --no-deps --no-build-isolation`

Then run: `python -m unittest tests.test_python36_compatibility.Python36PackagingTests.test_package_import_exposes_version_and_canape -v`

Expected: the test passes; warnings about an unavailable CANape DLL are acceptable on a development machine without CANape.

- [ ] **Step 5: Compile all runtime modules**

Run: `python -m compileall -q src`

Expected: exit code 0.

- [ ] **Step 6: Run the complete compatibility test suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 7: Commit runtime and CI compatibility**

Run:

```text
git add .github/workflows/ci.yml tests/test_python36_compatibility.py
git commit -m "ci: verify Python 3.6 installation"
```

### Task 4: Document and verify the compatibility branch

**Files:**
- Modify: `README.md`
- Test: package artifacts and Git status

- [ ] **Step 1: Document the compatibility scope**

Add this section after the README introduction:

```markdown
## Compatibility branch

This repository is based on pyCANape v0.6.2 and maintains installation and
import compatibility with CPython 3.6. Dependencies used by Python 3.6 are
pinned to compatible releases.

CANape 16 DLL symbols and structure layouts have not yet been validated in
this phase. Do not treat Python 3.6 package compatibility as confirmation of
CANape 16 runtime compatibility.
```

- [ ] **Step 2: Run fresh verification**

Run:

```text
python -m unittest discover -s tests -v
python -m compileall -q src
python -m build
python -m twine check dist/*
git diff --check
```

Expected: every command exits 0, tests report no failures, and both artifacts pass Twine validation.

- [ ] **Step 3: Commit documentation**

Run:

```text
git add README.md
git commit -m "docs: describe Python 3.6 compatibility"
```

- [ ] **Step 4: Inspect final scope before publication**

Run: `git status --short --branch` and `git log --oneline v0.6.2..HEAD`

Expected: clean branch containing only the design, plan, tests, packaging, CI, runtime compatibility if needed, and README commits.
