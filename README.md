# Logo Toolkit

`Logo Toolkit` 是一个 Windows 优先的桌面图片工具集，当前内置两个批量处理工具：

- `批量加 Logo`：给整批图片统一叠加一个可交互定位的 Logo
- `批量处理图片`：批量完成转格式、压缩和改尺寸

## 当前功能

### 批量加 Logo

- 批量导入图片文件或整个文件夹
- 为整批图片统一选择一个 Logo
- 在预览区拖动和缩放 Logo，实时调整位置与大小
- 支持导出到新文件夹或覆盖原图
- 支持模板保存与复用
- 支持导出时保持原文件夹结构

### 批量处理图片

- 批量转格式：支持输出为 `JPG`、`PNG`、`WEBP`
- 批量压缩：支持 `关闭 / 轻度 / 中等 / 高压缩`
- 批量改尺寸：
  - 按百分比缩放
  - 按最长边缩放
  - 按宽高缩放
- 支持导出到新文件夹或覆盖原图
- 支持导出时保持原文件夹结构
- 导出完成后自动打开输出目录

## 快速开始

1. 安装依赖

```bash
pip install -e .[dev]
```

2. 启动应用

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

打包完成后，可执行文件位于：

```text
dist/LogoToolkit/LogoToolkit.exe
```

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

- 核心图片处理逻辑与界面解耦，便于后续继续扩展更多工具
- 批量处理默认优先保证结果清晰、路径可控、适合新手使用
- v1 聚焦常见图片整理场景，不包含更复杂的裁剪、滤镜、自动命名规则等高级功能
