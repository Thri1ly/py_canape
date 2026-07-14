# Python 3.6 工作站直接使用手册

本手册用于在安装了 Python 3.6 和 CANape 16 的 Windows 工作站上直接
调试本仓库。仓库本身不需要执行 `pip install .`，修改源文件后重新运行
测试脚本即可生效。

## 1. 使用边界

直接接口解决的是“无需安装本工程”的问题。以下运行条件仍然需要满足：

- 已安装 CANape 16，并且许可证有效；
- Python 与 CANape API DLL 位数一致；
- Python 3.6 能够导入本工程依赖；
- CANape 工程、CNA、A2L 和设备通信配置可用；
- CANape 16 DLL 必须包含当前封装所使用的 API 函数。

本阶段已经验证 Python 3.6 语法和依赖兼容性，但尚未证明 CANape 16 的
全部 DLL 符号和结构体布局都与 CANape 17 相同。

## 2. 准备目录

从 GitHub 克隆或下载并解压仓库：

```powershell
git clone https://github.com/Thri1ly/py_canape.git D:\Tools\py_canape
cd D:\Tools\py_canape
```

直接使用时的主要文件为：

```text
py_canape/
├── canape_interface.py                  # 工作站统一接口
├── src/pycanape/                        # 原始 pyCANape 实现
├── examples/direct_workstation_usage.py # 完整示例
└── docs/direct_workstation_usage_zh.md  # 本手册
```

不要单独复制 `canape_interface.py`。它会从同一仓库的 `src` 目录加载原始
pyCANape 代码，因此这两部分必须保持在原目录结构中。

## 3. 准备 Python 3.6 依赖

工程本身不需要安装，但原始 pyCANape 使用了以下第三方库：

```text
numpy==1.19.5
psutil==5.9.8
backports.cached-property==1.0.2
typing-extensions==4.1.1
```

如果工作站允许安装第三方依赖，可以执行：

```powershell
python -m pip install "numpy==1.19.5" "psutil==5.9.8" `
    "backports.cached-property==1.0.2" "typing-extensions==4.1.1"
```

这条命令只安装依赖，不安装本工程。

离线工作站可以在联网电脑上下载 Python 3.6 对应的 wheel：

```powershell
python -m pip download --only-binary=:all: --python-version 36 `
    --platform win_amd64 --implementation cp --abi cp36m `
    "numpy==1.19.5" "psutil==5.9.8" `
    "backports.cached-property==1.0.2" "typing-extensions==4.1.1" `
    -d wheels
```

把 `wheels` 目录复制到工作站后执行：

```powershell
python -m pip install --no-index --find-links .\wheels `
    numpy psutil backports.cached-property typing-extensions
```

## 4. 确认 Python 和 DLL 位数

```powershell
python --version
python -c "import platform; print(platform.architecture())"
```

- 64 位 Python 加载 `CANapAPI64.dll`；
- 32 位 Python 加载 `CANapAPI.dll`。

搜索 64 位 DLL：

```powershell
Get-ChildItem "C:\Program Files\Vector*" -Recurse -Filter CANapAPI64.dll
```

接口接收的是 DLL 所在目录，而不是 DLL 文件完整路径。例如：

```text
C:\Program Files\Vector CANape 16\Exec64
```

接口只修改当前 Python 进程的 `PATH`，不会永久修改工作站环境变量。

## 5. 从仓库内直接运行

先打开 `examples/direct_workstation_usage.py`，修改以下配置：

```python
DLL_DIRECTORY = r"C:\Program Files\Vector CANape 16\Exec64"
PROJECT_PATH = r"D:\CANapeProjects\Demo"
MODULE_NAME = "ECU"
CALIBRATION_NAME = "Gain"
MEASUREMENT_SIGNALS = ["EngineSpeed", "EngineTemperature"]
MDF_FILENAME = r"D:\CANapeResults\direct_test.mf4"
```

当前底层初始化使用 ASCII 编码传递工程路径，因此建议 CANape 工程、A2L
和 MDF 路径只使用英文、数字和下划线。

在仓库根目录运行：

```powershell
cd D:\Tools\py_canape
python examples\direct_workstation_usage.py
```

不需要执行 `pip install .`。`canape_interface.py` 会自动把仓库的 `src`
目录加入 Python 搜索路径。

## 6. 从自己的自动化工程调用

假设自动化工程位于 `D:\AutomationTests`，仓库位于
`D:\Tools\py_canape`。在测试脚本最前面加入仓库根目录：

```python
import sys

PYCANAPE_REPOSITORY = r"D:\Tools\py_canape"
if PYCANAPE_REPOSITORY not in sys.path:
    sys.path.insert(0, PYCANAPE_REPOSITORY)

from canape_interface import CANapeInterface
```

之后即可创建接口：

```python
canape = CANapeInterface(
    dll_directory=r"C:\Program Files\Vector CANape 16\Exec64",
    project_path=r"D:\CANapeProjects\Demo",
    module_name="ECU",
)
```

## 7. 推荐的自动化测试结构

