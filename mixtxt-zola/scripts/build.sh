#!/usr/bin/env bash
# 校验 + 链接检查 + 构建 + 索引的唯一构建入口。
# Cloudflare Pages 与 GitHub Actions 都调用本文件，保证内容门禁永不缺席。
# 规则见 docs/product/04-Zola方案详细设计.md §2.12。
set -euo pipefail
cd "$(dirname "$0")/.."               # 自定位仓库根，与调用方 cwd 无关（CI/本地均可）
python3 scripts/validate_content.py   # 失败则中断，旧版本保持在线
zola build "$@"                       # 透传参数，如 --base-url "$CF_PAGES_URL"（含内部死链检查）
if command -v npx &>/dev/null; then
  npx -y pagefind@1.5.2 --site public
elif command -v python3 &>/dev/null; then
  # 无 Node.js 环境时的回退方案：pip install 指定版本
  python3 -m pagefind --site public 2>/dev/null ||
  (pip3 install -q pagefind==1.5.2 && python3 -m pagefind --site public)
else
  echo "warning: pagefind not found (npx nor python3 -m pagefind); search index not built"
fi