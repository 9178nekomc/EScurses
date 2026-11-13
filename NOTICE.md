# 来源与授权说明

## 上游

- 项目：**EScurses**
- 原始作者：**KID194**（GitHub: [@KID194](https://github.com/KID194)）
- 上游仓库：<https://github.com/KID194/EScurses>
- 本仓库是其 fork：<https://github.com/9178nekomc/EScurses>
- 上游许可证：**MIT**（2026-11-04 添加，完整文本见 [LICENSE](./LICENSE)）

## 授权状态（请务必读）

上游仓库已于 2026-11-04 添加 MIT 许可证。本 fork 同步采用 MIT 许可证，
并在 [LICENSE](./LICENSE) 中保留原作者的版权声明。除非某个文件另有说明，
本仓库中的代码均按 MIT 许可证提供。

因此本项目的授权状态说明如下：

1. `escurses/` 目录下 2.0 版本**新写的代码**（除兼容层外全部为重写）
   由 **9178nekomc** 以 MIT 许可证提供；
2. `escurses/_legacy.py` 的公开接口名称与行为约定源自 KID194 的原始实现，
   这部分著作权仍归原作者；
3. 本 fork 的发布目的是**把改进回流给上游**。如果上游后续更新许可证，
   以上游仓库的声明为准。

> 说明：本文件早期版本写于上游添加 LICENSE 之前，曾误称“上游没有 LICENSE”；
> 该说法已过时，现以上游当前的 MIT 许可证为准。本文件不构成法律意见。

## 主要改动概览

原始版本是一个 102 行的单文件库。2.0 在保留全部旧 API 的前提下重写了内部实现，
详见 [CHANGELOG.md](./CHANGELOG.md) 与 [README-zh.md](./README-zh.md) 的"修复清单"。
