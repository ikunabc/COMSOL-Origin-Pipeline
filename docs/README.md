# 文档索引

## 用户文档

- [Windows 发布版](WINDOWS_EXE.md)：EXE 下载、启动、文件位置和发布版检查参数。
- [Origin 绘图参数](SETTINGS_UI.md)：参数页、批量绘图、参数记忆和界面检查。
- [项目主页](../README.md)：源码安装、基本流程、命令行和常见问题。

## 开发与发布

- [API 审计](API_AUDIT.md)：上游 COMSOL 提取模块和 Origin 接口依据。
- [第三方声明](THIRD_PARTY_NOTICES.txt)：发布包使用的第三方软件声明。

| 脚本 | 用途 |
|---|---|
| [`scripts/verify_settings_ui.py`](../scripts/verify_settings_ui.py) | 检查界面和配置读写，不连接 COMSOL 或 Origin |
| [`scripts/verify_origin.py`](../scripts/verify_origin.py) | 连接真实 Origin 进行绘图、导出和工程检查 |
| [`scripts/verify_comsol.py`](../scripts/verify_comsol.py) | 连接真实 COMSOL 进行模型结果提取检查 |
| [`scripts/verify_images.py`](../scripts/verify_images.py) | 检查导出图片 |
| [`scripts/build_windows.py`](../scripts/build_windows.py) | 构建 Windows EXE |
| [`scripts/package_release.py`](../scripts/package_release.py) | 生成发布包、许可证和校验和 |
| [`scripts/publish_release.py`](../scripts/publish_release.py) | 发布已经构建并验证的文件 |

`API_AUDIT.md` 是开发依据，不是普通用户操作手册。JSON 验证报告由检查脚本生成且不提交到仓库。
