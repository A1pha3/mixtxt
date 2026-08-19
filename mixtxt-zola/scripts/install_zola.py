"""Download and install Zola static site generator (macOS / Linux)."""
import sys
import shutil
import tarfile
import platform
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

INSTALL_DIR = Path.home() / ".local" / "bin"
# 与 docs/product/04-Zola方案详细设计.md §2.11 的 Cloudflare ZOLA_VERSION 保持一致
# （config.toml 的 [markdown.highlighting] 需 Zola 0.22+，2026-08-12 官方稳定版 0.23.3）
VERSION = "v0.23.3"
ARCH_MAP = {
    "x86_64": "x86_64",
    "arm64": "aarch64",
    "aarch64": "aarch64",
}
OS_MAP = {
    "darwin": "apple-darwin",
    "linux": "unknown-linux-gnu",
}


def main() -> int:
    machine = platform.machine()
    system = platform.system().lower()
    if machine not in ARCH_MAP:
        print(f"不支持的架构：{machine}（仅支持 x86_64 / arm64）")
        return 1
    if system not in OS_MAP:
        print(f"不支持的操作系统：{platform.system()}（仅支持 macOS / Linux）")
        return 1
    archive = f"zola-{VERSION}-{ARCH_MAP[machine]}-{OS_MAP[system]}.tar.gz"
    url = f"https://github.com/getzola/zola/releases/download/{VERSION}/{archive}"

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    target = INSTALL_DIR / "zola"
    tar_path = Path("/tmp") / archive

    try:
        print(f"Downloading {url} ...")
        req = Request(url, headers={"User-Agent": "python/3"})
        with urlopen(req, timeout=120) as r:
            data = r.read()
        tar_path.write_bytes(data)
        print(f"Extracting {tar_path} ...")
        with tarfile.open(tar_path) as tar:
            tar.extract("zola", path=INSTALL_DIR)
        target.chmod(0o755)
    except (HTTPError, URLError) as e:
        print(f"下载失败（{e}）：{url}，请检查网络或版本号")
        return 1
    except (tarfile.TarError, OSError) as e:
        print(f"解压失败：{e}")
        return 1
    finally:
        tar_path.unlink(missing_ok=True)

    print(f"Installed to {target}")
    print("Run: export PATH=\"$HOME/.local/bin:$PATH\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
