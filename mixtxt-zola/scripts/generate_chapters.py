#!/usr/bin/env python3
"""AI 章节生成/修订 harness（Python 3.11+，零第三方依赖）。

规则见 docs/product/04-Zola方案详细设计.md §2.18。用法（OpenAI 兼容 API）：
  # 追加生成 3 章草稿（draft=true）
  LLM_API_KEY=sk-... LLM_MODEL=gpt-4o-mini \
    python3 scripts/generate_chapters.py --book sanguo-scifi --count 3 \
    --style "节奏明快，每章 3000 字左右"
  # 精确补位/重试：只处理指定章（生成）
  python3 scripts/generate_chapters.py --book sanguo-scifi --weights 5,7
  # 修订已有章节（保留 weight/slug/date/URL，只更新正文与 updatedAt）
  python3 scripts/generate_chapters.py --book sanguo-scifi --weights 5,7 --revise
  # --dry-run：只打印将处理的目标与 frontmatter 模板，不调用 LLM
"""
import argparse, datetime, json, os, pathlib, re, subprocess, sys, time, tomllib, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(".")
BOOKS = ROOT / "content" / "books"
LEDGERS = ROOT / "runs"                      # 每次运行的台账（可观测 + 精确重试依据）
ALLOWED_COPYRIGHT = ("public-domain", "authorized")
CN_TZ = ZoneInfo("Asia/Shanghai")            # 时间统一为北京时间；与运行机/CI 的本地时区（UTC）无关
SYSTEM_PROMPT = """你是小说章节作者。只输出章节正文（Markdown），
不要输出 frontmatter、不要解释、不要用代码块包裹正文。
要求：{style}
正文不超过 4000 字，结尾留钩子便于下一章衔接。"""


def now_cn() -> datetime.datetime:
    """当前时间（固定 Asia/Shanghai，UTC+8 无夏令时），避免 cron/沙箱的 UTC 漂移。"""
    return datetime.datetime.now(CN_TZ)


def read_frontmatter(path: pathlib.Path) -> tuple:
    """读一章的 (frontmatter dict, 正文字符串)。frontmatter 缺失/解析失败返回 ({}, 全文)。"""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^\+\+\+\s*\n(.*?)\n\+\+\+\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    try:
        return tomllib.loads(m.group(1)), m.group(2)
    except tomllib.TOMLDecodeError:
        return {}, m.group(2)


