# Sideband（简体中文说明）

> 这是 Sideband 的非官方简体中文派生版，保留上游 Mark Qvist / unsigned.io 的版权和许可证。中文构建发布在[本仓库 Releases](https://github.com/diffusion67/Sideband-i18n-zh-cn/releases)。上游安装包未包含本仓库的中文修改。
>
> 本次同步的 GitHub 公开源码版本仍为 **1.9.2**。上游更新的二进制版本与公开源码版本并不同步，不能将此派生版标为 2.2.0。

*本仓库是公开镜像；上游开发在 Reticulum 网络中进行。GitHub 会发布新版本，但最新源码仅可通过 Reticulum 获取。*

Sideband 是适用于 Android、Linux、macOS 和 Windows 的可扩展 LXMF 消息与 LXST 电话客户端，同时提供态势感知、远程控制与监控能力。它可经由 LoRa、分组无线电、Wi‑Fi、I2P、加密二维码纸质消息及 Reticulum 支持的其他媒介通信。

![Sideband 截图](https://github.com/markqvist/Sideband/raw/main/docs/screenshots/devices_small.webp)

Sideband 免费、端到端加密、无需许可、匿名且不依赖基础设施。它使用点对点、分布式的 [LXMF](https://github.com/markqvist/lxmf) 消息系统：无需注册、没有服务提供商、没有最终用户许可协议，也不会收集或监控你的数据。

## 功能

- 通过 Reticulum 上的 LXMF/LXST 进行安全、自主的消息和语音通话。
- 在所有支持的媒介上传输图片、文件和音频消息；Codec2 与 Opus 使音频也可通过 LoRa 和无线电链路工作。
- 安全、直接的 P2P 遥测和位置共享；数据不会交给第三方服务器。
- 支持通过插件扩展遥测、命令和服务。
- 支持在线地图及本地离线地图上的态势显示与地理空间计算。
- 支持加密的纸质二维码消息和 `lxm://` 链接消息。
- Android 设备可作为临时 Reticulum 路由器（Transport Instance）。

Sideband 兼容其他 LXMF 客户端，例如 [MeshChatX](https://git.quad4.io/RNS-Things/MeshChatX) 与 [Nomad Network](https://github.com/markqvist/nomadnet)。应用内“指南”页面介绍了它与常见即时通信系统的区别。

## 安装

### 已提供的构建任务

仓库保留并修复了原有的 Android 和 Windows GitHub Actions 任务，并沿用现有 cx_Freeze 配置补充 Linux/macOS 原生打包。可手动运行，也会在向 `main` 提交 PR 或推送时验证。安装前请核对 Releases 中的版本、架构、签名状态和 SHA-256 校验值。

- **Windows x86_64**：便携 ZIP，解压完整文件夹后运行 `Sideband.exe`，不要只移动 EXE 文件。未进行 Authenticode 签名。
- **Android arm64-v8a**：最低 Android 7 / API 24。未提供签名材料时，任务生成 `release-unsigned.apk`，仅供进一步签名，**不能直接安装**。本任务不会创建新的签名密钥。请使用自己的现有派生版密钥签名并验证后再安装；证书不同的 APK 不能直接覆盖上游版或其他签名的安装。
- **Linux x86_64**：使用 `sbapp/freeze.py` 构建 AppImage，兼容性受构建系统 libc 与本机图形、音频驱动限制。下载后赋予执行权限再运行；没有 FUSE 的系统可使用 `--appimage-extract` 解包后运行 `squashfs-root/AppRun`。
- **macOS Apple Silicon / Intel**：分别构建架构对应的 DMG，将其中的 Sideband.app 拖到“应用程序”。未进行 Developer ID 签名或公证；不要将此状态误认为已通过 Apple 验证。
- **Raspberry Pi / 其他架构**：仅以 Releases 实际提供并验证的架构为准，不要使用 x86_64 安装包。源码或 Python wheel 安装需要各平台依赖，wheel 不是原生独立安装包。

发布任务只汇集同一 `main` 提交的成功构建，生成 SHA-256 校验清单和构建来源记录后发布。实际可用平台、测试范围和签名状态以对应 Release 为准。

本派生版不能使用上游私有签名密钥；上游 README 中的 APK 证书指纹只适用于上游原版，不适用于本仓库构建。

### 从本仓库源码安装

请在独立 Python 虚拟环境中安装本仓库，而不是使用 `pip install sbapp`（该命令会安装上游包）。例如，已有合适 Python 和系统依赖时：

```bash
python -m venv .venv
# Linux/macOS
. .venv/bin/activate
# Windows PowerShell 使用：.venv\Scripts\Activate.ps1
python -m pip install .
sideband
```

Linux 上语音和剪贴板功能通常需要 `libopusfile0`、`codec2`、PortAudio、`xclip`/`xsel` 或 Wayland 剪贴板工具。macOS 还需要可用的音频依赖。完整系统依赖请参考[上游英文安装说明](README.md#installation)。

若尚未配置 Reticulum 连接，请编辑 `~/.reticulum/config`（Windows 为用户目录下 `.reticulum/config`），并按[接口文档](https://reticulum.network/manual/interfaces.html)添加所需接口。

### 本地回归检查

```bash
python -m unittest discover -s tests -v
python -m compileall -q sbapp
```

翻译只应用于明确标记的界面模板，格式化参数在翻译后原样插入。不会翻译用户消息、联系人名称、协议字段或插件提供的内容。Kivy 标记、占位符和技术命令由回归测试检查。

## 创建插件

Sideband 的插件系统支持三类插件：遥测插件、命令插件和服务插件。示例位于 [docs/example_plugins](https://github.com/markqvist/Sideband/tree/main/docs/example_plugins)，包括自定义遥测、BME280、基本命令、GPSd 和 Windows 定位、传播节点统计、摄像头查看、XKCD 漫画及服务插件。

内置二十余种传感器；若不满足需求，可使用 `Custom` 传感器。命令插件可以响应其他 LXMF 客户端的命令消息，服务插件可以将系统服务或桥接器集成到 Sideband。

## 纸质消息示例

英文 README 中提供了一个可导入身份和二维码消息示例。请在应用的“加密密钥”部分导入其中给出的 Reticulum Identity，再扫描二维码或打开 `lxm://` 链接即可解密并查看消息。

## 支持开发

可通过英文 README 所列的 Monero、Bitcoin、Ethereum、Liberapay 或 Ko‑fi 地址支持项目开发。请以英文 README 中的地址为准。

## 许可证

除非另有说明，本项目采用 [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-nc-sa/4.0/) 许可。允许出于任何目的使用和分发二进制副本，但不得收取或接受任何付款或报酬。
