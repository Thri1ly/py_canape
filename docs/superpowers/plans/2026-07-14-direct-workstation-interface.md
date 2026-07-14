# Direct Workstation Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Python 3.6-compatible repository-root interface that loads the existing `src` package directly and offers both automation helpers and original pyCANape objects without installing this repository.

**Architecture:** `canape_interface.py` bootstraps `<repo>/src`, configures the process-local DLL search path, and lazily imports pyCANape when `open()` is called. `CANapeInterface` owns one CANape session, one selected module, and optional acquisition state while exposing the underlying module and objects for debugging.

**Tech Stack:** CPython 3.6, standard-library `unittest`, pathlib, importlib, existing pyCANape ctypes wrapper, NumPy, psutil.

---

## File Structure

- Create `canape_interface.py`: source bootstrap, DLL configuration, lifecycle, calibration, acquisition, and raw-object access.
- Create `tests/test_direct_interface.py`: fake CANape API objects and behavior tests that do not require Vector software.
- Create `examples/direct_workstation_usage.py`: executable Python 3.6 calibration and MDF acquisition example.
- Create `docs/direct_workstation_usage_zh.md`: Chinese setup, direct import, API reference, debugging, and troubleshooting manual.
- Modify `README.md`: link to the direct-workstation manual.

### Task 1: Direct source bootstrap and lazy loading

**Files:**
- Create: `tests/test_direct_interface.py`
- Create: `canape_interface.py`

- [ ] **Step 1: Write the failing bootstrap tests**

```python
import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DirectBootstrapTests(unittest.TestCase):
    def test_module_import_adds_src_without_importing_pycanape(self):
        sys.modules.pop("canape_interface", None)
        sys.modules.pop("pycanape", None)
        spec = importlib.util.spec_from_file_location(
            "canape_interface", str(ROOT / "canape_interface.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn(str(ROOT / "src"), sys.path)
        self.assertNotIn("pycanape", sys.modules)

    def test_missing_dll_directory_is_rejected_when_opening(self):
        from canape_interface import CANapeInterface

        interface = CANapeInterface(
            dll_directory=str(ROOT / "missing-dll-directory"),
            project_path=r"C:\CANapeProjects\Demo",
            module_name="ECU",
        )
        with self.assertRaisesRegex(FileNotFoundError, "DLL directory"):
            interface.open()
```

- [ ] **Step 2: Run the bootstrap tests to verify RED**

Run:

```powershell
.venv\Scripts\python -m unittest tests.test_direct_interface.DirectBootstrapTests -v
```

Expected: ERROR because `canape_interface.py` does not exist.

- [ ] **Step 3: Implement bootstrap and constructor**

Create `canape_interface.py` with repository-root and `src` resolution, a
Python 3.6-compatible constructor, `_configure_dll_path()`, and `_load_pycanape()`.
The implementation must not import pyCANape at module import time. Use
`importlib.import_module("pycanape")` only from `_load_pycanape()`. Convert
`FileNotFoundError`, `ImportError`, and `OSError` into messages that include the
DLL directory, Python bitness, and original exception text.

```python
import importlib
import os
import pathlib
import platform
import sys


ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class CANapeInterface:
    def __init__(
        self,
        dll_directory,
        project_path,
        module_name,
        modal_mode=True,
        clear_device_list=False,
        kill_open_instances=False,
        _pycanape_module=None,
    ):
        self.dll_directory = pathlib.Path(dll_directory).resolve()
        self.project_path = str(project_path)
        self.module_name = module_name
        self.modal_mode = modal_mode
        self.clear_device_list = clear_device_list
        self.kill_open_instances = kill_open_instances
        self._pycanape = _pycanape_module
        self._canape = None
        self._module = None
        self._recorder = None
        self._task = None
        self._signal_names = []
        self._measurement_active = False

    def _configure_dll_path(self):
        if self._pycanape is not None:
            return
        if not self.dll_directory.is_dir():
            raise FileNotFoundError(
                "CANape API DLL directory does not exist: {}".format(
                    self.dll_directory
                )
            )
        current_path = os.environ.get("PATH", "")
        directory = str(self.dll_directory)
        entries = current_path.split(os.pathsep) if current_path else []
        if directory not in entries:
            os.environ["PATH"] = directory + os.pathsep + current_path

    def _load_pycanape(self):
        if self._pycanape is not None:
            return self._pycanape
        self._configure_dll_path()
        try:
            self._pycanape = importlib.import_module("pycanape")
        except (FileNotFoundError, ImportError, OSError) as exc:
            raise ImportError(
                "Unable to load CANape API from '{}', Python {}: {}".format(
                    self.dll_directory, platform.architecture()[0], exc
                )
            ) from exc
        return self._pycanape
```

- [ ] **Step 4: Run bootstrap tests to verify GREEN**

