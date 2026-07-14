"""Direct source-tree interface for Python 3.6 CANape workstations."""

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
    """Load pyCANape from this repository without installing the package."""

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
                    self.dll_directory,
                    platform.architecture()[0],
                    exc,
                )
            ) from exc
        return self._pycanape

    def open(self):
        """Open one CANape session and select the configured module."""
        if self._canape is not None:
            return self

        pycanape = self._load_pycanape()
        self._canape = pycanape.CANape(
            project_path=self.project_path,
            modal_mode=self.modal_mode,
            clear_device_list=self.clear_device_list,
            kill_open_instances=self.kill_open_instances,
        )
        self._module = self._canape.get_module_by_name(self.module_name)
        return self

    def _require_open(self):
        if self._canape is None or self._module is None:
            raise RuntimeError("CANape session is not open; call open() first")

    def close(self, close_canape=True):
        """Close the CANape session if it is open."""
        if self._canape is None:
            return

        canape = self._canape
        try:
            canape.exit(close_canape=close_canape)
        finally:
            self._canape = None
            self._module = None

    @property
    def pycanape(self):
        """Return the original imported pyCANape module."""
        self._require_open()
        return self._pycanape

    @property
    def raw_canape(self):
        """Return the original pycanape.CANape object."""
        self._require_open()
        return self._canape

    @property
    def module(self):
        """Return the original pycanape.Module object."""
        self._require_open()
        return self._module

    def read_calibration(self, name):
        """Read the physical value of a scalar calibration object."""
        self._require_open()
        calibration = self._module.get_calibration_object(name)
        return calibration.value

    def write_calibration(self, name, value, check_limits=True):
        """Write and read back a scalar calibration object's physical value."""
        self._require_open()
        calibration = self._module.get_calibration_object(name)
        if check_limits and not calibration.min <= value <= calibration.max:
            raise ValueError(
                "Calibration value {} is outside [{}, {}] for '{}'".format(
                    value,
                    calibration.min,
                    calibration.max,
                    name,
                )
            )
        calibration.value = value
        return calibration.value

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(close_canape=True)
        return False
