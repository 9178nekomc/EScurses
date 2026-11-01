# 来源与授权说明

## 上游

- 项目：**EScurses**
- 原始作者：**KID194**（GitHub: [@KID194](https://github.com/KID194)）
- 上游仓库：<https://github.com/KID194/EScurses>
- 本仓库是其 fork：<https://github.com/9178nekomc/EScurses>

## 授权状态（请务必读）

上游仓库**没有附带任何 LICENSE 文件**。按著作权法默认规则，这表示"保留所有权利"，
任何人（包括本 fork）都不能单方面为上游代码另行指定许可证。

因此本项目的授权状态说明如下：

1. `escurses/` 目录下 2.0 版本**新写的代码**（除兼容层外全部为重写）
   由 **9178nekomc** 以 MIT 许可证提供；
2. `escurses/_legacy.py` 的公开接口名称与行为约定源自 KID194 的原始实现，
   这部分著作权仍归原作者；
3. 本 fork 的发布目的是**把改进回流给上游**。如果 KID194 为本项目选定许可证，
   以原作者的声明为准，本文件随之失效。

换句话说：想在自己项目里用，请先确认上游作者的意愿；本 fork 不是法律意见。

## 主要改动概览

原始版本是一个 102 行的单文件库。2.0 在保留全部旧 API 的前提下重写了内部实现，
详见 [CHANGELOG.md](./CHANGELOG.md) 与 [README-zh.md](./README-zh.md) 的"修复清单"。
