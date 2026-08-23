#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ch076-090 名词层批量替换：龙城/玄械城体系 -> 星汉之契体系"""
import os

VOL = os.path.dirname(os.path.abspath(__file__))
FILES = [f"chapter-0{n}.md" for n in range(76, 91)]

# 顺序很重要：先长后短，先组合词后单字，避免部分匹配
REPL = [
    # 组合专有名词（必须最先）
    ("认己归城", "解契续契"),
    ("满城之桥", "连星道"),
    ("满城之肯", "星垣之肯"),
    ("焐稳满城", "焐稳星垣"),
    ("认心不认令", "验心不验令"),
    ("认肯沉", "履约沉印"),
    ("肯沉归城", "契约沉归"),
    ("肯沉", "契约沉"),
    ("问手台", "解契台"),
    ("沉心井", "归墟井"),
    ("收而不予", "断契独握"),
    ("玄械城之心", "契核"),
    ("玄械城", "璇枢"),
    ("七片归一", "七曜契重续"),
    ("七片", "七曜契"),
    ("认片", "解契引"),
    ("归片", "续契引"),
    ("守片", "守契引"),
    ("予片", "予契引"),
    ("认予守", "解予守"),
    ("认了路", "定了路"),
    ("甲认人", "甲应契"),
    ("甲士", "契士"),
    ("调甲", "调契"),
    ("活甲", "契甲"),
    ("认主", "解契认契"),
    ("龙城", "璇枢"),
    ("方想", ""),
    ("师士", "契士"),
    ("光甲", "契甲"),
    ("脑控", "契控"),
    # 满城 放在七片/肯沉之后，避免误伤组合词
    ("满城", "星垣"),
    # 认肯 单独处理（避免与认主/认片重叠）
    ("认肯", "履约肯"),
]

def apply(text):
    for old, new in REPL:
        if old in text:
            text = text.replace(old, new)
    return text

total = 0
for fn in FILES:
    p = os.path.join(VOL, fn)
    if not os.path.exists(p):
        print(f"[SKIP] {fn} 不存在")
        continue
    with open(p, encoding="utf-8") as f:
        t = f.read()
    before = len(t)
    t2 = apply(t)
    cnt = before - len(t2)  # 粗略命中计数（替换后长度变化）
    # 精确统计替换次数
    hits = 0
    for old, new in REPL:
        if old:
            hits += t.count(old)
    with open(p, "w", encoding="utf-8") as f:
        f.write(t2)
    total += hits
    print(f"[OK] {fn}: 名词命中约 {hits} 处")

print(f"\n合计名词层命中约 {total} 处")
