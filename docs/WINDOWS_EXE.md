# Windows 使用说明

## 启动

到 [Releases](https://github.com/ikunabc/comsol-origin-quick-processing/releases/latest) 下载 Windows x64 EXE，双击打开。如果下载的是 ZIP，先解压，再运行其中的 `COMSOLOrigin.exe`。

不需要安装 Python 或 Git。首次启动需要解包，可能要等几十秒。

程序依赖本机的 COMSOL 和 Origin 2024/2024b/2025/2025b，两者都需要有效授权。MPH 文件要提前求解，并使用兼容的 COMSOL 版本打开。

## 文件保存在哪里

配置和日志放在 `%LOCALAPPDATA%\COMSOLOrigin`。可把这个路径粘贴到资源管理器地址栏中打开。

- 配置：`config.toml`
- 日志：`logs/gui.log`、`logs/pipeline.log`
- 默认图片目录：`output/figures`

图片目录可以在“Origin 绘图参数…”中修改。GUI 生成的 OPJU 工程保存在本次模型提取的输出目录。

发行包只带合成示例数据，不带个人模型、科研结果或软件许可证。当前 EXE 未做代码签名，下载校验码见 Release 中的 `SHA256SUMS.txt`。

## 从源码打包

在 Windows x64、Python 3.11 或 3.12 环境中执行：

```powershell
git clone --recurse-submodules https://github.com/ikunabc/comsol-origin-quick-processing.git
cd comsol-origin-quick-processing
python -m pip install -r requirements-build.txt
python scripts/build_windows.py
```

生成的文件为 `dist/COMSOLOrigin.exe`。打包清单在 `COMSOLOrigin.spec`，包含 Python、Qt、数据处理依赖和上游提取模块，不包含 COMSOL 引擎和 Origin 桌面程序。

## 检查打包结果

以下选项用于开发检查：

- `--bundle-check`：检查依赖、原界面、参数按钮和 COMSOL 安装发现。
- `--verify-origin`：用合成数据检查处理、绘图、PNG/TIFF/PDF 导出及工程重开。
- `--verify-comsol`：读取 COMSOL 6.3 自带 busbar 示例中的结果表。
- `--verify-comsol --verify-origin`：将示例表提取的数据用于绘图、导出和工程重开检查。

检查报告放在 `%LOCALAPPDATA%\COMSOLOrigin\bundle-test`，验证工程放在当前工作目录的 `bundle-test` 中。报告中的 PASS 表示脚本内检查通过，进程能否正常退出也需要另外确认。

当前构建在本机 Windows 11 上做过检查；Windows 10 和全新无 Python 虚拟机尚未单独实测。
