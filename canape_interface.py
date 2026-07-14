"""Direct source-tree interface for Python 3.6 CANape workstations."""

import importlib
import os
import pathlib
import platform
import sys
from collections import OrderedDict


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
        self._acquisition_started = False
        self._recorder_started = False

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
        cleanup_error = None
        try:
            try:
                self.stop_measurement(save_to_mdf=True)
            except Exception as exc:
                cleanup_error = exc
            canape.exit(close_canape=close_canape)
        finally:
            self._canape = None
            self._module = None
        if cleanup_error is not None:
            raise cleanup_error

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

    @property
    def measurement_active(self):
        """Return whether acquisition and recording are currently active."""
        return self._measurement_active

    def start_measurement(
        self,
        signal_names,
        mdf_filename,
        task_name=None,
        polling_rate=1,
    ):
        """Configure signals and start CANape acquisition and MDF recording."""
        self._require_open()
        if self._measurement_active:
            raise RuntimeError("A CANape measurement is already active")

        signals = list(signal_names)
        if not signals:
            raise ValueError("signal_names must contain at least one signal")
        if polling_rate < 1:
            raise ValueError("polling_rate must be at least 1")

        tasks = self._module.get_ecu_tasks()
        if not tasks:
            raise RuntimeError("The selected CANape module has no ECU tasks")
        if task_name is None:
            task = next(iter(tasks.values()))
        else:
            try:
                task = tasks[task_name]
            except KeyError:
                raise KeyError(
                    "ECU task '{}' was not found; available tasks: {}".format(
                        task_name,
                        ", ".join(tasks.keys()),
                    )
                ) from None

        self._module.reset_data_acquisition_channels_by_module()
        for signal_name in signals:
            task.daq_setup_channel(
                measurement_object_name=signal_name,
                polling_rate=polling_rate,
                save_to_file=True,
            )

        recorder = self._canape.get_selected_recorder()
        recorder.set_mdf_filename(str(mdf_filename))
        recorder.enable()

        self._task = task
        self._recorder = recorder
        self._signal_names = signals
        try:
            self._canape.start_data_acquisition()
            self._acquisition_started = True
            recorder.start()
            self._recorder_started = True
        except Exception:
            try:
                self.stop_measurement(save_to_mdf=False)
            except Exception:
                pass
            raise

        self._measurement_active = True
        return self

    def read_current_values(self):
        """Read current samples and map them to configured signal names."""
        self._require_open()
        if not self._measurement_active or self._task is None:
            raise RuntimeError("No CANape measurement is active")
        samples = self._task.daq_get_current_values(len(self._signal_names))
        return OrderedDict(zip(self._signal_names, samples))

    def stop_measurement(self, save_to_mdf=True):
        """Stop recording and acquisition, then clear measurement state."""
        if not self._recorder_started and not self._acquisition_started:
            self._measurement_active = False
            return

        cleanup_error = None
        try:
            if self._recorder_started and self._recorder is not None:
                try:
                    self._recorder.stop(save_to_mdf=save_to_mdf)
                except Exception as exc:
                    cleanup_error = exc
            if self._acquisition_started and self._canape is not None:
                try:
                    self._canape.stop_data_acquisition()
                except Exception as exc:
                    if cleanup_error is None:
                        cleanup_error = exc
        finally:
            self._measurement_active = False
            self._acquisition_started = False
            self._recorder_started = False
            self._recorder = None
            self._task = None
            self._signal_names = []

        if cleanup_error is not None:
            raise cleanup_error

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(close_canape=True)
        return False
