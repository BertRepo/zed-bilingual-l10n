#!/usr/bin/env python3
"""One-click bilingual Zed patcher and restorer (Windows, Python 3.8+).

Start it through Launch.cmd: PowerShell then satisfies the local script policy
while PowerShell itself stays unsigned-safe. The tool never changes settings,
never downloads anything and never kills Zed. It swaps the Zed program plus a
small runtime language resource, only after writing a verified backup that
Restore.cmd can use.
"""
import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

FORMAT = "zed-bilingual-one-click-v1"
MIN_MAIN = 10 * 1024 * 1024
MIN_COMPANION = 10 * 1024
PROCESS_PATTERN = re.compile(r"^zed($|[-_])", re.IGNORECASE)
BACKUP_DIR_NAME = "zed-bilingual-backup"
LAUNCHER = "Launch.cmd"
PROGRAM_RE = re.compile(r"^Zed\.exe$", re.IGNORECASE)
STATE_KEYS = ("format", "version", "install_dir", "created_utc", "files")


class ToolError(Exception):
    pass


def prepare_console_encoding():
    """Make Chinese output readable in the legacy Windows console."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    if os.name != "nt":
        return
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def say(message=""):
    print(message, flush=True)


def digest(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pe_info(path):
    """Return (machine, is_dll) for a PE image, raising for unusable files."""
    try:
        with open(str(path), "rb") as stream:
            header = stream.read(64)
            if len(header) < 64 or header[:2] != b"MZ":
                raise ToolError("不是 Windows 可执行文件: {}".format(Path(path).name))
            offset = int.from_bytes(header[0x3C:0x40], "little")
            stream.seek(offset)
            coff = stream.read(24)
    except OSError as error:
        raise ToolError("无法读取文件: {} ({})".format(Path(path).name, error))
    if len(coff) < 24 or coff[:4] != b"PE\0\0":
        raise ToolError("PE 头无效: {}".format(Path(path).name))
    return int.from_bytes(coff[4:6], "little"), bool(int.from_bytes(coff[22:24], "little") & 0x2000)


def check_pe_file(path, minimum, want_dll, label):
    if not path.is_file():
        raise ToolError("缺少文件: {}".format(path))
    size = path.stat().st_size
    if size < minimum:
        raise ToolError("{} 大小异常 ({} 字节)".format(label, size))
    machine, is_dll = pe_info(path)
    if machine != 0x8664:
        raise ToolError("{} 必须是 64 位 Windows 程序".format(label))
    if is_dll != want_dll:
        raise ToolError("{} 文件类型不符".format(label))


def plain_path(path):
    cursor = Path(os.path.abspath(str(path)))
    while True:
        if cursor.exists() and cursor.is_symlink():
            raise ToolError("路径包含符号链接，已拒绝: {}".format(cursor))
        if cursor.parent == cursor:
            return
        cursor = cursor.parent


def running_zed():
    """Return names of running Zed-like processes without touching them."""
    if os.name != "nt":
        return []
    kernel32 = ctypes.windll.kernel32
    class Entry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot in (0, -1):
        return []
    entry = Entry()
    entry.dwSize = ctypes.sizeof(Entry)
    names = []
    try:
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            name = entry.szExeFile
            if PROCESS_PATTERN.match(name or ""):
                names.append(name)
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return names


def require_zed_closed():
    names = running_zed()
    if names:
        raise ToolError("请先退出 Zed（检测到进程: {}）。请先保存编辑内容，本工具不会强制结束任何程序。".format("、".join(sorted(set(names)))))


def load_patch(patch_dir):
    patch_file = patch_dir / "patch.json"
    if not patch_file.is_file():
        raise ToolError("缺少 patch.json，补丁包可能没有完整解压")
    with open(str(patch_file), encoding="utf-8-sig") as stream:
        patch = json.load(stream)
    if not isinstance(patch, dict) or patch.get("format") != FORMAT:
        raise ToolError("patch.json 格式不受支持")
    for key in ("version", "base_commit", "base_version", "upstream_sha256", "files"):
        if not patch.get(key):
            raise ToolError("patch.json 缺少字段: {}".format(key))
    payload = patch_dir / patch.get("payload_dir", "payload")
    files = patch["files"]
    if not isinstance(files, dict) or "Zed.exe" not in files:
        raise ToolError("patch.json 文件清单不完整")
    return patch, payload, files


def verify_payload(payload, files):
    for name, expected in files.items():
        target = payload / name
        if not target.is_file():
            raise ToolError("补丁文件缺失: {}".format(name))
        actual = digest(target)
        if actual.lower() != str(expected).lower():
            raise ToolError("补丁文件校验失败（下载不完整或被修改）: {}".format(name))
    check_pe_file(payload / "zed.exe", MIN_MAIN, False, "补丁程序")
    for name in ("conpty.dll", "OpenConsole.exe"):
        if name in files:
            check_pe_file(payload / name, MIN_COMPANION, name.lower().endswith(".dll"), name)
    language = payload / "zed.zh-CN.json"
    if not language.is_file():
        raise ToolError("补丁缺少语言资源 zed.zh-CN.json")
    with open(str(language), encoding="utf-8-sig") as stream:
        translations = json.load(stream)
    if not isinstance(translations, dict) or not translations:
        raise ToolError("语言资源不是有效的 英->中 映射")
    if not all(isinstance(value, str) for value in translations.values()):
        raise ToolError("语言资源包含非文本条目")


def display_name_from_inno(zed_exe):
    """Read the installer's version resource: ProductVersion is the app version."""
    if os.name != "nt":
        return ""
    path = str(Path(zed_exe).resolve()).replace("'", "''")
    script = (
        "$v=(Get-Item -LiteralPath '{0}' -ErrorAction Stop).VersionInfo;"
        "$name=$v.FileDescription;"
        "if($name -match 'Setup|Uninstall' -or $name -eq 'Zed Dev'){{$v.ProductVersion}}"
        "elseif(($v.OriginalFilename -eq 'Zed.exe') -and ($v.ProductVersion -match '\\+' -or $v.ProductVersion -eq $v.FileVersion)){{$v.ProductVersion}}"
        "elseif($v.OriginalFilename -eq 'Zed.exe'){{''}}else{{''}}"
    ).format(path)
    try:
        info = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                              capture_output=True, text=True, timeout=30)
        return info.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def discover_install_dir():
    if os.name != "nt":
        raise ToolError("当前版本仅支持 Windows")
    import winreg
    import string
    found = []

    def add(path):
        try:
            if path and (Path(path) / "Zed.exe").is_file() and (Path(path) / "Zed.exe").stat().st_size >= MIN_MAIN:
                resolved = Path(path).resolve()
                if resolved not in found:
                    found.append(resolved)
        except OSError:
            pass

    for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                      (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                      (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")):
        try:
            with winreg.OpenKey(hive, key) as parent:
                for index in range(winreg.QueryInfoKey(parent)[0]):
                    try:
                        with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as app:
                            try:
                                display = winreg.QueryValueEx(app, "DisplayName")[0]
                            except OSError:
                                continue
                            if "zed" not in str(display).lower():
                                continue
                            try:
                                location = winreg.QueryValueEx(app, "InstallLocation")[0]
                            except OSError:
                                continue
                            add(location)
                    except OSError:
                        continue
        except OSError:
            continue
    local = os.environ.get("LOCALAPPDATA", "")
    add(os.path.join(local, "Programs", "Zed"))
    add(os.path.join(local, "Zed"))
    add(os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Zed"))
    add(os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), "Zed"))
    for drive in string.ascii_uppercase:
        root = "{}:\\".format(drive)
        if not os.path.isdir(root):
            continue
        for sub in ("software", "Software", "Apps", "app", "Programs"):
            add(os.path.join(root, sub, "Zed"))
    if not found:
        raise ToolError("未找到 Zed 安装目录，请用 --install-dir 指定主程序所在的 Zed.exe 目录")
    found.sort(key=lambda p: len(str(p)))
    return found[0]


def describe(install_dir):
    zed = install_dir / "Zed.exe"
    size = zed.stat().st_size
    return "{}（{} 字节，版本 {}）".format(install_dir, size, version_label(install_dir) or "未知")


def version_label(install_dir):
    """App version label: prefer the Inno EULA-backed uninstaller resource."""
    candidate = Path(install_dir) / "unins000.exe"
    if candidate.is_file():
        value = display_name_from_inno(candidate)
        if value:
            return value
    zed_exe = Path(install_dir) / "Zed.exe"
    if zed_exe.is_file():
        value = display_name_from_inno(zed_exe)
        if value:
            return value
    return ""


def load_state(backup_dir):
    state_file = Path(backup_dir) / "state.json"
    if not state_file.is_file():
        return None
    try:
        with open(str(state_file), encoding="utf-8-sig") as stream:
            state = json.load(stream)
    except (OSError, ValueError):
        raise ToolError("备份状态文件损坏，无法继续: {}".format(state_file))
    if not isinstance(state, dict) or state.get("format") != FORMAT:
        raise ToolError("备份不是本工具创建的，已拒绝: {}".format(backup_dir))
    return state


def save_state(backup_dir, state):
    target = Path(backup_dir) / "state.json"
    temporary = target.with_suffix(".tmp")
    with open(str(temporary), "w", encoding="utf-8") as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(str(temporary), str(target))


def backup_file(install_dir, backup_dir, relative):
    source = Path(install_dir) / relative
    saved = {"relative": relative, "existed": source.is_file()}
    if saved["existed"]:
        saved["sha256"] = digest(source)
        saved["size"] = source.stat().st_size
    return saved


def apply_patch(install_dir, patch, payload, files, backup_dir):
    install_dir = Path(install_dir)
    backup_dir = Path(backup_dir)
    plain_path(install_dir)
    plain_path(backup_dir)

    zed_exe = install_dir / "Zed.exe"
    if not zed_exe.is_file():
        raise ToolError("目标目录中找不到 Zed.exe，请指定主程序所在的安装目录")
    machine, is_dll = pe_info(zed_exe)
    if machine != 0x8664 or is_dll:
        raise ToolError("目标 Zed.exe 不是 64 位 Windows 可执行程序")
    require_zed_closed()

    if backup_dir.exists():
        previous = load_state(backup_dir)
        zed_hash = digest(zed_exe) if zed_exe.is_file() else ""
        original_hash = ""
        for entry in ((previous or {}).get("files") or []):
            if str(entry.get("relative", "")).lower() == "zed.exe":
                original_hash = str(entry.get("sha256") or "")
                break
        if previous and original_hash and zed_hash.lower() == original_hash.lower():
            # The previous run was already restored; retire its leftover backup.
            shutil.rmtree(str(backup_dir))
        else:
            raise ToolError(
                "检测到已有备份目录 {}：那说明当前可能已经是汉化版，或上次安装未完成。\n"
                "请运行 Restore.cmd 恢复原版，或使用 Restore.cmd --discard 确认不需要回滚。".format(backup_dir))

    state = {
        "format": FORMAT,
        "version": patch["version"],
        "base_commit": patch["base_commit"],
        "base_version": patch["base_version"],
        "installed_version": version_label(install_dir),
        "install_dir": str(install_dir),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": [],
    }
    for name in files:
        state["files"].append({"relative": name, "backup": None})
    for name in ("Zed.exe",):
        if not any(entry["relative"].lower() == name.lower() for entry in state["files"]):
            state["files"].append({"relative": name, "backup": None})

    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir()
    # Record originals first; if copying fails half-way, nothing in the install is touched yet.
    for entry in state["files"]:
        source = install_dir / entry["relative"]
        info = {"existed": source.is_file()}
        if info["existed"]:
            info["sha256"] = digest(source)
            info["size"] = source.stat().st_size
            saved = backup_dir / entry["relative"]
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(saved))
            if digest(saved) != info["sha256"]:
                raise ToolError("备份校验失败，尚未修改 Zed: {}".format(entry["relative"]))
            entry["backup"] = str(Path(entry["relative"]))
        entry.update(info)
    save_state(backup_dir, state)

    require_zed_closed()
    for name, expected in files.items():
        target = install_dir / name
        restored = backup_dir / name
        if target.is_file() and not restored.is_file():
            # Defensive: never replace a file that is not recorded in the backup.
            raise ToolError("目标文件未备份，已停止: {}".format(name))
        shutil.copy2(str(payload / name), str(target))
        if digest(target).lower() != str(expected).lower():
            raise ToolError("安装校验失败: {}".format(name))
    say("汉化补丁已应用。备份: {}".format(backup_dir))
    say("如需还原原版，运行 Restore.cmd。")


