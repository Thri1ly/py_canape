import importlib.util
import pathlib
import sys
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


if __name__ == "__main__":
    unittest.main()