def toml_str(s: str) -> str:
    """把字符串转成合法 TOML 字符串字面量（转义反斜杠/引号/换行）。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') \
                 .replace("\n", "\\n") + '"'


def book_meta(book_dir: pathlib.Path) -> tuple:
    """读书 _index.md 的 (title, extra.copyrightStatus)；解析失败按 ("", "unknown") 处理（拒绝生成）。"""
    fm, _ = read_frontmatter(book_dir / "_index.md")
    return fm.get("title", ""), fm.get("extra", {}).get("copyrightStatus", "unknown")


def weight_files(book_dir: pathlib.Path) -> dict:
    """返回 {weight: 文件路径}，仅统计 frontmatter 里有合法 weight 的章节文件。"""
    out = {}
    for p in book_dir.glob("*.md"):
        if p.name == "_index.md":
            continue
        fm, _ = read_frontmatter(p)
        w = fm.get("weight")
        if isinstance(w, int) and w >= 0:
            out.setdefault(w, p)
    return out


def latest_published_seed(book_dir: pathlib.Path, limit: int = 300) -> str:
    """取本书「最新章节（weight 最大且非草稿）」的结尾作续写种子，保障多轮定时连载的前情连贯。"""
    best_w, best_body = -1, ""
    for w, p in weight_files(book_dir).items():
        fm, body = read_frontmatter(p)
        if fm.get("draft", False) is True:
            continue
        if w > best_w:
            best_w, best_body = w, body
    if not best_body:
        return ""
    return best_body.replace("\n", " ").strip()[-limit:]


def render_frontmatter(weight: int, title: str, desc: str, date, draft: bool,
                       model: str, ca_ymd: str) -> str:
    """按 §2.6 模板渲染 frontmatter；date 接受 datetime 或字符串，updatedAt 恒为今天。"""
    date_s = date.isoformat(timespec="seconds") if isinstance(date, datetime.datetime) else str(date)
    return (
        "+++\n"
        f"title = {toml_str(title)}\n"
        f"description = {toml_str(desc)}\n"
        f"weight = {weight}\n"
        f"draft = {'true' if draft else 'false'}\n"
        f"date = {date_s}\n"                       # 无引号 TOML datetime（官方建议不要用引号包日期）
        "[taxonomies]\n"
        'tags = ["AI改编"]\n'
        "[extra]\n"
        f'createdAt = "{ca_ymd}"\n'
        f'updatedAt = "{now_cn().date().isoformat()}"\n'
        "[extra.ai]\n"
        f'model = "{model}"\n'
        'prompt = "harness-cli"\n'
        "humanEdited = false\n"
        "+++\n"
    )


def llm_chat(system: str, user: str) -> str:
    key = os.environ.get("LLM_API_KEY")
    if not key:
        print("缺少 LLM_API_KEY 环境变量（OpenAI 兼容 API 的密钥）")
        sys.exit(1)
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    req = urllib.request.Request(
        f"{base.rstrip('/')}/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    for attempt in range(3):          # 429/5xx 退避重试，批量生成时抗偶发限流
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"LLM API 错误 {e.code}：{e.read().decode(errors='replace')[:200]}")
        except Exception as e:
            raise RuntimeError(f"LLM 调用失败：{e}")


def write_ledger(slug: str, mode: str, targets, ok, failed) -> None:
    """把一次运行追加进 runs/<slug>.jsonl，供无人值守排障与精确重试。"""
    try:
        LEDGERS.mkdir(exist_ok=True)
        rec = {"ts": now_cn().isoformat(timespec="seconds"), "mode": mode,
               "targets": sorted(targets), "ok": sorted(ok),
               "failed": [[w, e] for w, e in failed]}
        with (LEDGERS / f"{slug}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[warn] 写入 runs 台账失败（不影响生成）：{e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True, help="书 slug，对应 content/books/<slug>/")
    ap.add_argument("--count", type=int, default=None,
                    help="无 --weights 时：追加生成的章节数（从现有最大 weight+1 起）")
    ap.add_argument("--weights", default=None,
                    help="精确寻址的章号，逗号分隔，如 5,7,9；配合 --revise 修订、否则生成（重试补位用）")
    ap.add_argument("--revise", action="store_true",
                    help="修订已有章节（保留 weight/slug/date/URL，只更新正文与 updatedAt）")
    ap.add_argument("--context", default=None,
                    help="续写上下文种子；缺省自动取最新章节结尾约 300 字（仅生成时生效）")
    ap.add_argument("--title", help="书标题（默认读 _index.md 的 title）")
    ap.add_argument("--style", default="节奏明快，每章 3000 字左右",
                    help="风格要求，会拼进系统提示词")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--parallel", type=int, default=4,
                    help="并发生成数（默认 4，上百章时建议 8-16）")
    args = ap.parse_args()

    # 目标判定：--weights 显式寻址；否则按 --count 追加新章
    if args.weights is None and args.count is None:
        ap.error("需指定 --count 或 --weights")
    if args.revise and args.weights is None:
        ap.error("--revise 需配合 --weights 指定要修订的章")

    if not re.fullmatch(r"[a-z0-9-]+", args.book):
        print(f"书 slug 非法：{args.book}（只允许小写字母/数字/连字符）")
        return 1

    book_dir = BOOKS / args.book
    idx = book_dir / "_index.md"
    if not idx.exists():
        print(f"书不存在：{idx}（先建书目录与 _index.md）")
        return 1

    # fail-fast：版权未确认的书直接拒绝——不调用 LLM、不写文件
    book_title, cr = book_meta(book_dir)
    if cr not in ALLOWED_COPYRIGHT:
        print(f"书 {args.book} 的 copyrightStatus={cr}，不允许 AI 生成（需 public-domain/authorized）")
        return 1

    existing = weight_files(book_dir)
    if args.weights is not None:
        targets = [int(x.strip()) for x in args.weights.split(",") if x.strip()]
        if not targets:
            ap.error("--weights 为空")
        if args.revise:
            missing = [w for w in targets if w not in existing]
            if missing:
                print(f"--revise 目标章不存在：{missing}")
                return 1
            mode = "revise"
        else:
            collide = [w for w in targets if w in existing]
            if collide:
                print(f"--weights 指到的章已存在（如需修订请加 --revise）：{collide}")
                return 1
            mode = "generate"
    else:
        start = max(existing, default=0) + 1
        targets = list(range(start, start + args.count))
        mode = "generate"

    if args.dry_run:
        print(f"[dry-run] mode={mode} book={args.book} targets={targets}")
        if mode == "revise":
            fm, _ = read_frontmatter(existing[targets[0]])
            print(f"[dry-run] 以原 frontmatter 为基底修订 {existing[targets[0]].name}"
                  f"（保留 weight={targets[0]}/draft={fm.get('draft')}）")
        else:
            print(render_frontmatter(targets[0], "示例章标题", "示例摘要",
                                     now_cn(), True,
                                     os.environ.get("LLM_MODEL", "gpt-4o-mini"),
                                     now_cn().date().isoformat()))
        return 0

    seed = args.context if args.context is not None else latest_published_seed(book_dir)
    model_default = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    book_name = args.title or book_title or args.book

    def gen_one(w: int) -> tuple:
        """处理一章；返回 (weight, None) 成功或 (weight, 错误信息) 失败——单章失败不拖垮整批。"""
        try:
            if mode == "revise":
                path = existing[w]
                fm, old_body = read_frontmatter(path)
                ctx = old_body.replace("\n", " ").strip()[:800]   # 供修订参考的现有正文
                user = (f"请精修《{book_name}》第 {w} 章的正文，保持情节/人物/设定连贯，"
                        f"不要变换叙事视角。\n\n=== 现有正文（供修订）===\n{ctx}\n===")
                body = llm_chat(SYSTEM_PROMPT.format(style=args.style), user)
                title = fm.get("title") or f"第 {w} 章"
                first = re.sub(r"^#+\s*", "", body.split("\n")[0])
                desc = (first[:60] or title)
                ca = (fm.get("extra", {}).get("createdAt")
                      or now_cn().date().isoformat())
                draft = bool(fm.get("draft", False))
                date_val = fm.get("date", now_cn())
                model = (fm.get("extra", {}).get("ai", {}).get("model") or model_default)
                path.write_text(
                    render_frontmatter(w, title, desc, date_val, draft, model, ca)
                    + "\n" + body, encoding="utf-8")
            else:
                user = f"这是《{book_name}》的第 {w} 章，请写正文。"
                if seed:
                    user += f"\n\n=== 前情（上一章结尾，供衔接）===\n{seed}\n==="
                body = llm_chat(SYSTEM_PROMPT.format(style=args.style), user)
                title = f"第 {w} 章"          # 人工修订时可改成真实标题
                first = re.sub(r"^#+\s*", "", body.split("\n")[0])   # 去掉首行 Markdown 标题标记
                desc = (first[:60] or f"第 {w} 章")
                (book_dir / f"ch{w:03d}.md").write_text(
                    render_frontmatter(w, title, desc, now_cn(), True,
                                       model_default, now_cn().date().isoformat())
                    + "\n" + body, encoding="utf-8")
            return w, None
        except Exception as e:
            return w, str(e)              # 单章失败：记录并继续其余章节

    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        futures = [pool.submit(gen_one, w) for w in targets]
        ok, failed = [], []
        for fut in as_completed(futures):
            w, err = fut.result()
            if err:
                failed.append((w, err))
                print(f"[{w:03d}] 失败：{err}")
            else:
                ok.append(w)
                print(f"[{w:03d}] {'修订' if mode == 'revise' else '完成'}")

    write_ledger(args.book, mode, targets, ok, failed)

    if failed:
        print(f"有 {len(failed)} 章失败（未写文件）："
              f"{', '.join(f'{w:03d}' for w, _ in failed)}")
        print(f"精确重试：python3 scripts/generate_chapters.py --book {args.book}"
              f" --weights {','.join(str(w) for w, _ in failed)}"
              + (" --revise" if mode == "revise" else ""))
        return 1

    print("生成完成，运行校验：")
    return subprocess.run([sys.executable, "scripts/validate_content.py"]).returncode


if __name__ == "__main__":
    sys.exit(main())