def restore(install_dir, backup_dir, discard=False):
    backup_dir = Path(backup_dir)
    state = load_state(backup_dir)
    if state is None:
        raise ToolError("没有找到可回滚的备份: {}".format(backup_dir))
    install_dir = Path(state.get("install_dir") or install_dir)
    plain_path(install_dir)
    require_zed_closed()
    problems = []
    for entry in state["files"]:
        relative = entry["relative"]
        target = install_dir / relative
        saved = backup_dir / relative if entry.get("backup") else None
        if entry.get("existed"):
            if not saved or not saved.is_file():
                problems.append("备份缺失: {}".format(relative))
            elif digest(saved).lower() != str(entry.get("sha256", "")).lower():
                problems.append("备份已损坏: {}".format(relative))
        elif target.is_file() and not discard:
            # A file we added; only remove when it is still exactly what we installed.
            expected = entry.get("installed_sha256")
            if expected and digest(target).lower() != str(expected).lower():
                problems.append("用户修改过的文件需要确认: {}".format(relative))
    if problems:
        raise ToolError("无法安全还原：\n  " + "\n  ".join(problems) + "\n如确实要覆盖，使用 Restore.cmd --discard。")
    for entry in state["files"]:
        relative = entry["relative"]
        target = install_dir / relative
        saved = backup_dir / relative
        if entry.get("existed"):
            shutil.copy2(str(saved), str(target))
            if digest(target).lower() != str(entry.get("sha256", "")).lower():
                raise ToolError("还原校验失败: {}".format(relative))
        elif target.is_file():
            target.unlink()
    say("已还原到补丁前状态。备份目录保留在: {}".format(backup_dir))
    say("确认无误后可手动删除该备份目录。")


