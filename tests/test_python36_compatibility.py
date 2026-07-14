import configparser
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Python36PackagingTests(unittest.TestCase):
    def setUp(self):
        self.config = configparser.ConfigParser()
        self.config.read(str(ROOT / "setup.cfg"), encoding="utf-8")

    def test_package_declares_python36_support(self):
        self.assertEqual(self.config["options"]["python_requires"], ">=3.6")

    def test_python36_dependencies_are_pinned(self):
        requirements = self.config["options"]["install_requires"]
        self.assertIn('numpy==1.19.5; python_version < "3.7"', requirements)
        self.assertIn('psutil==5.9.8; python_version < "3.7"', requirements)
        self.assertIn(
            'backports.cached-property==1.0.2; python_version < "3.8"',
            requirements,
        )
        self.assertIn(
            'typing-extensions==4.1.1; python_version < "3.8"', requirements
        )

    def test_ci_includes_python36(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
        self.assertIn('python-version: ["3.6", "3.10"]', workflow)

    def test_ci_uses_supported_artifact_action(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertNotIn("actions/upload-artifact@v3", workflow)

    def test_ci_does_not_require_editable_build_support(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
        self.assertNotIn("pip install -e", workflow)

    def test_legacy_setup_entrypoint_supports_editable_installs(self):
        setup_py = (ROOT / "setup.py").read_text("utf-8")
        self.assertEqual(setup_py, "from setuptools import setup\n\nsetup()\n")

    def test_package_import_exposes_version_and_canape(self):
        import pycanape

        self.assertEqual(pycanape.__version__, "0.6.2")
        self.assertTrue(hasattr(pycanape, "CANape"))


if __name__ == "__main__":
    unittest.main()
