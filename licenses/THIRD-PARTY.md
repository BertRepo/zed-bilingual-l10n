# 第三方组件与许可证 / Third-party components and licenses

本项目基于 Zed 源码构建，并包含第三方词库。分发时请保留所有原始许可声明。

This project is built from the Zed source tree and bundles third-party translation data. Keep all original license notices when redistributing.

## 直接来源 / Direct sources

| 组件 Component | 版本 Version | 许可证 License | 说明 Notes |
| --- | --- | --- | --- |
| [zed-industries/zed](https://github.com/zed-industries/zed) | 1.27.0 (`a5c4ca8`) | GPL-3.0（部分 Apache-2.0） | 上游编辑器源码。本项目为其源码补丁构建。<br>Upstream editor source; this project is a patched build of it. |
| [TC999/zed-loc](https://github.com/TC999/zed-loc) | — | MIT | 基础中文词库。<br>Base Chinese translation dictionary. |
| Rust toolchain / MSVC CRT / Windows SDK | — | MIT OR Apache-2.0 / Microsoft EULA | 构建工具链，不随本仓库再分发（见下方说明）。<br>Build toolchain, not redistributed here (see below). |

## 间接依赖 / Transitive dependencies

完整依赖清单见 [`sbom/zed-pinned-sbom.json`](../sbom/zed-pinned-sbom.json)（SPDX 格式，1771 个依赖）。

Full dependency list: SPDX document with 1771 packages.

许可证分布概览 / License distribution:

| 许可证 License | 数量 Count |
| --- | --- |
| MIT OR Apache-2.0 | 671 |
| MIT | 442 |
| NOASSERTION（未标注 undeclared） | 147 |
| Apache-2.0 OR MIT | 137 |
| Apache-2.0 | 91 |
| Apache-2.0 WITH LLVM-exception | 45 |
| Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT | 39 |
| Zlib OR Apache-2.0 OR MIT | 24 |
| Unicode-3.0 | 24 |
| BSD-3-Clause | 23 |
| MPL-2.0 | 17 |
| ISC | 15 |

## 关于 Windows 运行时组件 / Runtime components

发布包内的 `conpty.dll` 与 `OpenConsole.exe` 来自上游 Zed 的 Windows 终端（ConPTY）依赖，由 Zed 构建流程下载。如你所在组织对再分发微软组件有额外要求，请自行评估。

The `conpty.dll` and `OpenConsole.exe` files in the release package come from Zed's Windows ConPTY dependency, downloaded by Zed's build process. Evaluate Microsoft's redistribution terms for your own organization.

## GPL-3.0 合规说明 / GPL-3.0 compliance

- 本仓库提供：本工具源码、安装器、语言资源、补丁与依赖清单。
- Releases 提供：对应版本的二进制发布包。
- 上游 Zed 完整源码可从 [zed-industries/zed](https://github.com/zed-industries/zed) 以提交 `a5c4ca8bf6c4717a328a4a61b42d6d1d38949bcc` 获取。

- This repository: tool source, installer, language resource, SBOM.
- Releases: the matching binary package.
- Upstream Zed source: available from zed-industries/zed at commit `a5c4ca8bf6c4717a328a4a61b42d6d1d38949bcc`.

本仓库未修改上游许可证文本，`LICENSE` 为 GPL-3.0 全文，`licenses/LICENSE-APACHE` 为 Apache-2.0 全文。

No upstream license text was modified. `LICENSE` is the full GPL-3.0 text; `licenses/LICENSE-APACHE` is the full Apache-2.0 text.
