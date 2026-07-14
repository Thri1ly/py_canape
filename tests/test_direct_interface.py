import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FakeModule:
    def __init__(self):
        self.calibrations = {}

    def get_calibration_object(self, name):
        return self.calibrations[name]


class FakeCalibration:
    def __init__(self, value=1.0, minimum=0.0, maximum=10.0):
        self.value = value
        self.min = minimum
        self.max = maximum


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


if __name__ == "__main__":
    unittest.main()
