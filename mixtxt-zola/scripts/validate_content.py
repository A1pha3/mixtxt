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
import tomllib

ROOT = pathlib.Path(".")
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
books = {}
for book_dir in (content / "books").iterdir():
    if book_dir.is_dir():
        books[book_dir.name] = book_dir

for book_dir in books.values():
    idx = book_dir / "_index.md"
    if not idx.exists():
        errors.append(f"{book_dir}: 缺少 _index.md")
        continue
    fm = parse_frontmatter(idx)
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

    # 章节校验（单一真源：weight 决定章号/排序/显示；文件名只是 URL slug，不承载章号；书归属由目录决定）
    seen_weight = set()
    seen_slug = set()
    for ch in book_dir.glob("*.md"):
        if ch.name == "_index.md":
            continue
        fm = parse_frontmatter(ch)
        extra = fm.get("extra", {})
        weight = fm.get("weight")
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
        # 日期（feed/sitemap 需要）
        if "date" in fm:
            check_date(ch, fm["date"])
        # createdAt 不晚于 updatedAt（共享模型 doc 03 §2.14；YYYY-MM-DD 字典序即时间序）
        ca, ua = extra.get("createdAt"), extra.get("updatedAt")
        if ca and ua and ca > ua:
            errors.append(f"{ch}: createdAt({ca}) 晚于 updatedAt({ua})")
        # 已发布章节（draft=false 或缺省）必须挂在可公开的书下；草稿（draft=true）不受此限
        is_published = (fm.get("draft", False) is False)
        if is_published and cr in ("unknown", "private-draft"):
            errors.append(f"{ch}: 已发布章节但所属书 copyrightStatus={cr} 不允许公开构建")

if errors:
    print("内容校验失败：")
    print("\n".join(f"- {e}" for e in errors))
    sys.exit(1)
print("content validation passed")