# COMSOL → Origin 快速处理

把 COMSOL 已求解模型中的结果导入 Origin，再按设置画图、导出图片。

这个项目基于 [COMSOL-to-CSV-and-Origin-parser](https://github.com/GhVost/COMSOL-to-CSV-and-Origin-parser)。模型读取和数据导入沿用原项目，新增了 Origin 绘图、图片导出和参数设置窗口。

## 下载与使用

Windows 用户可以直接到 [Releases](https://github.com/ikunabc/comsol-origin-quick-processing/releases/latest) 下载 EXE，双击打开，不需要安装 Python 或 Git。ZIP 包中另附使用说明和依赖许可证。

电脑上仍需安装并授权 COMSOL 和 Origin 2024/2024b/2025/2025b。模型要提前求解；用高版本 COMSOL 保存的模型，需要相应版本才能打开。

1. 打开程序，点击 **Open** 选择 MPH 文件。
2. 在结果列表中勾选要提取的内容。
3. 点击 **Origin 绘图参数…**，填写要绘制的结果 Tag、X/Y 列，调整样式和导出目录。
4. 勾选 **Import extracted results into OriginLab**，点击 **Extract**。

提取的数据会导入 Origin，随后按设置绘图，导出 PNG、TIFF 或 PDF，并保存 OPJU 工程。图片保存在设置中的导出目录，工程保存在本次模型提取的输出目录。

EXE 的配置和日志位于 `%LOCALAPPDATA%\COMSOLOrigin`。详细路径和构建方法见 [Windows 使用说明](docs/WINDOWS_EXE.md)。

## 绘图设置

在参数窗口中可以调整：

- X/Y 数据列、折线/散点/柱形图、标题和 Origin 模板。
- 曲线颜色、线型、线宽、符号大小和图例文字。
- 坐标范围、刻度间隔、线性或对数坐标、坐标标题和单位。
- 字体、字号、图例位置和图层边距。
- 图片尺寸、DPI、透明背景、保存目录和文件名。
- 无效值清理、排序、平滑和插值。

保存后，下次提取会读取新设置，无需重启。上一份配置会备份为 `config.toml.ui-backup`。参数说明见 [绘图参数](docs/SETTINGS_UI.md)。

修改单位文字不会换算数据。例如，将 m/s 改为 μm/s，还需要把数据乘以 10⁶。目前多条曲线来自同一数据集的多列；暂不支持合并多个模型或多张表，也不支持多面板排版。

## 从源码运行

需要 Git、64 位 Python 3.11 或 3.12，以及 COMSOL 和 Origin。

```powershell
git clone --recurse-submodules https://github.com/ikunabc/comsol-origin-quick-processing.git
cd comsol-origin-quick-processing
```

首次运行双击 `Setup-GUI.cmd` 安装依赖，之后双击 `Start-GUI.cmd` 启动。也可以用 `Origin-Settings.cmd` 单独打开参数窗口。

首次启动会从 `config.default.toml` 创建 `config.toml`。本机配置、模型、输出文件和日志已加入 Git 忽略规则。

如果下载源码时漏掉了子模块，可以在项目目录执行：

```powershell
git submodule update --init --recursive
python -m pip install -r requirements-gui.txt
```

### 命令行

```powershell
python main.py
python main.py --config config.example-csv.toml
python main.py --check
python main.py --dry-run
python main.py --list-results
```

- `--check`：检查依赖、COMSOL 安装和 Origin COM 注册，不启动软件引擎。
- `--dry-run`：显示本次运行计划。
- `--list-results`：加载模型并列出可用结果，不求解模型。

CSV 模式不启动 COMSOL。项目附带的 `example.csv` 是合成数据，可用来试跑；不提供科研模型。

## 使用时要注意

- 程序读取已有结果，不负责求解，也不保存源 MPH 文件。
- Savitzky–Golay 平滑要求 X 近似等距。插值要求 X 唯一且递增，三次插值至少需要 4 个点。
- 参数扫描混在同一列时，应先拆分条件。重复的 X 不能直接当作一条曲线插值。
- 插值后只保留选中的 X/Y 列，其他列不会自动补值。
- 图片的物理尺寸由像素尺寸和 DPI 决定。PDF 为矢量页面；透明背景只支持 PNG、TIFF。
- 程序不会处理 COMSOL 或 Origin 的授权问题，软件生成的试用水印也会保留。

## 常见问题

**找不到 COMSOL，或提示许可证错误**

先确认 COMSOL 能单独打开模型。源码运行可用 `--check` 检查安装版本。高版本 MPH 无法用低版本 COMSOL 打开。

**提示找不到结果或数据列**

检查结果 Tag 是否与界面勾选的内容一致。源码运行可用 `--list-results` 查看 Tag。X/Y 列使用去掉单位后的表头名称；重名列需要在 `column_map` 中分别命名。

**Origin 无法连接**

先手动启动 Origin，完成首次运行和许可提示。源码运行还需确认 Python 为 64 位，并已安装 `originpro`、`OriginExt`。

**图片或工程保存失败**

检查输出目录是否可写、文件是否被占用，以及 Origin 是否有未关闭的对话框。路径过长时，可以先改用较短的本地目录。

**图页在 Origin 窗口里显得很小**

先检查显示缩放比例，将图页设为适应窗口。窗口周围的灰色区域不会导出；白色图页内的留白可通过图层边距调整。

**CSV 读不出来**

尝试指定 `standard`、`backend` 或 `native` 格式，并检查编码。程序不会自动识别使用逗号作小数点的文件。

报错详情见 `logs/gui.log` 和 `logs/pipeline.log`；EXE 的日志在 `%LOCALAPPDATA%\COMSOLOrigin\logs`。

## 开发与测试

上游项目以 Git 子模块放在 `lib/comsol_csv_tool/`，当前固定版本为 `4c63ac17fbb6272603a893e0233c6d27aa485180`，未修改上游源码。新增功能主要在 `src/adapters/`，参数窗口在 `src/settings_ui.py`。

Origin 操作通过 `originpro` / `OriginExt` 完成。接口记录见 [API_AUDIT.md](docs/API_AUDIT.md)。更新上游后，需要重新检查接口和运行结果。

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/verify_settings_ui.py
```

实际连接 Origin 的检查另行运行：

```powershell
python scripts/verify_origin.py
python scripts/verify_images.py
```

本机已做过 COMSOL 6.3/6.4 数据提取，以及 Origin 2025b 绘图、图片导出和工程重开的检查。不同软件版本、许可证和目录权限仍可能影响结果；全新无 Python 环境和 Windows 10 尚未单独实测。
