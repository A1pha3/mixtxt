#!/usr/bin/env python3
"""Zola 内容构建前校验（Python 3.11+，内置 tomllib，零第三方依赖）。

规则见 docs/product/04-Zola方案详细设计.md §2.12。单一真源：
`weight` 决定章号/排序/显示；文件名（slug）只作 URL、不承载章号；
书归属由所在目录唯一决定。任一校验失败打印清单并以退出码 1 中断构建
（旧版本保持在线）。
"""
import datetime
import pathlib
import re
import sys
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # Python < 3.11 回退

ROOT = pathlib.Path(__file__).resolve().parent.parent   # 脚本自定位仓库根，与调用方 cwd 无关
content = ROOT / "content"
errors = []
slug_re = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_frontmatter(path: pathlib.Path) -> dict:
    """读 `+++` 包裹的 TOML frontmatter；缺失或解析失败记入 errors 并返回空 dict。"""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^\+\+\+\s*\n(.*?)\n\+\+\+", text, re.S)
    if not m:
        errors.append(f"{path}: frontmatter 缺失或未闭合（须以 +++ 开头、以独占一行的 +++ 结尾）")
        return {}
    try:
        return tomllib.loads(m.group(1))
    except tomllib.TOMLDecodeError as e:
        errors.append(f"{path}: frontmatter TOML 解析失败: {e}")
        return {}


def check_date(path: pathlib.Path, value) -> None:
    """date 接受 TOML datetime 或 YYYY-MM-DD / RFC3339 字符串；官方建议不要用引号包 RFC3339。"""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return
    if isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:?\d{2}|Z))?", value):
        return
    errors.append(f"{path}: date 格式非法（应为 YYYY-MM-DD 或 RFC3339）：{value!r}")


# 收集所有书 section 的 slug（目录名）
books_dir = content / "books"
books = {}
if not books_dir.exists():
    errors.append(f"content/books 目录不存在（{books_dir}）：请在 Zola 站点根运行校验，或先按 §2.4 初始化结构")
else:
    for book_dir in books_dir.iterdir():
        if book_dir.is_dir():
            books[book_dir.name] = book_dir

