# Zed 中英双语汉化 · Bilingual Chinese Localization for Zed

把 Zed 的界面改成 **中文为主、英文小字参考**（中文后跟更小更淡的英文，便于学习英语），并提供下载即用的一键补丁包。

Turn Zed's interface into **Chinese-first text with smaller, muted English** right after it — usable for daily work and as an English-learning aid — shipped as a download-and-double-click patch package.

> ⚠️ **重要 / Important**
> 本项目**不是** Zed 官方扩展或插件，也**不是** Zed 官方认可的汉化。它是一个基于固定上游版本的**第三方定制构建**，会替换你安装目录里的 `Zed.exe`。
> This is **not** an official Zed extension, plugin, or endorsed localization. It is a **third-party custom build** pinned to one upstream version, and it replaces the `Zed.exe` in your installation folder.

---

# 一、快速使用（中文）

## 适用条件

| 项目 | 要求 |
| --- | --- |
| 操作系统 | 64 位 Windows 10 / 11 |
| Zed | 已正常安装（官方安装包或常见便携解压均可） |
| Python | **Python 3.8 及以上**，安装时勾选 “Add Python to PATH” |
| 版本基线 | 基于 **Zed 1.27.0**（提交 `a5c4ca8`）构建 |

## 三步安装

1. 到本仓库 **Releases** 页面下载 `Zed汉化一键补丁-20261112.zip`，**完整解压**到一个文件夹（不要在压缩包内直接双击）。
2. **保存工作并关闭所有 Zed 窗口**（工具不会强行结束进程，检测到 Zed 正在运行会提示你先退出）。
3. 双击 `Launch.cmd` → 按回车确认 → 看到“汉化补丁已应用”即完成。

## 还原原版

关闭 Zed，双击 `Restore.cmd`，按回车即可把程序逐字节恢复成安装补丁前的状态。

## 命令行（可选）

```text
Launch.cmd --status                          查看当前汉化状态
Launch.cmd --install-dir "D:\software\Zed"   手动指定 Zed 安装目录
Launch.cmd --backup-dir "D:\backup\zed"      自定义备份目录
Restore.cmd --discard                        备份与当前文件不一致时，确认覆盖还原
```

## 工具会做什么、不会做什么

**会做：**

- 从注册表卸载项和常见目录自动定位 Zed 安装位置；
- 校验包内每个文件的 SHA256 与 PE 架构，校验失败直接中止；
- 在 Zed 目录下创建 `zed-bilingual-backup`，备份原文件并记录状态；
- 替换 `Zed.exe`、`conpty.dll`、`OpenConsole.exe`，并放置 `zed.zh-CN.json` 语言资源。

**不会做：**

- 不联网、不下载任何东西；
- 不修改你的 Zed 配置、账号、模型、MCP 或项目文件；
- 不静默结束 Zed 进程；
- 不修改系统执行策略或注册表安全项。

---

# 二、实现思路 / How it works

## 2.1 为什么不能做成“普通插件”

Zed 的扩展 API（manifest + WIT 接口）只能注册语言、主题、调试适配器、MCP 等能力，**无法替换应用本体的菜单栏、设置页、欢迎页、命令面板和 GPUI 标签排版**。因此不存在一个能“装上就汉化”的官方扩展形态。

**结论：** 只能对 Zed 源码打补丁，重新构建一份定制程序。

## 2.2 为什么不能直接改官方 Zed.exe

官方 `Zed.exe` 是**数字签名**的 PE 文件，且签名证书表紧贴文件末尾、之后没有可写入空间：

1. 追加任何字节都会破坏 Authenticode 签名；
2. 界面英文是 ASCII/UTF-8，中文是 3 字节，**无法等长替换**；
3. 插入内容会让所有 PE 段的 RVA 与文件偏移错位，需要整体重排；
4. 重新签名需要 Zed Industries 的私钥——不可能。

**结论：** 二进制热补丁不可行，只能源码构建。

## 2.3 中文优先 + 英文小字的实现

