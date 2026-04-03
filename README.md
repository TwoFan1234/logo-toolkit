# Logo Toolkit

`Logo Toolkit` 是一个 Windows 优先的桌面工具集，首个内置工具是“批量加 Logo”。

## 功能

- 批量导入图片文件或整个文件夹
- 为整批图片统一选择一个 logo
- 在预览图中通过拖动和缩放控制 logo 的位置和大小
- 同步支持数值输入，方便精确调整
- 支持导出到新文件夹或直接覆盖原图
- 处理过程中显示进度、成功/失败状态和失败原因
- 工具集壳结构已就绪，后续可以继续增加批量裁剪、改尺寸等工具

## 快速开始

1. 安装依赖：

```bash
pip install -e .[dev]
```

2. 启动应用：

```bash
logo-toolkit
```

或：

```bash
python -m logo_toolkit
```

## 打包 Windows 可执行版

```bash
pyinstaller packaging/logo_toolkit.spec
```

打包完成后，可执行文件位于 `dist/LogoToolkit/LogoToolkit.exe`。

## 项目结构

```text
src/logo_toolkit/
  core/
  tools/
  ui/
tests/
packaging/
```

## 设计说明

- logo 位置和大小使用归一化比例保存，保证不同分辨率图片使用同一套参数时表现一致。
- 图像处理逻辑与 UI 解耦，后续可以复用到命令行、自动化任务或服务端处理。
- v1 只支持每次批处理使用一个 logo，并将同一套 placement 应用于全部图片。