for book_dir in books.values():
    idx = book_dir / "_index.md"
    if not idx.exists():
        errors.append(f"{book_dir}: 缺少 _index.md")
        continue
    fm = parse_frontmatter(idx)
    # 书 section 必须显式指定 book.html 模板，否则 Zola 回退 section.html（丢失书页布局）
    if fm.get("template") != "book.html":
        errors.append(f"{book_dir.name}: 缺少 template = \"book.html\"（否则书页回退默认 section 模板）")
    # 排序方式必须为 weight，否则章节顺序由文件名决定而非 weight
    if fm.get("sort_by") != "weight":
        errors.append(f"{book_dir.name}: sort_by 须为 \"weight\"（否则章节顺序由文件名决定）")
    extra = fm.get("extra", {})
    vis = extra.get("visibility", "public")
    cr = extra.get("copyrightStatus", "unknown")
    section_draft = fm.get("draft", False)
    # 硬约束：unknown / private-draft 不允许公开构建
    if cr in ("unknown", "private-draft"):
        errors.append(f"{book_dir.name}: copyrightStatus={cr} 不允许公开构建")
    if cr == "private-draft" and vis != "hidden":
        errors.append(f"{book_dir.name}: private-draft 时 visibility 必须为 hidden")
    # hidden 书 = section draft=true（否则整本书会被 Zola 构建公开访问，模板过滤救不了）
    if vis == "hidden" and section_draft is not True:
        errors.append(f"{book_dir.name}: visibility=hidden 的书必须设 section draft=true")
    # 封面存在性
    cover = extra.get("cover")
    if cover and not (ROOT / "static" / cover.lstrip("/")).exists():
        errors.append(f"{book_dir.name}: 封面缺失 {cover}")
    # 书 section 必需字段（模板渲染依赖）
    for field in ("original", "status", "copyrightStatus", "startedAt", "updatedAt"):
        if field not in extra:
            errors.append(f"{book_dir.name}: extra.{field} 缺失（模板渲染需要）")

    # 章节校验（单一真源：weight 决定章号/排序/显示；文件名只是 URL slug，不承载章号；书归属由目录决定）
    seen_weight = set()
    seen_slug = set()
    for ch in book_dir.glob("*.md"):
        if ch.name == "_index.md":
            continue
        fm = parse_frontmatter(ch)
        ch_extra = fm.get("extra", {})
        weight = fm.get("weight")
        # 章节页必须显式指定 chapter.html 模板，否则 Zola 回退到 page.html（丢失章号/导航/搜索标记）
        if fm.get("template") != "chapter.html":
            errors.append(f"{ch.name}: 缺少 template = \"chapter.html\"（否则章节页回退 page.html 模板）")
        # 文件名（slug）只作 URL，须合法且书内唯一
        if not slug_re.fullmatch(ch.stem):
            errors.append(f"{ch.name}: 文件名（slug）不合法（仅小写字母/数字/连字符，且书内唯一）")
        else:
            if ch.stem in seen_slug:
                errors.append(f"{ch.name}: 同书重复 slug {ch.stem}")
            seen_slug.add(ch.stem)
        # weight 是章号/排序/显示的唯一真源：须为非负整数且书内唯一
        if not isinstance(weight, int) or weight < 0:
            errors.append(f"{ch}: 缺少 weight 或非非负整数（排序/章号的唯一真源，须显式声明）")
        else:
            if weight in seen_weight:
                errors.append(f"{ch}: 同书重复 weight {weight}")
            seen_weight.add(weight)
            # 显示副本：Zola 的 page 上下文不暴露顶层 weight，须镜像到 extra.weight 供模板渲染；两层须一致
            extra_w = ch_extra.get("weight")
            if extra_w is None:
                errors.append(f"{ch}: extra.weight 缺失（Zola 不暴露 page.weight，须镜像到 extra 供模板显示章号）")
            elif extra_w != weight:
                errors.append(f"{ch}: extra.weight({extra_w}) 与顶层 weight({weight}) 不一致")
        # 日期（feed/sitemap 需要）
        if "date" in fm:
            check_date(ch, fm["date"])
        # createdAt 不晚于 updatedAt（共享模型 doc 03 §2.14；YYYY-MM-DD 字典序即时间序）
        ca, ua = ch_extra.get("createdAt"), ch_extra.get("updatedAt")
        if ca and ua and ca > ua:
            errors.append(f"{ch}: createdAt({ca}) 晚于 updatedAt({ua})")
        # updatedAt 不早于 发布日 date（修订/发布后不会超前于原文日期）
        if ua and "date" in fm:
            dv = fm["date"]
            d_key = dv.date().isoformat() if hasattr(dv, "date") else str(dv)[:10]
            if d_key > ua:
                errors.append(f"{ch}: 发布日 date({d_key}) 晚于 updatedAt({ua})——修订后需重刷 updatedAt")
        # aliases（改名防死链，§2.8）：必须是字符串数组、每项非空且无空白
        ali = fm.get("aliases")
        if ali is not None:
            if not isinstance(ali, list) or not all(isinstance(a, str) and a.strip() and " " not in a for a in ali):
                errors.append(f"{ch}: aliases 须为非空字符串数组（每项为旧 URL，不能含空白）")
        # 已发布章节（draft=false 或缺省）必须挂在可公开的书下；草稿（draft=true）不受此限
        is_published = (fm.get("draft", False) is False)
        if is_published and cr in ("unknown", "private-draft"):
            errors.append(f"{ch}: 已发布章节但所属书 copyrightStatus={cr} 不允许公开构建")

if errors:
    print("内容校验失败：")
    print("\n".join(f"- {e}" for e in errors))
    sys.exit(1)
print("content validation passed")