# Sideband（简体中文说明）

> 本文对应仓库中的英文 README。命令、文件名、协议名和校验值保持原样，以免影响安装与验证。

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

### Android

从[最新发行页](https://github.com/markqvist/Sideband/releases/latest)下载 APK。安装后，可在应用的“软件源”页面直接获取更新。

首次安装前应验证 APK 签名证书：

```text
SHA-256 digest: 1c65f01f586a2b73ac4eb8bf48730b3899d046447185fd9d005685a4af20cdea
SHA-1 digest: 4ab9269c320c72f4e4057ec7ea5acade320c2a48
MD5 digest: 09afff8c505089a544ad2bf371c29422
```

若下载源不是官方仓库，或证书哈希不匹配，请勿安装。Android 版本不依赖 Google 或其他供应商的组件；它使用原生 Android OS API，兼容 GrapheneOS、去 Google 化设备及其他自定义 ROM。

### Linux

大多数发行版可直接从[最新发行页](https://github.com/markqvist/Sideband/releases/latest)下载并运行 AppImage。语音、音频消息和剪贴板功能可能还需要 `opusfile` 及 `xclip`、`xsel` 或 `wl-clipboard`。

也可以通过 pip 安装：

```bash
# Debian 13+/Ubuntu 24.04+ 及衍生版所需依赖
sudo apt install python3-pip python3-pyaudio libopusfile0 codec2 xclip xsel

# 安装 Sideband
pip install sbapp --break-system-packages
sideband
```

无界面运行、控制台用途或使用 pipx 时：

```bash
pipx install sbapp
# 或仅安装核心包，再自行安装 rns 和 lxmf
pip install sbapp --no-dependencies
pip install rns lxmf
```

若尚未配置 Reticulum 连接，请编辑 `~/.reticulum/config` 并按[接口文档](https://reticulum.network/manual/interfaces.html)添加所需接口。

### Raspberry Pi

最简单的方式是下载并运行 `aarch64` AppImage。64 位 Raspberry Pi OS 也可安装：

```bash
sudo apt install python3-pyaudio codec2 xclip xsel
pip install sbapp --break-system-packages
sideband
```

较旧的系统可能还需要 `python3-pip`、`python3-dev`、`libopusfile0`、`portaudio19-dev` 等依赖，具体请参考英文 README。

### macOS

在[最新发行页](https://github.com/markqvist/Sideband/releases/latest)下载适用于 ARM 或 Intel 的 DMG，挂载后把 `Sideband` 拖入应用程序文件夹即可。建议另行安装 RNS 命令行工具：

```bash
pip3 install rns --user
```

也可以从源包安装，以使用守护进程、调试日志和设置导入/导出：

```bash
pip3 install sbapp --user
sideband
```

### Windows

从[最新发行页](https://github.com/markqvist/Sideband/releases/latest)下载 Windows ZIP，解压后运行 `Sideband.exe`。初次运行会创建 Reticulum 配置；如需互联网连接，可在 `C:\Users\USERNAME\.reticulum\config` 中添加接口或 Reticulum Testnet 公共中继。

建议额外安装 RNS 工具：

```bash
pip install rns
```

从源包安装 Sideband：

```bash
pip install sbapp
sideband
```

## 创建插件

Sideband 的插件系统支持三类插件：遥测插件、命令插件和服务插件。示例位于 [docs/example_plugins](https://github.com/markqvist/Sideband/tree/main/docs/example_plugins)，包括自定义遥测、BME280、基本命令、GPSd 和 Windows 定位、传播节点统计、摄像头查看、XKCD 漫画及服务插件。

内置二十余种传感器；若不满足需求，可使用 `Custom` 传感器。命令插件可以响应其他 LXMF 客户端的命令消息，服务插件可以将系统服务或桥接器集成到 Sideband。

## 纸质消息示例

英文 README 中提供了一个可导入身份和二维码消息示例。请在应用的“加密密钥”部分导入其中给出的 Reticulum Identity，再扫描二维码或打开 `lxm://` 链接即可解密并查看消息。

## 支持开发

可通过英文 README 所列的 Monero、Bitcoin、Ethereum、Liberapay 或 Ko‑fi 地址支持项目开发。请以英文 README 中的地址为准。

## 许可证

除非另有说明，本项目采用 [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-nc-sa/4.0/) 许可。允许出于任何目的使用和分发二进制副本，但不得收取或接受任何付款或报酬。