def install_shortcut(install_dir, restore=False):
    """Create a Desktop / Start Menu shortcut that opens the list of backups."""
    import winreg
    if os.name != "nt":
        return []
    kernel32 = ctypes.windll.kernel32
    created = []
    tool_dir = Path(__file__).resolve().parent
    launch = tool_dir / LAUNCHER
    candidate_dirs = [Path(os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")),
                      Path(os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"))]
    for directory in candidate_dirs:
        if not str(directory) or not directory.is_dir():
            continue
        link = directory / ("Zed 汉化还原.lnk" if restore else "Zed 汉化补丁.lnk")
        if link.exists():
            continue
        command = 'cmd.exe /c ""{}" {} {} "'.format(launch, "--restore" if restore else "--apply", "--shortcut")
        try:
            import win32com.client  # Optional; not required for core patching.
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(link))
            shortcut.Targetpath = str(launch)
            shortcut.Arguments = "{} --shortcut".format("--restore" if restore else "--apply")
            shortcut.WorkingDirectory = str(tool_dir)
            shortcut.IconLocation = str(install_dir / "Zed.exe")
            shortcut.Description = "Zed 中英双语汉化" if not restore else "Zed 汉化还原"
            shortcut.save()
            created.append(str(link))
        except Exception:
            continue
    return created


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Zed 中英双语汉化一键补丁 / 还原工具（Windows）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="安装汉化补丁（自动检测 Zed）")
    mode.add_argument("--restore", action="store_true", help="还原到汉化前的 Zed")
    mode.add_argument("--status", action="store_true", help="查看补丁与 Zed 当前状态")
    parser.add_argument("--install-dir", help="Zed 安装目录（含主程序 Zed.exe）；默认自动检测")
    parser.add_argument("--backup-dir", help="备份目录；默认在安装目录下创建 {}".format(BACKUP_DIR_NAME))
    parser.add_argument("--patch-dir", help="补丁包目录；默认使用本工具所在目录")
    parser.add_argument("--discard", action="store_true", help="还原时确认覆盖你修改过的文件")
    parser.add_argument("--yes", action="store_true", help="不再交互确认")
    parser.add_argument("--shortcut", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    tool_dir = Path(__file__).resolve().parent
    try:
        patch_dir = Path(args.patch_dir).resolve() if args.patch_dir else tool_dir
        install_dir = Path(args.install_dir).resolve() if args.install_dir else discover_install_dir()
        backup_dir = Path(args.backup_dir).resolve() if args.backup_dir else install_dir / BACKUP_DIR_NAME

        if args.status:
            say("Zed 位置: {}".format(describe(install_dir) if (install_dir / 'Zed.exe').is_file() else install_dir))
            state = load_state(backup_dir) if backup_dir.exists() else None
            zed_exe = install_dir / "Zed.exe"
            current_hash = digest(zed_exe) if zed_exe.is_file() else ""
            original_hash = ""
            for entry in ((state or {}).get("files") or []):
                if str(entry.get("relative", "")).lower() == "zed.exe":
                    original_hash = str(entry.get("sha256") or "")
                    break
            if state and original_hash and current_hash.lower() == original_hash.lower():
                say("汉化状态: 未安装（检测到上次安装的备份，当前程序是原版；如确需回滚残留文件可运行 Restore.cmd）")
                say("备份目录: {}".format(backup_dir))
            elif state:
                say("汉化状态: 已安装（补丁 {}，安装时间 {}）".format(state.get("version"), state.get("created_utc")))
                say("备份目录: {}".format(backup_dir))
            else:
                say("汉化状态: 未安装")
            running = running_zed()
            say("Zed 进程: {}".format("正在运行" if running else "未运行"))
            return 0

        if args.restore:
            say("将从备份还原: {}".format(backup_dir))
            if not args.yes:
                input("按回车继续还原到原版 Zed（Ctrl+C 取消）…")
            restore(install_dir, backup_dir, discard=args.discard)
            return 0

        patch, payload, files = load_patch(patch_dir)
        verify_payload(payload, files)
        say("补丁版本: {}（基于 Zed {}，{}）".format(patch["version"], patch["base_version"], patch["base_commit"][:12]))
        say("Zed 位置: {}".format(describe(install_dir) if (install_dir / 'Zed.exe').is_file() else install_dir))
        say("备份位置: {}".format(backup_dir))
        if not args.yes:
            input("按回车继续安装汉化补丁（Ctrl+C 取消）…")
        apply_patch(install_dir, patch, payload, files, backup_dir)
        return 0
    except ToolError as error:
        say("\n[未能完成] " + str(error))
        return 2
    except KeyboardInterrupt:
        say("\n已取消。")
        return 130
    return 1


if __name__ == "__main__":
    prepare_console_encoding()
    sys.exit(main())