Run the Task 1 test command. Expected: two tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add canape_interface.py tests/test_direct_interface.py
git commit -m "feat: bootstrap pycanape directly from source"
```

### Task 2: Session lifecycle and raw API access

**Files:**
- Modify: `tests/test_direct_interface.py`
- Modify: `canape_interface.py`

- [ ] **Step 1: Add failing lifecycle tests**

Add fake `CANape`, module, and pyCANape objects that record calls. Test that
`open()` is idempotent, selects the named module, the three raw properties
return the injected objects, context manager cleanup calls `exit(True)`, and an
operation before `open()` raises `RuntimeError`.

```python
class FakeModule:
    pass


class FakeCANape:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.selected_module = FakeModule()
        self.exit_calls = []

    def get_module_by_name(self, name):
        self.module_name = name
        return self.selected_module

    def exit(self, close_canape=True):
        self.exit_calls.append(close_canape)


class FakePyCANape:
    def __init__(self):
        self.instances = []

    def CANape(self, **kwargs):
        instance = FakeCANape(**kwargs)
        self.instances.append(instance)
        return instance


class LifecycleTests(unittest.TestCase):
    def make_interface(self):
        from canape_interface import CANapeInterface

        return CANapeInterface(
            dll_directory="ignored-for-injected-api",
            project_path=r"C:\CANapeProjects\Demo",
            module_name="ECU",
            _pycanape_module=FakePyCANape(),
        )

    def test_open_is_idempotent_and_exposes_raw_objects(self):
        interface = self.make_interface()
        self.assertIs(interface.open(), interface)
        self.assertIs(interface.open(), interface)
        self.assertEqual(len(interface.pycanape.instances), 1)
        self.assertIs(interface.raw_canape, interface.pycanape.instances[0])
        self.assertIs(interface.module, interface.raw_canape.selected_module)

    def test_context_manager_closes_canape(self):
        interface = self.make_interface()
        with interface as opened:
            raw = opened.raw_canape
        self.assertEqual(raw.exit_calls, [True])

    def test_raw_canape_requires_open_session(self):
        with self.assertRaisesRegex(RuntimeError, "open"):
            self.make_interface().raw_canape
```

- [ ] **Step 2: Run lifecycle tests to verify RED**

Run:

```powershell
.venv\Scripts\python -m unittest tests.test_direct_interface.LifecycleTests -v
```

Expected: FAIL because lifecycle methods and properties are absent.

- [ ] **Step 3: Implement lifecycle and properties**

Implement `open`, `close`, `_require_open`, `__enter__`, `__exit__`, and
read-only `pycanape`, `raw_canape`, and `module` properties. `close()` must be
idempotent and always clear references after calling `exit(close_canape)`.

- [ ] **Step 4: Run lifecycle and bootstrap tests**

Run:

```powershell
.venv\Scripts\python -m unittest tests.test_direct_interface -v
```

Expected: all current tests pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add canape_interface.py tests/test_direct_interface.py
git commit -m "feat: manage direct CANape session lifecycle"
```

### Task 3: Scalar calibration helpers

**Files:**
- Modify: `tests/test_direct_interface.py`
- Modify: `canape_interface.py`

- [ ] **Step 1: Add failing calibration tests**

Extend `FakeModule` with calibration objects. Verify read, bounded write and
read-back, and rejection of an out-of-range value.

```python
class FakeCalibration:
    def __init__(self, value=1.0, minimum=0.0, maximum=10.0):
        self.value = value
        self.min = minimum
        self.max = maximum


def test_read_and_write_calibration(self):
    interface = self.make_interface().open()
    calibration = FakeCalibration()
    interface.module.calibrations = {"Gain": calibration}
    interface.module.get_calibration_object = (
        lambda name: interface.module.calibrations[name]
    )
    self.assertEqual(interface.read_calibration("Gain"), 1.0)
    self.assertEqual(interface.write_calibration("Gain", 2.5), 2.5)
    self.assertEqual(calibration.value, 2.5)


def test_write_rejects_value_outside_a2l_limits(self):
    interface = self.make_interface().open()
    calibration = FakeCalibration()
    interface.module.get_calibration_object = lambda name: calibration
    with self.assertRaisesRegex(ValueError, "outside"):
        interface.write_calibration("Gain", 11.0)
```

- [ ] **Step 2: Run calibration tests to verify RED**

Expected: FAIL because `read_calibration` and `write_calibration` are absent.

- [ ] **Step 3: Implement minimal calibration helpers**

`read_calibration(name)` returns `.value`.
`write_calibration(name, value, check_limits=True)` validates inclusive bounds,
writes `.value`, and returns the read-back value. Both call `_require_open()`.

