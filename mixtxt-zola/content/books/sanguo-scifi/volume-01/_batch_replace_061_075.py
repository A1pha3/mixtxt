#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ch061-075 名词层去侵权批量替换（第一层）。
映射依据 docs/product/06-星汉三国-原创设定手册.md。
注意：本脚本只做名词/专名替换，机制层语义改写由后续 Edit 完成。
"""
import os
import re

BASE = "/Volumes/mini_matrix/github/a1pha3/web/mixtxt/mixtxt-zola/content/books/sanguo-scifi/volume-01"
FILES = [f"chapter-0{n}.md" for n in range(61, 76)]

# 顺序敏感：长词优先
REPLACES = [
    # 城市/枢纽
    ("玄械城", "璇枢"),
    ("沉心井", "归墟井"),
    ("问手台", "解契台"),
    ("满城之桥", "连星道"),
    # 七片（认收夺守予归己）→ 七曜契引信体系
    ("认片", "解契引"),
    ("归片", "续契引"),
    ("守片", "守契引"),
    ("予片", "予契引"),
    ("夺片", "夺契引"),
    ("收片", "收契引"),
    ("己片", "归契引"),
    ("七片", "七曜契"),
    ("七片归一", "七契重续"),
    # 人物/职业
    ("甲士", "契士"),
    ("调甲师", "调契师"),
    ("活甲", "契甲"),
    # 认主/收而不予
    ("认主", "解契认契"),
    ("收而不予", "断契独握"),
    ("认肯不认收", "履约不认独握"),
    ("认肯沉", "履约沉印"),
    ("认肯", "履约肯"),
    # 满城 → 星垣（语境无害化，后续机制层再精修）
    ("满城之肯", "星垣之契"),
    ("满城的人", "星垣的众"),
    ("满城", "星垣"),
    ("焐稳满城", "焐稳星垣"),
    ("认了路", "定了路"),
    ("认予守", "解予守"),
    ("肯沉", "契沉"),
    # 其他残留
    ("认心不认令", "验心不验令"),
    ("甲认人", "契应人"),
    ("龙城", "璇枢"),
    ("师士", "契士"),
    ("光甲", "契甲"),
    ("脑控", "契控"),
]

def process(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    before = {k: text.count(k) for k, _ in REPLACES if text.count(k) > 0}
    for old, new in REPLACES:
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    after = sum(text.count(new) for _, new in REPLACES)
    return before, after

for fn in FILES:
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        print(f"[SKIP] {fn} 不存在")
        continue
    before, after = process(p)
    total_before = sum(before.values())
    print(f"[OK] {fn}: 替换前命中 {total_before} 处 -> 新词出现 {after} 处")
    if before:
        detail = ", ".join(f"{k}×{v}" for k, v in sorted(before.items(), key=lambda x:-x[1]))
        print(f"      {detail}")