```python
import sys
import time

sys.path.insert(0, r"D:\Tools\py_canape")

from canape_interface import CANapeInterface


with CANapeInterface(
    dll_directory=r"C:\Program Files\Vector CANape 16\Exec64",
    project_path=r"D:\CANapeProjects\Demo",
    module_name="ECU",
    clear_device_list=False,
    kill_open_instances=False,
) as canape:
    old_value = canape.read_calibration("Gain")
    print("Old value:", old_value)

    new_value = canape.write_calibration("Gain", old_value + 1.0)
    print("Read-back value:", new_value)

    canape.start_measurement(
        signal_names=["EngineSpeed", "EngineTemperature"],
        mdf_filename=r"D:\CANapeResults\test_001.mf4",
        polling_rate=1,
    )
    try:
        time.sleep(5)
        samples = canape.read_current_values()
        for signal_name, sample in samples.items():
            print(signal_name, sample.timestamp, sample.value)
    finally:
        canape.stop_measurement(save_to_mdf=True)
```

`with` 代码块退出时会停止未结束的采集并关闭 CANape。即使测试抛出异常，
清理逻辑也会执行。

## 8. 高层接口参考

### 启动和关闭

```python
canape.open()
canape.close(close_canape=True)
```

重复调用 `open()` 不会创建第二个 CANape 会话。重复调用 `close()`不会报错。

### 读取标定量

```python
value = canape.read_calibration("Gain")
```

该接口适用于标量标定对象，返回物理值。

### 写入标定量

```python
actual_value = canape.write_calibration("Gain", 2.5)
```

默认按照 A2L 中的最小值和最大值检查范围，并返回写入后的回读值。如需由
底层 CANape 处理范围，可显式关闭检查：

```python
actual_value = canape.write_calibration(
    "Gain", 2.5, check_limits=False
)
```

### 启动采集

```python
canape.start_measurement(
    signal_names=["EngineSpeed", "EngineTemperature"],
    mdf_filename=r"D:\CANapeResults\test.mf4",
    task_name=None,
    polling_rate=1,
)
```

`task_name=None` 时选择模块返回的第一个 ECU Task。在正式测试中建议先打印
可用任务，再显式指定：

```python
print(list(canape.module.get_ecu_tasks().keys()))
```

### 读取当前采集值

```python
samples = canape.read_current_values()
sample = samples["EngineSpeed"]
print(sample.timestamp, sample.value)
```

返回值保持 `signal_names` 的顺序。

### 停止采集

```python
canape.stop_measurement(save_to_mdf=True)
```

停止顺序为 Recorder、Data Acquisition。即使其中一步失败，接口仍会尝试
完成另一项清理并重置内部状态。

## 9. 使用原始 pyCANape API 调试

高层接口不会限制底层 API。会话启动后可以直接访问：

```python
with CANapeInterface(...) as canape:
    # 原始 pycanape Python 模块
    original_package = canape.pycanape

    # 原始 pycanape.CANape 对象
    raw_canape = canape.raw_canape
    print(raw_canape.get_application_version())
    print(raw_canape.get_dll_version())

    # 原始 pycanape.Module 对象
    raw_module = canape.module
    print(raw_module.get_database_path())
    print(raw_module.get_ecu_tasks())

    # 非标量标定对象仍然通过原始对象处理
    curve = raw_module.get_calibration_object("TorqueCurve")
    print(curve.axis)
    print(curve.values)
```

修改 `src\pycanape` 下的底层代码后，需要结束当前 Python 进程并重新运行，
确保 DLL 映射和 Python 模块都被重新加载。

## 10. 常见问题

### `No module named 'canape_interface'`

运行目录不是仓库根目录，或者外部测试脚本没有把仓库根目录加入
`sys.path`。加入的是 `D:\Tools\py_canape`，不是它下面的 `src`。

### `No module named 'numpy'` 或其他第三方库

本工程没有安装是允许的，但依赖仍需存在。按照第3节安装或离线复制兼容
wheel。

### `CANape API DLL directory does not exist`

`dll_directory` 必须是实际存在的文件夹。不要把
`CANapAPI64.dll` 文件名放进参数。

### `CANape API not found`

确认 DLL 名称、目录和 Python 位数。64 位 Python 必须能够在指定目录中
找到 `CANapAPI64.dll` 及其依赖 DLL。

### `%1 is not a valid Win32 application`

Python 与 DLL 位数不匹配。重新确认 Python 是 32 位还是 64 位。

### `Could not map function 'Asap3...'`

CANape 16 DLL 中没有当前封装加载的函数，或导出名称与 CANape 17 不同。
错误中的函数名就是下一步需要针对 CANape 16 适配的 API。不要通过吞掉该
错误继续测试，否则后续 ctypes 调用可能产生不可预测结果。

### 找不到模块

确认 `module_name` 与 CANape 工程中的设备名完全一致，并使用：

```python
clear_device_list=False
```

这样会保留 CNA/CANape 工程中已经配置的设备。

### `UnicodeEncodeError`

当前底层代码使用 ASCII 编码传递工程目录。把工程、A2L、MDF 输出目录移到
只包含英文字符的路径。

## 11. 工作站调试建议

先按以下顺序缩小问题范围：

1. 只执行 `from canape_interface import CANapeInterface`；
2. 创建接口但不调用 `open()`；
3. 调用 `open()`，确认 DLL 映射和 CANape 启动；
4. 通过 `canape.module` 确认设备和 ECU Task；
5. 只读一个标定量；
6. 写入一个可恢复的测试标定量并回读；
7. 添加一个测量信号并采集；
8. 最后再加入多个信号和完整自动化流程。

这样可以区分源码导入、DLL ABI、工程配置、ECU 通信和自动化逻辑问题。