GPUI 的 `TextRun` **不支持给单个 run 单独设字号**，所以双语标签不是“一个字符串里两种字号”，而是**两个元素**：

```text
中文文本（正常字号）
英文文本（约 75% 字号，Color::Muted）
```

具体做法：

1. 在 `crates/ui` 新增 `localization` 模块，提供 `translate()`、`translate_text()`、`primary_text()`、`bilingual_text()`；
2. 词库用 `OnceLock` 惰性加载，内置词库与可选的 `zed.zh-CN.json` 合并；
3. 支持**安全模板匹配**：像 `New {} Thread` 这类带占位的文案，用正则匹配运行时拼接结果并回填捕获组，保证文件名、代码、用户数据不会被误翻；
4. 提供显式开关接口：`Label::new_localized()`、`Headline::new_localized()`、`TreeViewItem::localized()`、`Button::label_verbatim()`、`Tooltip::text_verbatim()`。

**关键取舍：`Label::new()` 默认永不翻译。** 这样可以保护文件名、代码、配置键、模型名、搜索框内容等用户数据——只有显式标记为界面文案的字符串才会被翻译。

## 2.4 词库策略

- 基础词库来源：[TC999/zed-loc](https://github.com/TC999/zed-loc)（MIT）；
- 本项目补充审校，覆盖菜单、设置、命令面板、助手面板、Git、调试器、终端、协作等界面；
- 分发版语言资源为 **3060 条**；编译期合并后约 **9695 条**；
- 英文作为参考保留在中文之后，符合“顺便学英语”的使用目标。

## 2.5 安装器设计

`patch_zed.py` 不依赖任何第三方库，只做四件事：

1. **定位**：注册表 Uninstall 键 + `LOCALAPPDATA` / `Program Files` / 各盘符启发式查找；
2. **校验**：包内文件 SHA256 与 PE Machine 字段（必须是 x64 可执行，非 DLL）；
3. **备份**：先把要改的文件复制到 `zed-bilingual-backup` 并写入 `state.json`，全部校验通过后才替换；
4. **回滚**：按 `state.json` 逐字节还原，并删除补丁新增的文件。

任何一步失败都会中止且不留半成品；已存在备份目录时会拒绝重复安装，避免覆盖唯一的还原点。

---

# 三、局限性与风险 / Limitations

请务必逐条阅读，这些都是**已知限制**，不是待修问题。

1. **只支持 Windows x64。** macOS / Linux 未构建、未验证。
2. **固定版本。** 安装后你的 Zed 是 1.27.0 的定制版，不是最新版；上游新功能不会自动获得。
3. **必须关闭自动更新。** 否则 Zed 官方更新会覆盖汉化版。建议安装后在设置里关闭 `auto_update`。
4. **每次 Zed 大版本更新都需要重新构建补丁包**，无法自动适配新版官方程序。
5. **程序未签名。** 首次运行可能触发 Windows SmartScreen 提示；这与下载任何第三方未签名程序的风险相同，请自行判断是否信任来源。
6. **需要 Python 3.8+。** 这是安装器的唯一外部依赖。
7. **汉化不是 100%。** 部分文案在程序里未接入本地化渲染通道（例如助手输入框提示、新建会话标题的部分动态文本），仅改词库无法生效，需要改源码重新编译。
8. **不翻译的内容（有意保留）：** 文件名、路径、代码、配置键、动作标识、模型名、第三方品牌名、快捷键。
9. **可能影响依赖内部行为。** 本项目替换了 `conpty.dll` 与 `OpenConsole.exe`（终端控制台组件）；如你使用特殊终端配置，请先备份。
10. **法律层面。** 上游 Zed 使用 GPL-3.0（部分文件 Apache-2.0）。分发预编译二进制时，**必须同时提供对应源码**；本仓库的 `dist/` 中包含了本工具的完整源码与补丁说明。请遵守相应许可证，不得移除版权与许可声明。

---

# 四、仓库结构

```text
dist/unpacked/                      发布包的可读源码视图（安装脚本、清单、词库、许可证）
dist/unpacked/patch_zed.py          一键安装与还原逻辑
dist/unpacked/patch.json            版本基线与文件 SHA256 清单
dist/unpacked/payload/zed.zh-CN.json  语言资源（3060 条）
sbom/zed-pinned-sbom.json           上游依赖与许可证清单（1771 个依赖，SPDX）
licenses/                           上游与词库许可证原文
```

发布包（发布在 Releases 附件）内部：

```text
Launch.cmd            一键安装入口
Restore.cmd           一键还原入口
patch_zed.py          安装/还原逻辑（标准库实现，无第三方依赖）
patch.json            版本基线与文件 SHA256 清单
payload/Zed.exe       定制构建的双语程序（约 380 MB）
payload/zed.zh-CN.json  语言资源（3060 条）
payload/conpty.dll、OpenConsole.exe   终端控制台组件
licenses/             GPL-3.0、Apache-2.0、zed-loc MIT
validation/           实机效果截图
```

> **GPL-3.0 说明：** 本仓库提供本工具的源码、补丁说明、词库与依赖清单；二进制发布包作为 Release 附件提供。两者共同构成 GPL-3.0 要求的“对应源码 + 可执行程序”分发。<br>
> **GPL-3.0 note:** This repository ships the tool's source, dictionary and SBOM; the binaries are attached to Releases. Together they form the "corresponding source + executable" distribution required by GPL-3.0.

---

# 五、English summary

## What it is

A download-and-run patch package that turns Zed's UI into **Chinese-first text with smaller, muted English** right after each label. It replaces `Zed.exe` with a custom build compiled from Zed **1.27.0** (`a5c4ca8`).

## Usage

1. Download `Zed汉化一键补丁-20261112.zip` from the **Releases** page and **fully extract** it.
2. Close Zed (save your work first).
3. Double-click `Launch.cmd`, press Enter. Run `Restore.cmd` to revert byte-for-byte.

Requires 64-bit Windows and **Python 3.8+** on PATH.

## Why not a normal plugin?

Zed's extension API cannot replace native menus, settings pages, the welcome screen, the command palette, or GPUI label layout, so no installable extension can localize the app shell.

## Why not patch the official binary?

The official `Zed.exe` is Authenticode-signed with its certificate table flush against EOF. Any byte we add breaks the signature, CJK text needs 3 bytes versus 1 for ASCII (no in-place swap is possible), and inserted content would misalign every PE section. Re-signing would require Zed Industries' private key.

## How the bilingual rendering works

GPUI `TextRun` has no per-run font size, so each bilingual label is rendered as **two elements**: the Chinese text at normal size, then English at ~75% size in `Color::Muted`. A `localization` module exposes `translate()`, `translate_text()`, `primary_text()` and `bilingual_text()`, backed by an embedded dictionary merged with an optional `zed.zh-CN.json`, plus regex-based safe template matching so runtime-formatted strings translate without touching user data.

`Label::new()` deliberately **never** translates — only explicitly localized widgets do — which protects filenames, code, config keys, and model names.

## Known limitations

Windows x64 only; pinned to 1.27.0; auto-update must be disabled or it overwrites the patch; every upstream major release needs a rebuild; the binary is unsigned (SmartScreen may warn); Python 3.8+ required for the installer; coverage is high but not complete — some strings are not wired to the localization render path and need a recompile; filenames, paths, code, config keys, brand names and shortcuts stay in English on purpose.

## License

Zed is licensed GPL-3.0 (some files Apache-2.0). Distributing prebuilt binaries requires making the corresponding source available; this repository ships the tool's full source and its SBOM. Base translation data comes from [TC999/zed-loc](https://github.com/TC999/zed-loc) (MIT). See `licenses/`.

---

## 致谢 / Credits

- [Zed Industries / zed](https://github.com/zed-industries/zed) — 上游编辑器（GPL-3.0）
- [TC999/zed-loc](https://github.com/TC999/zed-loc) — 基础中文词库（MIT）