- [ ] **Step 4: Run all direct-interface tests**

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add canape_interface.py tests/test_direct_interface.py
git commit -m "feat: add direct calibration helpers"
```

### Task 4: Measurement and cleanup helpers

**Files:**
- Modify: `tests/test_direct_interface.py`
- Modify: `canape_interface.py`

- [ ] **Step 1: Add failing acquisition tests**

Add fake task, recorder, and acquisition methods. Verify signal ordering,
selected task behavior, recorder filename, channel count, ordered result
mapping, double-start rejection, harmless double-stop, and cleanup on close.

```python
class FakeTask:
    def __init__(self):
        self.channels = []

    def daq_setup_channel(self, measurement_object_name, polling_rate, save_to_file):
        self.channels.append(
            (measurement_object_name, polling_rate, save_to_file)
        )

    def daq_get_current_values(self, channel_count):
        return list(range(channel_count))


class FakeRecorder:
    def __init__(self):
        self.filename = None
        self.events = []

    def set_mdf_filename(self, filename):
        self.filename = filename

    def enable(self):
        self.events.append("enable")

    def start(self):
        self.events.append("start")

    def stop(self, save_to_mdf=True):
        self.events.append(("stop", save_to_mdf))


def test_measurement_maps_values_in_signal_order(self):
    interface = self.make_measurement_interface().open()
    interface.start_measurement(
        ["Speed", "Temperature"], r"C:\Results\test.mf4"
    )
    values = interface.read_current_values()
    self.assertEqual(list(values.items()), [("Speed", 0), ("Temperature", 1)])
    interface.stop_measurement()
    self.assertFalse(interface.measurement_active)
```

- [ ] **Step 2: Run acquisition tests to verify RED**

Expected: FAIL because acquisition methods are absent.

- [ ] **Step 3: Implement acquisition state machine**

Use `collections.OrderedDict` for Python 3.6 ordering guarantees. Validate that
`signal_names` is non-empty and `polling_rate >= 1`. Choose `task_name` exactly
when supplied, otherwise choose the first task. Configure the module, selected
recorder, acquisition, and recorder in that order. If startup fails, unwind any
completed stages. `stop_measurement()` must attempt recorder and acquisition
cleanup, reset all state in `finally`, and re-raise the first cleanup error.

- [ ] **Step 4: Run all direct and existing tests**

Run:

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add canape_interface.py tests/test_direct_interface.py
git commit -m "feat: add direct measurement workflow"
```

### Task 5: Workstation example and Chinese manual

**Files:**
- Create: `examples/direct_workstation_usage.py`
- Create: `docs/direct_workstation_usage_zh.md`
- Modify: `README.md`

- [ ] **Step 1: Create the executable example**

The example must import only `CANapeInterface` from the repository root, define
plain configuration constants, use a `with` block, read and conditionally write
a scalar, start two signals, wait five seconds, print current values, and stop
with MDF saving. It must use English-only example paths because the current
wrapper encodes project paths as ASCII.

- [ ] **Step 2: Create the Chinese direct-use manual**

Document repository layout, Python 3.6 dependency preparation without
`pip install .`, DLL discovery and bitness, running from the repository root,
high-level API signatures, raw access, the complete example, offline dependency
installation, and the errors `CANape API not found`, invalid Win32 application,
missing DLL symbol, missing module, and ASCII path encoding.

Use these dependency versions for Python 3.6:

```text
numpy==1.19.5
psutil==5.9.8
backports.cached-property==1.0.2
typing-extensions==4.1.1
```

- [ ] **Step 3: Link the manual from README**

Add a `Direct workstation usage` section linking
`docs/direct_workstation_usage_zh.md` and showing:

```python
from canape_interface import CANapeInterface
```

- [ ] **Step 4: Verify example syntax with Python 3.6 compileall**

Run official CPython 3.6.8 embeddable against `canape_interface.py`, `examples`,
`src`, and `tests`. Expected: exit code 0.

- [ ] **Step 5: Commit Task 5**

```powershell
git add examples/direct_workstation_usage.py docs/direct_workstation_usage_zh.md README.md
git commit -m "docs: add direct workstation usage guide"
```

### Task 6: Full verification and publication

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run unit tests and compilation**

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python -m compileall -q canape_interface.py examples src tests
```

Expected: all tests and compilation pass.

- [ ] **Step 2: Run formatting and linting**

```powershell
uvx ruff==0.0.284 check --config pyproject.toml canape_interface.py examples src tests
uvx black==23.7.0 --config pyproject.toml --check canape_interface.py examples src tests
```

Expected: both commands exit 0.

- [ ] **Step 3: Build and inspect artifacts**

```powershell
uv build
uvx twine==6.2.0 check dist\*
```

Expected: wheel and sdist pass Twine checks. Confirm direct root files are for
source-tree use and do not alter the installed package API.

- [ ] **Step 4: Verify repository cleanliness**

```powershell
git diff --check
git status --short
```

Expected: no uncommitted changes.

- [ ] **Step 5: Push and verify GitHub Actions**

```powershell
git push target HEAD:main
git ls-remote target refs/heads/main
git rev-parse HEAD
```

Expected: local and remote SHA values match and all GitHub Actions jobs pass,
including compatibility on Python 3.6.
