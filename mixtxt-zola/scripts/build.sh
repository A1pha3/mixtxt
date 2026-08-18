#!/usr/bin/env bash
# 校验 + 链接检查 + 构建 + 索引的唯一构建入口。
# Cloudflare Pages 与 GitHub Actions 都调用本文件，保证内容门禁永不缺席。
# 规则见 docs/product/04-Zola方案详细设计.md §2.12。
set -euo pipefail
python3 scripts/validate_content.py   # 失败则中断，旧版本保持在线
zola check --skip-external-links      # 内部死链门禁（不发 HTTP，构建环境稳定；外部链接本地手动全量查）
zola build "$@"                       # 透传参数，如 --base-url "$CF_PAGES_URL"
npx pagefind@1.5.2 --site public      # 生成搜索索引（固定版本；零 Node 则用 python3 -m pagefind，见 §2.3）