"""Build self-contained native release assets on the current operating system."""
from pathlib import Path
import hashlib
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
OUTPUT = ROOT / "release"
ARCH = {"AMD64": "x86_64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())


def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def main():
    OUTPUT.mkdir(exist_ok=True)
    name = "Browser Selector" if sys.platform == "darwin" else "browser-selector"
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--noupx",
            "--name", name, "--specpath", ROOT / "build", "--paths", ROOT,
            "--hidden-import", "ctypes",
            "--add-data", f"{ROOT / 'scripts/register_linux.py'}:registration",
            "--add-data", f"{ROOT / 'scripts/register_windows.py'}:registration"]
    if sys.platform in ("win32", "darwin"):
        args += ["--windowed"]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "local.browser-selector"]
    run(*args, ROOT / "scripts/desktop_entry.py")
    bundle = ROOT / "dist" / name
    if sys.platform == "darwin":
        app = ROOT / "dist/Browser Selector.app"
        info = app / "Contents/Info.plist"
        content = plistlib.loads(info.read_bytes())
        content.update(CFBundleURLTypes=[{"CFBundleURLName": "Web links", "CFBundleTypeRole": "Viewer",
                                        "CFBundleURLSchemes": ["http", "https"]}],
                       CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION, NSHighResolutionCapable=True)
        info.write_bytes(plistlib.dumps(content))
        run("codesign", "--force", "--deep", "--sign", "-", app)
        run(app / "Contents/MacOS/Browser Selector", "--self-test")
        with tempfile.TemporaryDirectory(prefix="browser-selector-dmg-") as temp:
            stage = Path(temp)
            shutil.copytree(app, stage / app.name, symlinks=True)
            (stage / "Applications").symlink_to("/Applications")
            run("hdiutil", "create", "-volname", "Browser Selector", "-srcfolder", stage,
                "-ov", "-format", "UDZO", OUTPUT / f"browser-selector-{VERSION}-macos-{ARCH}.dmg")
    elif sys.platform == "win32":
        run(bundle / "browser-selector.exe", "--self-test")
        zip_path = OUTPUT / f"browser-selector-{VERSION}-windows-{ARCH}-portable.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in bundle.rglob("*"):
                if file.is_file():
                    archive.write(file, Path("browser-selector") / file.relative_to(bundle))
        compiler = shutil.which("ISCC") or str(Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6/ISCC.exe")
        run(compiler, f"/DAppVersion={VERSION}", f"/DAppArch={ARCH}", ROOT / "packaging/windows.iss")
    else:
        run(bundle / "browser-selector", "--version")
        run(bundle / "browser-selector", "--self-test")
        archive = OUTPUT / f"browser-selector-{VERSION}-linux-{ARCH}.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            output.add(bundle, arcname="browser-selector")
        with tempfile.TemporaryDirectory(prefix="browser-selector-deb-") as temp:
            stage = Path(temp)
            destination = stage / "opt/browser-selector"
            shutil.copytree(bundle, destination, symlinks=True)
            (stage / "usr/bin").mkdir(parents=True)
            (stage / "usr/bin/browser-selector").symlink_to("/opt/browser-selector/browser-selector")
            desktop = stage / "usr/share/applications/browser-selector.desktop"
            desktop.parent.mkdir(parents=True)
            desktop.write_text("[Desktop Entry]\nType=Application\nName=Browser Selector\n"
                               "Comment=Choose a browser and profile for web links\n"
                               "Exec=/opt/browser-selector/browser-selector %U\nIcon=web-browser\nTerminal=false\n"
                               "Categories=Network;WebBrowser;\nMimeType=x-scheme-handler/http;x-scheme-handler/https;\n")
            control = stage / "DEBIAN/control"
            control.parent.mkdir()
            deb_arch = {"x86_64": "amd64", "arm64": "arm64"}[ARCH]
            libc_version = platform.libc_ver()[1] or "2.35"
            control.write_text(f"Package: browser-selector\nVersion: {VERSION}\nArchitecture: {deb_arch}\n"
                               "Maintainer: HariTP <harigvnd2003@gmail.com>\nSection: web\nPriority: optional\n"
                               f"Depends: libc6 (>= {libc_version}), libglib2.0-0, libgl1, libegl1, libdbus-1-3, libfontconfig1, libxkbcommon0, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-xinerama0, xdg-utils\n"
                               "Description: Choose a browser and profile for external web links\n")
            run("dpkg-deb", "--root-owner-group", "--build", stage,
                OUTPUT / f"browser-selector-{VERSION}-linux-{deb_arch}.deb")
    assets = sorted(p for p in OUTPUT.iterdir() if p.is_file() and not p.name.endswith(".sha256"))
    checksum = OUTPUT / f"SHA256SUMS-{sys.platform}-{ARCH}.sha256"
    lines = []
    for asset in assets:
        with asset.open("rb") as source:
            lines.append(f"{hashlib.file_digest(source, 'sha256').hexdigest()}  {asset.name}\n")
    checksum.write_text("".join(lines))
    print(f"Release assets: {OUTPUT}")


if __name__ == "__main__":
    main()
