"""Download and install Zola static site generator."""
import sys
import shutil
import tarfile
import platform
from pathlib import Path
from urllib.request import urlopen, Request

INSTALL_DIR = Path.home() / ".local" / "bin"
VERSION = "v0.19.2"
ARCH_MAP = {
    "x86_64": "x86_64",
    "arm64": "aarch64",
    "aarch64": "aarch64",
}
OS_MAP = {
    "darwin": "apple-darwin",
    "linux": "unknown-linux-gnu",
}


def main():
    machine = ARCH_MAP[platform.machine()]
    system = OS_MAP[platform.system().lower()]
    archive = f"zola-{VERSION}-{machine}-{system}.tar.gz"
    url = f"https://github.com/getzola/zola/releases/download/{VERSION}/{archive}"

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    target = INSTALL_DIR / "zola"

    print(f"Downloading {url} ...")
    req = Request(url, headers={"User-Agent": "python/3"})
    data = urlopen(req, timeout=120).read()

    tar_path = Path("/tmp") / archive
    tar_path.write_bytes(data)
    print(f"Extracting {tar_path} ...")
    with tarfile.open(tar_path) as tar:
        tar.extract("zola", path=INSTALL_DIR)
    target.chmod(0o755)
    tar_path.unlink()

    print(f"Installed to {target}")
    print(f"Run: export PATH=\"$HOME/.local/bin:$PATH\"")


if __name__ == "__main__":
    main()