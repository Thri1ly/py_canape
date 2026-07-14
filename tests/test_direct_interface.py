import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    unittest.main()
