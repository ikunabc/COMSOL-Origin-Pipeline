# COMSOL → Origin 快速处理

把已求解的 COMSOL 模型或 CSV 数据导入 Origin，完成数据处理、绘图、图片导出和 OPJU 工程保存。

项目基于 [COMSOL-to-CSV-and-Origin-parser](https://github.com/GhVost/COMSOL-to-CSV-and-Origin-parser)。上游模块负责 COMSOL 结果提取，本项目增加了数据处理、Origin 绘图、图片导出和参数界面。

## 快速开始

### Windows 发布版

从 [Releases](https://github.com/ikunabc/comsol-origin-quick-processing/releases/latest) 下载 EXE，双击启动。发布版不需要安装 Python 或 Git，但电脑仍需安装并授权 COMSOL 和 Origin 2024/2024b/2025/2025b。

详细说明见 [Windows 发布版](docs/WINDOWS_EXE.md)。

### 从源码运行

需要 Git、uv、64 位 Python 3.11 或 3.12，以及已安装并授权的 COMSOL 和 Origin。

```powershell
git clone --recurse-submodules https://github.com/ikunabc/comsol-origin-quick-processing.git
cd comsol-origin-quick-processing
.\Setup-GUI.cmd
.\Start-GUI.cmd
```

首次运行 `Setup-GUI.cmd` 会初始化 Git 子模块，并通过 `uv sync --locked` 创建 `.venv`、安装锁定的依赖。以后只需运行 `Start-GUI.cmd`。单独编辑 Origin 绘图参数可运行 `Origin-Settings.cmd`。

如果克隆时没有下载子模块，重新执行：

```powershell
git submodule update --init --recursive
```

## 基本流程

1. 选择输入方式：已求解的 MPH 模型或 CSV 文件。
2. 识别并选择要提取的结果。
3. 设置 X/Y 列、图形样式、数据处理和导出目录。
4. 直接运行，或把多组设置加入队列后批量生成。

CLI 和集成 GUI 按配置生成：

- 处理后的 CSV 和元数据：`data/processed/`
- 图片：默认位于 `output/figures/`
- Origin 工程：默认位于 `output/origin/`
- 日志：`logs/pipeline.log` 和 `logs/gui.log`

发布版的配置、默认输出和日志位于 `%LOCALAPPDATA%\COMSOLOrigin`。旧版上游 GUI（`gui_main.py --legacy`）的 OPJU 工程保存在该次模型提取的输出目录。

## 配置文件

| 文件 | 用途 |
|---|---|
| `config.toml` | 本机实际配置，由程序读取，已加入 Git 忽略规则 |
| `config.default.toml` | 首次启动时复制的默认模板 |
| `config.example-csv.toml` | 使用项目内示例 CSV 的配置 |
| `config.example-comsol63.toml` | COMSOL 6.3 模型的命令行示例 |

配置路径相对于配置文件自身解析。参数窗口保存成功后，上一份配置会备份为 `config.toml.ui-backup`。

绘图和数据处理参数见 [Origin 绘图参数](docs/SETTINGS_UI.md)。

## 命令行

默认使用项目根目录的 `config.toml`：

```powershell
uv run --locked python main.py
```

常用检查命令：

```powershell
uv run --locked python main.py --check
uv run --locked python main.py --dry-run
uv run --locked python main.py --list-results
uv run --locked python main.py --config config.example-csv.toml
```

| 参数 | 作用 |
|---|---|
| `--check` | 检查依赖、COMSOL 安装和 Origin COM 注册，不启动软件引擎 |
| `--dry-run` | 解析配置并显示运行计划，不连接 COMSOL 或 Origin |
| `--list-results` | 加载 MPH 模型并列出可用结果，不求解模型 |
| `--config PATH` | 使用指定的配置文件 |

CSV 模式不会启动 COMSOL，但正式运行仍会连接 Origin。项目内的 `data/input/example.csv` 是合成示例数据。

## 项目结构

```text
main.py / gui_main.py          命令行和图形界面入口
src/pipeline.py                处理流程编排
src/adapters/                  COMSOL、数据处理和 Origin 适配器
src/models/                    数据模型
lib/comsol_csv_tool/           固定版本的上游 Git 子模块
tests/                         自动化测试
scripts/                       构建、发布和真实软件验证
docs/                          用户与开发文档
```

核心流程：

```text
COMSOL/CSV → 数据清洗与处理 → Origin 工作簿 → 绘图 → 图片与 OPJU
```

完整文档入口见 [docs/README.md](docs/README.md)。

## 使用限制

- 程序只读取已有结果，不负责求解，也不会保存源 MPH 文件。
- 高版本 COMSOL 保存的模型需要兼容版本才能打开。
- 修改坐标单位文字不会换算数据。
- 多条曲线来自同一数据集的多列；暂不合并多个模型或多张表，也不提供多面板排版。
- Savitzky-Golay 平滑要求 X 近似等距；插值要求 X 唯一且递增。
- 三次插值至少需要 4 个点；插值后只保留选中的 X/Y 列，其他列不会自动补值。
- 参数扫描混在同一列时，应先拆分不同条件。
- 图片物理尺寸由像素尺寸和 DPI 决定；PDF 为矢量页面，透明背景只支持 PNG 和 TIFF。
- 程序不处理 COMSOL 或 Origin 的授权问题，软件生成的试用水印也会保留。

## 常见问题

**找不到 COMSOL 或许可证错误**

先确认 COMSOL 可以单独打开目标模型，再运行 `uv run --locked python main.py --check`。配置中的 `[comsol].version` 必须与已安装版本匹配。

**找不到结果或数据列**

使用界面中的识别功能，或运行 `uv run --locked python main.py --list-results` 查看结果 Tag。X/Y 列使用去掉单位后的表头名称；清理后重名的列需要在 `[comsol.column_map]` 中分别命名。

**Origin 无法连接**

先手动启动 Origin，完成首次运行和许可提示。源码版还需使用 64 位 Python，并正确安装 `originpro` 和 `OriginExt`。

**图片或工程保存失败**

检查输出目录是否可写、文件是否被占用，以及 Origin 是否存在未关闭的对话框。完整错误见日志。

**CSV 无法读取**

在配置中尝试 `standard`、`backend` 或 `native` 格式，并检查编码。程序不会自动识别使用逗号作为小数点的文件。

## 开发与测试

```powershell
uv sync --locked --group dev
uv run --locked --group dev poe check
uv run --locked --group dev python scripts/verify_settings_ui.py
```

`poe check` 依次运行 Ruff lint、格式检查、mypy、配置 dry-run 和测试。单项检查可用 `uv run --locked --group dev poe test`、`poe lint`、`poe fmt-check`、`poe typecheck` 或 `poe validate`；需要整理格式时运行 `poe format`。

完成 `uv sync --locked --group dev` 后，也可直接运行 `uv run poe check`。pytest 将临时文件和缓存分别放在项目根目录的 `.pytest-run/`、`.pytest-run-cache/`，避免使用无权限的系统临时目录；两者均不会提交到 Git。

连接真实软件的检查需要单独运行：

```powershell
uv run --locked --group dev python scripts/verify_origin.py
uv run --locked --group dev python scripts/verify_images.py
uv run --locked --group dev python scripts/verify_comsol.py
```

Origin 接口依据见 [API 审计](docs/API_AUDIT.md)。更新上游子模块、COMSOL、Origin 或 `originpro` 后，应重新检查对应接口和真实运行结果。

当前构建曾在 Windows 11、COMSOL 6.3/6.4 和 Origin 2025b 上进行本机检查；Windows 10、其他软件版本和全新无 Python 环境仍可能表现不同。
