# Python 3.6 Compatibility Design

## Goal

Create a maintainable compatibility branch of pyCANape that installs and imports on CPython 3.6 while preserving the behavior and public API of upstream release `v0.6.2`.

This phase covers only the first three agreed steps:

1. Use upstream `v0.6.2` as the source baseline.
2. Remove Python 3.7+ language and standard-library requirements from runtime code.
3. Pin runtime and build dependencies to versions that support CPython 3.6.

CANape 16 DLL discovery, symbol filtering, structure verification, and hardware integration tests are intentionally deferred to the next phase.

## Selected Approach

Keep the upstream Git history and develop on an `agent/py36-compat` branch rooted at tag `v0.6.2`. Backport only compatibility changes required for CPython 3.6 instead of reviving the much older Python 3.6 snapshot or rewriting current `master`.

This approach keeps the API surface that the user originally evaluated, minimizes unrelated changes, and retains upstream attribution and MIT licensing. The older Python 3.6 snapshot would lose later fixes, while current `master` would require a substantially larger syntax and packaging backport.

## Runtime Compatibility

Runtime modules will be valid CPython 3.6 source. Compatibility work includes:

- replacing postponed annotations and newer annotation syntax with Python 3.6-compatible `typing` forms;
- using backports for `cached_property` and `importlib.metadata` where required;
- keeping typing-only imports from affecting runtime imports;
- avoiding APIs added after Python 3.6;
- preserving all public class, method, function, and enum names from `v0.6.2`.

The DLL bindings and CANape behavior will not be redesigned in this phase. The expected functional behavior remains identical to `v0.6.2` when used with the same CANape DLL.

## Packaging and Dependencies

The package metadata will explicitly declare Python 3.6 support. Runtime dependencies will use environment markers or upper bounds so a Python 3.6 installer selects compatible releases. In particular, NumPy will be constrained to the Python 3.6-compatible line instead of the upstream `numpy>=1.21` requirement.

The build configuration will avoid requiring a setuptools release that cannot run on Python 3.6. Package name, import name, license, source layout, and public metadata will remain unchanged unless a compatibility constraint requires a narrowly scoped adjustment.

## Verification

Because this workstation does not have CPython 3.6 or CANape installed, verification is split into two levels:

1. Local checks on the available Python versions:
   - compile every runtime source file;
   - import the package without a CANape DLL;
   - run compatibility-focused tests for metadata and source syntax;
   - build both wheel and source distribution and inspect their metadata.
2. CI checks on Windows with CPython 3.6:
   - install the package from the repository;
   - import `pycanape` without CANape installed;
   - run the compatibility test suite.

The CI job will not claim CANape 16 compatibility. DLL-level verification requires the CANape 16 header and DLL in the next phase.

## Error Handling

Missing CANape DLL behavior must remain the same as upstream `v0.6.2`: importing the package is allowed, while constructing functionality that requires the DLL reports the existing clear error. Dependency-resolution failures on Python 3.6 should be prevented through explicit version constraints rather than handled at runtime.

## Deliverable

The target repository will contain the upstream history through `v0.6.2`, the compatibility commits on `agent/py36-compat`, documentation of the selected baseline, and reproducible checks for Python 3.6 installation and import. No release publication to PyPI is part of this phase.
