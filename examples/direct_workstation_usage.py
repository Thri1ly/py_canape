"""Run from the repository root with a Python 3.6 interpreter."""

import pathlib
import time

from canape_interface import CANapeInterface

DLL_DIRECTORY = r"C:\Program Files\Vector CANape 16\Exec64"
PROJECT_PATH = r"D:\CANapeProjects\Demo"
MODULE_NAME = "ECU"
CALIBRATION_NAME = "Gain"
MEASUREMENT_SIGNALS = ["EngineSpeed", "EngineTemperature"]
MDF_FILENAME = r"D:\CANapeResults\direct_test.mf4"


def main():
    pathlib.Path(MDF_FILENAME).parent.mkdir(parents=True, exist_ok=True)

    with CANapeInterface(
        dll_directory=DLL_DIRECTORY,
        project_path=PROJECT_PATH,
        module_name=MODULE_NAME,
        clear_device_list=False,
        kill_open_instances=False,
    ) as canape:
        old_value = canape.read_calibration(CALIBRATION_NAME)
        print("Calibration before test:", old_value)

        requested_value = old_value + 1.0
        actual_value = canape.write_calibration(
            CALIBRATION_NAME,
            requested_value,
        )
        print("Calibration after write:", actual_value)

        canape.start_measurement(
            signal_names=MEASUREMENT_SIGNALS,
            mdf_filename=MDF_FILENAME,
            polling_rate=1,
        )
        try:
            time.sleep(5)
            for name, sample in canape.read_current_values().items():
                print(name, sample.timestamp, sample.value)
        finally:
            canape.stop_measurement(save_to_mdf=True)

        # Original objects remain available for low-level workstation debugging.
        print("CANape version:", canape.raw_canape.get_application_version())
        print("Module:", canape.module.get_module_name())


if __name__ == "__main__":
    main()
