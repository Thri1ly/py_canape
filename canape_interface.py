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
        """Load the original pyCANape module."""
        self._load_pycanape()
        return self
