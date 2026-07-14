import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FakeModule:
    def __init__(self):
        self.calibrations = {}
        self.tasks = {}
        self.reset_calls = 0

    def get_calibration_object(self, name):
        return self.calibrations[name]

    def get_ecu_tasks(self):
        return self.tasks

    def reset_data_acquisition_channels_by_module(self):
        self.reset_calls += 1


class FakeCalibration:
    def __init__(self, value=1.0, minimum=0.0, maximum=10.0):
        self.value = value
        self.min = minimum
        self.max = maximum


class FakeTask:
    def __init__(self, values=None):
        self.channels = []
        self.values = list(values or [])

    def daq_setup_channel(
        self, measurement_object_name, polling_rate, save_to_file
    ):
        self.channels.append(
            (measurement_object_name, polling_rate, save_to_file)
        )

    def daq_get_current_values(self, channel_count):
        return self.values[:channel_count]


class FakeRecorder:
    def __init__(self):
        self.filename = None
        self.events = []
        self.fail_start = False

    def set_mdf_filename(self, filename):
        self.filename = filename

    def enable(self):
        self.events.append("enable")

    def start(self):
        if self.fail_start:
            raise RuntimeError("recorder start failed")
        self.events.append("start")

    def stop(self, save_to_mdf=True):
        self.events.append(("stop", save_to_mdf))


class FakeCANape:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.selected_module = FakeModule()
        self.selected_recorder = FakeRecorder()
        self.exit_calls = []
        self.acquisition_events = []

    def get_module_by_name(self, name):
        self.module_name = name
        return self.selected_module

    def exit(self, close_canape=True):
        self.exit_calls.append(close_canape)

    def get_selected_recorder(self):
        return self.selected_recorder

    def start_data_acquisition(self):
        self.acquisition_events.append("start")

    def stop_data_acquisition(self):
        self.acquisition_events.append("stop")


class FakePyCANape:
    def __init__(self):
        self.instances = []

    def CANape(self, **kwargs):
        instance = FakeCANape(**kwargs)
        self.instances.append(instance)
        return instance


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


class CalibrationTests(unittest.TestCase):
    def make_interface(self):
        from canape_interface import CANapeInterface

        return CANapeInterface(
            dll_directory="ignored-for-injected-api",
            project_path=r"C:\CANapeProjects\Demo",
            module_name="ECU",
            _pycanape_module=FakePyCANape(),
        )

    def test_read_and_write_calibration(self):
        interface = self.make_interface().open()
        calibration = FakeCalibration()
        interface.module.calibrations["Gain"] = calibration

        self.assertEqual(interface.read_calibration("Gain"), 1.0)
        self.assertEqual(interface.write_calibration("Gain", 2.5), 2.5)
        self.assertEqual(calibration.value, 2.5)

    def test_write_rejects_value_outside_a2l_limits(self):
        interface = self.make_interface().open()
        interface.module.calibrations["Gain"] = FakeCalibration()

        with self.assertRaisesRegex(ValueError, "outside"):
            interface.write_calibration("Gain", 11.0)


class MeasurementTests(unittest.TestCase):
    def make_interface(self):
        from canape_interface import CANapeInterface

        interface = CANapeInterface(
            dll_directory="ignored-for-injected-api",
            project_path=r"C:\CANapeProjects\Demo",
            module_name="ECU",
            _pycanape_module=FakePyCANape(),
        ).open()
        interface.module.tasks = {
            "Slow": FakeTask([100, 20]),
            "Fast": FakeTask([101, 21]),
        }
        return interface

    def test_measurement_maps_values_in_signal_order(self):
        interface = self.make_interface()

        interface.start_measurement(
            ["Speed", "Temperature"],
            r"C:\Results\test.mf4",
            polling_rate=2,
        )
        values = interface.read_current_values()

        self.assertEqual(
            list(values.items()), [("Speed", 100), ("Temperature", 20)]
        )
        self.assertEqual(
            interface.module.tasks["Slow"].channels,
            [("Speed", 2, True), ("Temperature", 2, True)],
        )
        self.assertEqual(interface.module.reset_calls, 1)
        self.assertEqual(
            interface.raw_canape.selected_recorder.filename,
            r"C:\Results\test.mf4",
        )
        self.assertEqual(
            interface.raw_canape.selected_recorder.events,
            ["enable", "start"],
        )
        self.assertEqual(interface.raw_canape.acquisition_events, ["start"])

        interface.stop_measurement()

        self.assertFalse(interface.measurement_active)
        self.assertEqual(
            interface.raw_canape.selected_recorder.events[-1],
            ("stop", True),
        )
        self.assertEqual(
            interface.raw_canape.acquisition_events, ["start", "stop"]
        )

    def test_named_task_is_selected(self):
        interface = self.make_interface()

        interface.start_measurement(
            ["Speed"], r"C:\Results\fast.mf4", task_name="Fast"
        )

        self.assertEqual(
            interface.module.tasks["Fast"].channels,
            [("Speed", 1, True)],
        )

    def test_second_measurement_start_is_rejected(self):
        interface = self.make_interface()
        interface.start_measurement(["Speed"], r"C:\Results\one.mf4")

        with self.assertRaisesRegex(RuntimeError, "already active"):
            interface.start_measurement(["Speed"], r"C:\Results\two.mf4")

    def test_measurement_requires_at_least_one_signal(self):
        interface = self.make_interface()

        with self.assertRaisesRegex(ValueError, "at least one signal"):
            interface.start_measurement([], r"C:\Results\test.mf4")

    def test_polling_rate_must_be_positive(self):
        interface = self.make_interface()

        with self.assertRaisesRegex(ValueError, "at least 1"):
            interface.start_measurement(
                ["Speed"], r"C:\Results\test.mf4", polling_rate=0
            )

    def test_recorder_start_failure_stops_acquisition(self):
        interface = self.make_interface()
        interface.raw_canape.selected_recorder.fail_start = True

        with self.assertRaisesRegex(RuntimeError, "recorder start failed"):
            interface.start_measurement(["Speed"], r"C:\Results\test.mf4")

        self.assertFalse(interface.measurement_active)
        self.assertEqual(
            interface.raw_canape.acquisition_events, ["start", "stop"]
        )

    def test_close_stops_active_measurement_before_exit(self):
        interface = self.make_interface()
        raw_canape = interface.raw_canape
        recorder = raw_canape.selected_recorder
        interface.start_measurement(["Speed"], r"C:\Results\test.mf4")

        interface.close()

        self.assertEqual(recorder.events[-1], ("stop", True))
        self.assertEqual(raw_canape.acquisition_events, ["start", "stop"])
        self.assertEqual(raw_canape.exit_calls, [True])


if __name__ == "__main__":
    unittest.main()
