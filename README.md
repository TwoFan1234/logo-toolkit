# 素材工具箱

素材工具箱是一个 Windows 优先的批量图片/视频处理桌面工具，面向非技术同事使用，同时保留源码工程，方便后续继续扩展。

## 已有功能

- 批量处理图片
- 批量给图片添加 Logo
- 批量视频处理
- 批量给视频加 EC，可把透明 MOV 结尾批量叠到素材尾部
- 批量给视频添加 Logo
- 视频套边框，支持把 16:9、1:1、9:16 等素材相互扩展成其他画幅

## 给团队同事使用

团队同事不需要安装 Python，也不需要使用 GitHub。维护者打包后，把 `release` 目录里的 zip 文件发到团队云盘即可。

生成团队分享包：

```powershell
powershell -ExecutionPolicy Bypass -File packaging/create_team_release.ps1
```

生成后会得到类似：

```text
release/素材工具箱-v0.2-20260417.zip
```

同事只需要解压 zip，然后双击 `素材工具箱.exe`。当前发布包使用单文件 exe，减少误删 `_internal` 文件夹导致无法启动的问题。

`V0.2` 里新增了“批量加 EC”入口，适合给一整批视频统一叠加透明 MOV 结尾素材。当前页面保留最常用的参数，只需要选 EC 文件和重叠时长即可。

更详细的小白说明见：

```text
docs/TEAM_USAGE.md
```

## 开发运行

```powershell
pip install -e .[dev]
logo-toolkit
```

也可以使用：

```powershell
python -m logo_toolkit
```

## 打包 Windows 可执行版

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

如果只想生成团队可分享 zip，优先使用：

```powershell
powershell -ExecutionPolicy Bypass -File packaging/create_team_release.ps1
```

## 测试

```powershell
python -m pytest -q
```

## 两台电脑同步开发

开始开发前先拉取最新代码：

```powershell
git pull --ff-only origin main
```

改完后提交并推送：

```powershell
git add .
git commit -m "描述这次改动"
git push origin main
```