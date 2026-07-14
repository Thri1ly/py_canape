# Direct Workstation Interface Design

## Goal

Allow a Python 3.6 workstation to clone or unpack this repository and use it
directly, without installing the repository as a Python package. Provide both a
small automation-oriented facade and access to the original pyCANape objects
for low-level debugging.

## Scope

The change adds a repository-root entry point, an example, tests, and a Chinese
manual. It does not vendor third-party dependencies and does not claim that all
CANape 16 DLL symbols or structure layouts are compatible. NumPy, psutil,
backports.cached-property, and typing-extensions must still be available to the
Python 3.6 interpreter.

## Public Interface

The repository root will contain `canape_interface.py`. A workstation script
can import it directly:

```python
from canape_interface import CANapeInterface
```

`CANapeInterface` accepts the CANape API DLL directory, project directory,
module name, and the relevant CANape initialization options. It exposes:

- `open()` and `close()` for explicit lifecycle control;
- context-manager support for deterministic cleanup;
- `get_module()` for selecting an existing CANape module;
- `read_calibration()` and `write_calibration()` for scalar calibration;
- `start_measurement()`, `read_current_values()`, and `stop_measurement()` for
  configuring signals, reading live samples, and saving an MDF file.

For low-level debugging, the facade exposes read-only properties:

- `pycanape`: the original imported module;
- `raw_canape`: the original `pycanape.CANape` instance;
- `module`: the original `pycanape.Module` instance.

## Source and DLL Loading

Before importing pyCANape, the root entry point resolves `<repository>/src` and
adds it to `sys.path`. It validates the requested DLL directory and prepends it
to the current process `PATH`. This is intentionally process-local and does not
modify the workstation's permanent environment variables.

The pyCANape import is lazy: importing `canape_interface` alone must not load a
CANape DLL. The DLL is loaded when `open()` first imports pyCANape. This makes
the module testable on development computers without CANape installed and lets
callers configure the DLL directory first.

The interface will report clear errors for a missing DLL directory, a missing
CANape API library, and a CANape 16 DLL that lacks a symbol required by the
current wrapper. Bitness and ABI validation remain the caller's responsibility.

## Lifecycle and State

`open()` is idempotent and returns the interface instance. It creates one
CANape session and selects the configured module. `close()` stops an active
recorder and acquisition before closing CANape. It is also idempotent so it can
safely be called from `finally` blocks.

Operations that require an open session raise `RuntimeError` with an actionable
message. Starting a second acquisition while one is active is rejected.
Stopping an inactive acquisition is harmless.

## Calibration Flow

`read_calibration(name)` returns the scalar object's physical value.
`write_calibration(name, value, check_limits=True)` checks the A2L minimum and
maximum by default, writes the physical value, and returns the value read back
from CANape. Non-scalar objects remain available through `module` and are not
hidden or reimplemented by the facade.

## Measurement Flow

`start_measurement(signal_names, mdf_filename, task_name=None,
polling_rate=1)` clears API-added channels for the selected module, chooses the
named ECU task or the first available task, adds each signal in the supplied
order, configures the selected recorder, and starts acquisition and recording.

`read_current_values()` requests the current values using the same channel
count and returns an ordered dictionary mapping signal names to sample objects.
`stop_measurement(save_to_mdf=True)` stops the recorder, then the acquisition,
and resets internal state even if cleanup raises an exception.

## Files

- Create `canape_interface.py`: direct source bootstrap and facade.
- Create `examples/direct_workstation_usage.py`: calibration and MDF example.
- Create `docs/direct_workstation_usage_zh.md`: Python 3.6 workstation manual.
- Create `tests/test_direct_interface.py`: loading, lifecycle, calibration,
  acquisition, cleanup, and raw-access tests using injected fake API objects.
- Modify `README.md`: link to the new direct-use manual.

## Testing

Tests will run without CANape by injecting a fake pyCANape module into the
facade. They will verify Python 3.6-compatible syntax and behavior, including
idempotent cleanup and partial-failure cleanup. Existing packaging and CI tests
must continue to pass. The final verification will include CPython 3.6.8
`compileall`, unit tests, Ruff, Black, artifact checks, and GitHub Actions.

## Compatibility Boundary

This feature removes the need to install this repository but cannot remove the
runtime dependency on Vector CANape, its license, its API DLL, or the Python
dependencies used by the existing wrapper. A missing CANape 16 export is an ABI
compatibility finding to be addressed separately rather than silently ignored.
