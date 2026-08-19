# Zola 方案详细设计（场景 A — AI 改编小说网，Rust 静态生成器）

> 文档类型：单作者 AI 改编小说静态站 — Zola 专属详细设计
>
> 适用场景：单作者、Markdown（TOML frontmatter）正本、无数据库、读者只读、Git 版本管理、免费公开阅读。**这是 Hugo + Git 路线的 Rust 平替。**
>
> 本方案对应选型结论（见 [01-需求与方案选型.md](./01-需求与方案选型.md) 第〇节「三个不变量」与第二节）：Zola 是 Hugo 的 1:1 替代，单文件二进制、零依赖、模板用 Tera（Jinja2 风格，比 Go template 好写）。
>
> **共享基础设计（内容模型 / 章节导航 / 版本管理 / 部署限制 / 版权边界 / 草稿过滤 / 搜索）全部见 [03-轻量静态站架构设计.md](./03-轻量静态站架构设计.md) 第一部分 1.1–1.9，本文不再重复，只写 Zola 与共享模型的差异和完整实现。**
>
> 原始需求：[AI改编小说网需求.md](./archive/AI改编小说网需求.md)
>
> 文档版本：1.12 ｜ 创建：2026-08-17 ｜ 最后更新：2026-08-19
>
> 1.12 变更（对抗性审查第 11 轮，简洁性收敛）：① **变更历史压缩**——1.1~1.8 详细记录移出至 [CHANGELOG-04-Zola方案详细设计.md](./CHANGELOG-04-Zola方案详细设计.md)，文头只保留最近 3 版；② **§2.13 精简**——移除与 §2.18 重叠的批量发布命令和定时自动化实现细节，统一引用 §2.18 作为唯一实现参考。
>
> 1.11 变更（对抗性审查第 10 轮，P0-P2 落地）：① §2.5 高亮配置随 Zola 0.22 迁移——`[markdown]` 的 `highlight_code`/`highlight_theme` 改为 `[markdown.highlighting] theme`（旧键在锁定的 0.23.3 下已失效，会构建报错/高亮失效）；② 全文"内置 Elasticlunr"事实更新为"内置搜索（Fuse.js）"（Zola 0.19 起内置搜索已换 Fuse.js，结论"需 Pagefind"不变；§2.1/§2.3/§2.5/§2.9/§2.16 同步）；③ `generate_chapters.py --revise` 保留 `aliases`（原重建式会丢防死链元数据），并明示"修订已发布章直接生效"语义；④ `--weights`/`--publish` 非法输入改为友好报错（原裸 ValueError traceback）；⑤ build.sh/validate/generate 自定位仓库根（原依赖调用方 cwd），validate 对缺失 content/books 友好报错；⑥ §2.4 目录树缩进修复、§2.7 标注"其余模板以本文档为唯一真源"。
>
> 1.10 变更（定时自动化端到端，判断 F1+F2+G+H1 落地）：① **§2.13 新增"定时自动化接线"小节**——四个原子步（生成/修订 → 攒稿 → `--publish` 一次性翻发 → validate 通过才 `git pull --rebase`+commit+push），明确**节流铁律（草稿攒够批量才翻发、多 commit 少 build，压到每月 30–90 构建）**、**串行+幂等（同刻只跑一个任务、push 前 rebase、无改动不 commit，避撞免费层单并发构建）**、**台账自愈（读 `runs/` 失败记录用 `--weights` 补位重试）**；② **G：validate 补两条**——`updatedAt ≥ 发布日 date`、`aliases` 须为不含空白的非空字符串数组（§2.12 同步）；③ **H1：翻发收敛进 harness 的 `--publish`**——替代 §2.13 手写 `sed`/shell 批量改 `draft`，只做 `draft=true→false` 手术式替换（保留 title/description/`aliases`/`ai`），不能与 `--count/--weights/--revise` 同用，§2.18 三种模式补齐。
>
> 1.9 变更（定时自动化适配，判断 A+B+C 落地）：harness `generate_chapters.py` 升级为**生成/修订双模式 + 精确寻址 + 前情上下文 + 确定时区 + 运行台账**——① 新增 `--revise`（改已有章，保留 `weight`/slug/`date`/URL，只重写正文并更新 `updatedAt`），补上"修改小说"的自动化闭环；② 新增 `--weights 5,7` 精确寻址，失败可 `--weights` 精确补位重试，不再有"中段失败章被永久跳过留空档"；③ 新增 `--context`（缺省 `latest_published_seed()` 取最新章节结尾约 300 字作续写前情种子），多轮定时连载不脱节；④ 时间统一 `ZoneInfo("Asia/Shanghai")`，与运行机/CI 的 UTC 无关，杜绝 `date`/RSS 漂移；⑤ 每次运行追加 `runs/<book>.jsonl` 台账（可观测 + 精确重试依据），失败时打印可复制重试命令。同步 §2.18 结构要点与 §2.4 树（新增 `runs/`）、`render_frontmatter`（`date` 保留原值、`updatedAt` 恒今天）。validate 的 `updatedAt≥date`、`aliases` 等补充留待后续（判断 E，本期不做）。

---

## 第一部分：Zola 与共享基础设计的字段映射

Zola 用「书 = section（目录 + `_index.md`）、章节 = page（`.md` 文件）」天然映射嵌套结构，因此共享模型里「books 用 JSON、chapters 用 MD」的拆分在 Zola 里被**合并**为一个目录树。字段映射如下：

| 共享模型（doc 03 §1.2） | Zola 实现 | 说明 |
|--------------------------|-----------|------|
| books（JSON 元数据） | 书目录下的 `_index.md` frontmatter | `title`/`description` 为顶层；`status`/`visibility`/`cover`/`copyrightStatus` 等自定义字段放 `[extra]` |
| chapters `status: published` | 章节 `draft = false` | Zola 无枚举；**已发布 = `draft=false`，其余（draft/review/archived）= `draft=true`（不参与构建）** |
| chapters `chapterNo: "002"` | 章节 `weight = 2`（整数升序） | Zola 用 `weight` 排序，前导零无必要；显示章号由模板 `"%03d"\|format(weight)` 派生（§2.7） |
| chapters `summary` | 章节 `description`（顶层） | Zola 标准字段，自动用于 meta/feed |
| `visibility` / `copyrightStatus` | `extra.visibility` / `extra.copyrightStatus` | **`visibility=hidden` 的书 → 书 section `draft = true`**（Zola 官方：被 draft 的 section 其子孙页面一律不处理，见 §2.6 书示例）；构建期校验门控（见 §2.12） |
| `tags` | `[taxonomies] tags = [...]` | 在 config.toml 声明 taxonomy |
| releases（MD） | `content/releases/` section | 同结构 |
| prompts（MD，作者侧） | **仓库根 `prompts/`（在 `content/` 之外）** | 不是站点内容，不进构建/导航/搜索；AI 工作流直接读文件（见 §2.4/§2.13） |
| `seo`（共享模型可选字段） | **不逐章存储，由模板推导** | title/description block 已在 base.html/chapter.html 实现；存了反而造成"改 title 忘改 seo.title"的漂移 |
| chapters `wordCount` | **不存储，用 Zola 原生 `page.word_count`** | zh/ja 按字符计（`page.reading_time` 同是内建），免手工维护、不会随改文过期 |
| site 配置（JSON） | `config.toml` + `config.extra` | 全站标题/描述/作者/GitHub 链接 |

**导航铁律不变**：章节导航不跨书，按 `weight` 升序算上一篇/下一篇（见 §2.8）。**草稿铁律不变**：`draft=true` 不参与 `zola build`、不进搜索索引、不进 sitemap/feed（共享铁律见 doc 03 §1.7，Zola 行为见 §2.8/§2.9）；**hidden 书 = 整本书 `draft=true`**（§2.6/§2.12）。**版权铁律不变**：`extra.copyrightStatus` 为 `unknown`/`private-draft` 的书籍，生产构建必须被校验脚本拦截（见 §2.12）。

---

## 第二部分：Zola 方案完整设计

### 2.1 结论与设计边界

```text
Zola + GitHub + Cloudflare Pages（单文件二进制、零依赖、Tera 模板、Pagefind 搜索索引）
```

保留的条件与共享模型一致：正文仍是 Markdown 文件、不需要数据库、只有你一个创建者、读者只读、Git 保存版本、Cloudflare Pages 自动构建发布。

**为什么 Zola 在这里是 Hugo 的更优平替：**
1. **单文件二进制、零依赖**：`zola build` 不需要 Go 工具链、不需要 Node、不需要插件生态；CI 里下一个二进制即可，比 Hugo extended 更轻。
2. **模板更友好**：Tera 是 Jinja2 风格，比 Go template 易读易写；作者/维护者更易改阅读器。
3. **内置能力齐全**：Sass 编译、代码高亮、`zola check` 链接检查（内/外链）全部内建；内置搜索索引（Fuse.js）虽开箱即用，但**对无空格中文分词不佳**，中文站需外接 Pagefind（唯一"内置但不适合中文"的能力，见 §2.9）。
4. **Git 工作流完全同 Hugo**：AI 生成 `.md` → `git push` → Cloudflare Pages 自动 `zola build` 发布。

**它不能满足的（与 Hugo 一致）：** 网页后台在线编辑（需接 Decap CMS / 自写编辑 UI，或换 Astro+Pages CMS）、读者网页版本切换（需按 tag 额外构建）、逐章 diff 页面。**内置搜索（Fuse.js）对无空格中文站分词不佳**（中文搜索需接 Pagefind，见 §2.9）。

### 2.2 系统总览

```mermaid
flowchart LR
    A["AI 生成草稿（.md + TOML frontmatter）"] --> B["作者修订 / zola serve --drafts 预览"]
    B --> C["Git commit & push"]
    C --> D["Cloudflare Pages 触发 scripts/build.sh"]
    D --> E["build.sh：校验+死链门控+构建+索引"]
    E --> F["Zola 生成 HTML"]
    F --> F2["Pagefind 生成搜索索引"]
    F2 --> G["Cloudflare CDN"]
    G --> H["读者阅读网站"]
```

**一次章节发布如何流动：** AI 生成草稿（含 `draft=true`）→ 作者本地 `zola serve --drafts` 预览（注意：Zola 的 `build` 与 `serve` 默认都不含草稿，看草稿必须显式 `--drafts`）→ 改 `draft=false` + 提交 Git → push 触发 Cloudflare Pages 构建 → `scripts/build.sh` 先跑校验脚本 + `zola check --skip-external-links` 查内部死链（任一失败则中断构建，旧版本仍在线）→ Zola 按 `weight` 排序生成书页/章节页、过滤 `draft=true`、生成 sitemap/feed → `npx pagefind@1.5.2 --site public` 生成搜索索引 → CDN 发布。

> 注：上方 Mermaid 图需支持 Mermaid 的渲染器（GitHub、部分 IDE 插件）；纯 Markdown 阅读器会显示源码，不影响其余内容。

### 2.3 技术栈

```text
生成器:       Zola（Rust 单文件二进制，零运行时依赖）
模板:         Tera（Jinja2 风格）
内容格式:     Markdown + TOML frontmatter（+++ 包裹）
样式:         原生 Sass（Zola 内置编译）
站内搜索:     Pagefind（构建后扫描 public/，固定 1.5.2，中文站必须 extended 版；见 §2.9）
版本管理:     Git + GitHub
部署平台:     Cloudflare Pages（原生支持，构建命令 zola build）
校验:         Python + tomllib（无第三方依赖，见 §2.12）
```

安装（单文件，无需生态）：

```bash
brew install zola                 # macOS
# 或下载预编译二进制：https://github.com/getzola/zola/releases
zola --version
```

> **搜索依赖取舍**：Pagefind 有三种等价跑法，选一种并固定版本——
> ① `npx pagefind@1.5.2 --site public`：npx **自动使用支持中/日文的 `pagefind_extended` 版**，Cloudflare 构建环境自带 Node；
> ② 零 Node：`python3 -m pip install 'pagefind[extended]==1.5.2'` 后 `python3 -m pagefind --site public`（官方 PyPI 包装，同样 extended 版，与本方案 Python 校验脚本同生态）；
> ③ 下载 GitHub 预编译二进制：**必须选 `pagefind_extended`，标准版不支持中文索引**。
> 想彻底零外部依赖也可用 Zola 内置搜索（Fuse.js）——但**它对无空格中文分词不佳**（见 §2.9）。中文小说站建议接受 Pagefind 这一个依赖。

### 2.4 仓库结构

```text
mixtxt-zola/
├── config.toml                   # 全站配置（标题/基础 URL/taxonomy/Sass）
├── prompts/                      # AI 提示词模板（作者侧资产，在 content/ 之外，不进构建）
│   └── rewrite-style-guide.md
├── content/
│   ├── _index.md                 # 首页：书籍列表（template = "home.html"）
│   ├── books/
│   │   ├── _index.md             # 书籍总览（template = "books.html"）
│   │   ├── sanguo-scifi/         # 一本书 = 一个 section
│   │   │   ├── _index.md         # 书页：简介 + 章节目录（extra.* + sort_by=weight）
│   │   │   ├── prologue.md       # 章节（weight=1）——文件名仅作 URL slug，不承载章号
│   │   │   ├── huangjin.md       # 章节（weight=2）
│   │   │   └── ...
│   ├── releases/
│   │   ├── _index.md             # 版本说明列表（template = "releases.html"）
│   │   └── sanguo-scifi-v0-1-0.md
│   ├── search.md                 # 搜索页（template = "search.html"）
│   └── about.md                  # 关于页（template = "page.html" 或默认）
├── templates/
│   ├── base.html                 # 全站骨架（头部/底部/样式引用）
│   ├── home.html                 # 首页
│   ├── books.html                # 书籍总览
│   ├── book.html                 # 单本书页（目录）
│   ├── chapter.html              # 章节页（正文 + 上下篇导航）
│   ├── releases.html             # 版本说明
│   ├── search.html               # 搜索
│   ├── page.html                 # 通用单页（about 等）
│   ├── taxonomy_list.html        # 标签总览页（见 §2.7；不提供则 Zola 默认裸页面无站点样式）
│   ├── taxonomy_single.html      # 单个标签页（同上）
│   └── 404.html                  # 404（Zola 模板级支持，不写则用默认）
├── sass/
│   └── main.scss                 # 编译到 public/main.css
├── static/
│   ├── covers/                   # 封面图
│   ├── images/chapters/          # 章节插图
│   ├── favicon.svg
│   ├── robots.txt
│   └── _headers                  # Cloudflare 缓存/安全头
├── scripts/
│   ├── validate_content.py       # 构建前校验（Python + tomllib）
│   ├── generate_chapters.py      # AI 章节生成/修订 harness（§2.18）
│   └── build.sh                  # 校验 + zola check + build + pagefind 唯一入口
├── runs/                         # harness 运行台账 runs/<book>.jsonl（§2.18，自动生成、可入 git 留审计）
├── .gitignore                    # 忽略 public/（含 pagefind/ 产物）
└── README.md
```
> 上述 `scripts/*` 与 `templates/search.html` 的**完整实现已在仓库根 [`mixtxt-zola/`](../../mixtxt-zola/) 就地落地**（单一真实源，见 §2.9/§2.12/§2.18）；本文只给规则与关键要点，不再粘贴全文。

**为什么书用嵌套目录（而非平铺）：** Zola 的 section 机制天然把「一本书 = 一个目录」，`_index.md` 即书元数据、目录下 `.md` 即章节；导航/上下篇自动限制在当前 section 内，零额外代码。这与 doc 03 §1.3 的「按书嵌套目录（Hugo 风格）」一致。**章节文件名只作 URL slug、不承载章号**（`huangjin.md`），排序/显示由 frontmatter `weight` 决定——这让插章/删章/重排只需改 `weight`、文件名与既有链接永远不动（§2.8）。

**为什么 prompts 在 `content/` 之外：** `content/` 里任何 `.md` 都会被 Zola 当页面处理；section 的 `render = false` 只关掉 section 自身页面，**不阻止子页面渲染**（官方确认，且 `render=false` 的页面仍会出现在 taxonomy 页）。prompts 是作者侧资产而非站点内容，放在仓库根 `prompts/` 才是零歧义的隔离——AI 工作流（§2.13）直接按路径读文件即可。

### 2.5 配置 config.toml

```toml
base_url = "https://mixtxt.example.com"
title = "Mixtxt · AI 改编小说"
description = "AI 辅助改编小说的单作者阅读站"
default_language = "zh"
author = "matrix"           # 顶层 author：供 Atom/RSS feed 的 <author>（放在 [extra] 不会被 feed 识别）

# 内建能力
compile_sass = true          # sass/main.scss -> public/main.css
build_search_index = false   # 搜索用 Pagefind（构建后生成索引）；内置搜索（Fuse.js）对无空格中文分词不佳，勿开
generate_feeds = true        # 自动 RSS/Atom（需页面有 date）
generate_sitemap = true      # 自动 sitemap.xml
feed_filenames = ["atom.xml"]  # 0.19 起字段名（原 feed_filename 已废弃）
minify_html = true           # 压缩 HTML（可选，按需开启）

# 分类法：书籍/章节都可打 tags（自动生成 /tags/ 页，模板见 §2.7；若首版不做标签页，删掉本节并清掉章节示例的 [taxonomies]）
taxonomies = [
  { name = "tags", feed = true },
]

# 代码高亮（Zola 0.22+ 用 Giallo，配置在 [markdown.highlighting]；小说站不需要高亮则删掉本段，默认不高亮）
[markdown.highlighting]
theme = "github-dark"

[extra]
copyright = "改编内容版权归原作者与作者所有；非公版内容仅作私人草稿。"
```

> **构建命令**：`zola build` 输出到 `public/`（默认排除草稿）。`zola serve --drafts` 本地预览草稿（默认不含草稿，需显式 `--drafts`）。`zola check` 校验内/外链接（外链默认发 HTTP；跳过的策略见 §2.12）。

### 2.6 内容模型与字段示例

**书：`content/books/sanguo-scifi/_index.md`**（section frontmatter）

```toml
+++
title = "三国演义：星火纪元"
description = "把东汉末年的群雄割据改写成星际文明崩塌后的权力重组。"   # = summary
template = "book.html"
sort_by = "weight"          # 章节按 weight 升序
draft = false               # 与 extra.visibility 联动：hidden 的书此处置 true（整本书不进公开构建）
[extra]
original = "三国演义"
author = "罗贯中"
adaptor = "matrix + AI"
status = "serializing"      # planning/serializing/completed/paused
visibility = "public"       # public/hidden（hidden → 顶层 draft=true）
cover = "/covers/sanguo-scifi.webp"
copyrightStatus = "public-domain"   # public-domain/authorized/private-draft/unknown
startedAt = "2026-06-03"
updatedAt = "2026-06-03"
+++
```

> **hidden 书 = section `draft = true`**（Zola 官方：被 draft 的 section，其子孙页面无论自身 draft 与否一律不处理，`zola serve --drafts` 才可见）。这样"隐藏书"不是靠模板过滤卡片（那只是不显示入口，页面仍会被构建公开访问），而是整本书不进构建产物——与"构建即公开"的静态站边界一致。`validate_content.py` 强制联动（§2.12）。

**章节：`content/books/sanguo-scifi/huangjin.md`**（page frontmatter；文件名只作 URL slug，不承载章号）

```toml
+++
title = "黄巾初起"
description = "巨鹿星区的张角点燃第一枚信标，旧帝国的边境开始瓦解。"   # = summary
weight = 2                  # 排序与显示章号的唯一真源；validate 强制（§2.12）
draft = false               # false = 已发布；true = 草稿/未发布
date = 2026-06-03T10:00:00+08:00
# 不写 in_search_index：那是 Zola 内置搜索（build_search_index）的开关；本方案搜索由
# Pagefind 的 data-pagefind-body 控制（§2.7），写它只会误导
[taxonomies]
tags = ["三国", "科幻", "AI改编"]
[extra]
createdAt = "2026-06-03"
updatedAt = "2026-06-03"
[extra.ai]
model = "manual-or-ai-assisted"
prompt = "rewrite-style-guide"
humanEdited = true
+++
```

> 正文在 `+++` 之后的 Markdown 中书写。Zola 只识别固定顶层键（`title`/`description`/`date`/`weight`/`draft`/`slug`/`template`/`sort_by`/`in_search_index`/`taxonomies`/`extra` 等）；`status`/`visibility`/`cover`/`copyrightStatus`/`ai` 等自定义字段必须放 `[extra]`，模板里用 `page.extra.xxx` 访问。**字数/阅读时长不用存**——Zola 原生提供 `page.word_count`（zh/ja 按字符计）与 `page.reading_time`。**章号与书归属也不用存**：`weight` 是排序与显示章号的唯一真源（显示用 `"%03d" | format(page.weight)` 派生三位章号），书归属由所在目录唯一决定、章节 URL 用文件名 slug——**文件名不承载章号**（插章/重排只改 weight，URL/链接恒定，§2.8）；存 `chapterNo`/`book` 只会造成第三份漂移源，与已删的 `wordCount`/`seo` 同理（validate 的单一真源校验见 §2.12）。
>
> **不存 `[extra.seo]`**：页面 title/description 已由 base.html/chapter.html 的 block 推导（`{weight} {title} - {book} - {site}`，章号由 `"%03d"|format(weight)` 派生），逐章存 seo 是死数据且会漂移（改了 title 忘改 seo.title）。共享模型的 `seo` 是可选字段，Zola 用模板推导即等价实现。

**releases：`content/releases/sanguo-scifi-v0-1-0.md`**

```toml
+++
title = "v0.1.0 星火初燃"
description = "首批 12 章上线，完成楔子到黄巾落幕。"
template = "releases.html"
[extra]
book = "sanguo-scifi"
version = "v0.1.0"
versionSlug = "sanguo-scifi-v0-1-0"
gitTag = "v0.1.0"
+++
```

**prompts（作者侧资产，放仓库根 `prompts/`，不在 `content/` 里）**

```text
prompts/rewrite-style-guide.md    # 纯 Markdown 文本即可，无 frontmatter 要求
```

> prompts 不是站点内容，放 `content/` 外就不会被 Zola 当页面处理（section `render=false` 不阻止子页面渲染，见 §2.4 说明）。AI 工作流直接按 `prompts/<slug>.md` 路径读取。

### 2.7 模板（Tera）

> 真源说明：当前仅 `templates/search.html` 已在仓库根 [`mixtxt-zola/`](../../mixtxt-zola/) 落地（§2.9）；base/home/book/chapter 等其余模板**以本文档 §2.7 为唯一真源**，Phase 1 创建站点时按本文落地，避免文档与 repo 双写漂移。

**base.html（骨架）**

```html
<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}{{ config.title }}{% endblock %}</title>
  <meta name="description" content="{% block description %}{{ config.description }}{% endblock %}">
  <link rel="canonical" href="{{ current_url }}">
  <meta property="og:title" content="{% block title %}{{ config.title }}{% endblock %}">
  <meta property="og:description" content="{% block description %}{{ config.description }}{% endblock %}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{{ current_url }}">
  <meta property="og:image" content="{% block ogimage %}{{ get_url(path='favicon.svg') }}{% endblock %}">
  <link rel="stylesheet" href="{{ get_url(path='main.css', cachebust=true) }}">
</head>
<body>
  <header class="site-header">
    <a href="{{ config.base_url }}">{{ config.title }}</a>
    <nav><a href="{{ get_url(path='@/books/_index.md') }}">作品</a>
         <a href="{{ get_url(path='@/search.md') }}">搜索</a>
         <a href="{{ get_url(path='@/about.md') }}">关于</a></nav>
  </header>
  <main>{% block content %}{% endblock %}</main>
  <footer class="site-footer"><p>{{ config.extra.copyright }}</p></footer>
  {% block scripts %}{% endblock %}
</body>
</html>
```

**home.html（首页：书籍列表）**

```html
{% extends "base.html" %}
{% block content %}
<h1>全部作品</h1>
<div class="book-grid">
{% set books_section = get_section(path="@/books/_index.md") %}
{% for sub in books_section.subsections %}
  {% set s = get_section(path=sub) %}
  {% if s.extra.visibility != "hidden" %}
  {# 双保险：hidden 书除 section draft=true（构建期过滤）外，再留一道模板过滤——Zola 未保证 draft section 会从父 section 的 subsections 移除（§2.6/§2.12） #}
  <article class="book-card">
    <a href="{{ s.permalink }}">
      <img src="{{ s.extra.cover }}" alt="{{ s.title }}">
      <h2>{{ s.title }}</h2>
    </a>
    <p>{{ s.description }}</p>
    <p class="meta">状态：{{ s.extra.status }} ｜ 版权：{{ s.extra.copyrightStatus }}</p>
  </article>
  {% endif %}
{% endfor %}
</div>
{% endblock %}
```

**book.html（单本书页：简介 + 章节目录）**

```html
{% extends "base.html" %}
{% block title %}{{ section.title }} - {{ config.title }}{% endblock %}
{% block description %}{{ section.description }}{% endblock %}
{% block ogimage %}{% if section.extra.cover %}{{ get_url(path=section.extra.cover) }}{% else %}{{ get_url(path='favicon.svg') }}{% endif %}{% endblock %}
{% block content %}
<article class="book">
  <header>
    <img src="{{ section.extra.cover }}" alt="{{ section.title }}">
    <h1>{{ section.title }}</h1>
    <p class="meta">原作：{{ section.extra.original }} ｜ 状态：{{ section.extra.status }}</p>
    <p class="summary">{{ section.description }}</p>
    <p class="copyright">版权：{{ section.extra.copyrightStatus }}</p>
  </header>
  <h2>目录</h2>
  <ol class="toc">
  {% for page in section.pages %}
    {# 双保险：Zola 构建期已把草稿从 section.pages 移出，此判断通常恒真；保留以防子目录漏排 #}
    {% if not page.draft %}
    <li><a href="{{ page.permalink }}">{{ "%03d" | format(page.weight) }} {{ page.title }}</a></li>
    {% endif %}
  {% endfor %}
  </ol>
</article>
{% endblock %}
```

**chapter.html（章节页：正文 + 上下篇导航）**

```html
{% extends "base.html" %}
{% block title %}{{ "%03d" | format(page.weight) }} {{ page.title }} - {{ section.title }} - {{ config.title }}{% endblock %}
{% block description %}{{ page.description }}{% endblock %}
{% block ogimage %}{% if section.extra.cover %}{{ get_url(path=section.extra.cover) }}{% else %}{{ get_url(path='favicon.svg') }}{% endif %}{% endblock %}
{% block content %}
<article class="chapter" data-pagefind-body>
  <header><h1>{{ "%03d" | format(page.weight) }} {{ page.title }}</h1></header>
  {{ page.content | safe }}
  <nav class="chapter-nav" data-pagefind-ignore>
    {% if page.lower %}<a href="{{ page.lower.permalink }}">← 上一章</a>{% endif %}
    <a href="{{ section.permalink }}">目录</a>
    {% if page.higher %}<a href="{{ page.higher.permalink }}">下一章 →</a>{% endif %}
  </nav>
</article>
{% endblock %}
```

> `data-pagefind-body`：Pagefind（§2.9）只索引显式标记的元素——章节正文才进搜索索引；`data-pagefind-ignore` 排除导航等噪音（不加的话"上一章/下一章/目录"会被索引，搜"目录"会命中所有章节）。这是主搜索方案的必需标记，不是预留。

**taxonomy_list.html / taxonomy_single.html（标签页，简版）**

```html
{% extends "base.html" %}
{% block content %}
<h1>标签：{{ term.name }}</h1>
<ul>
{% for page in term.pages %}
  <li><a href="{{ page.permalink }}">{{ page.title }}</a></li>
{% endfor %}
</ul>
{% endblock %}
```

> 上面是 `taxonomy_single.html`（单个标签页，`term.pages` 即该标签下页面）；`taxonomy_list.html`（/tags/ 总览）写法相同，把 `term.name` 换成遍历 `{% for term in terms %}`。**不提供这两个模板时，Zola 用内置默认渲染标签页——是脱离全站样式的裸页面**。若首版不做标签页，删掉 config 的 `taxonomies` 与章节示例的 `[taxonomies]` 即可，模板也不需要。

### 2.8 章节导航 prev/next（不跨书）

Zola 里章节是 book section 的子页面，排序由 `_index.md` 的 `sort_by = "weight"` 决定（升序）。在 `chapter.html` 中：

- `page.lower` → 当前 section 内排序值更小（`weight` 更小）的上一章
- `page.higher` → 当前 section 内排序值更大（`weight` 更大）的下一章

> **命名注意**：`lower`/`higher` 是 Zola 0.16+ 的正式命名（旧版叫 `earlier`/`later`，**0.16 起已移除**）。用对命名后方向固定：`lower`=上一章、`higher`=下一章，无需任何交换。

由于限制在当前 section，**天然不跨书**，与共享铁律一致。草稿（`draft=true`）不出现在 `lower`/`higher` 与 `section.pages` 中，因此导航永远指向已发布章节。

**连载中插章/删章/重排（只动 `weight`，文件名/slug/URL 永不改变）：** 章号唯一真源是 frontmatter 的 `weight`，文件名只是 URL slug、不承载顺序。因此在书中间插入新章 = 把其后所有章节的 `weight` 批量 +1 即可，文件名与链接零改动——天然没有 `git mv` 冲突、没有死链。最高频操作不要手改，用脚本批量改并让 `validate_content.py` 把关：

```bash
# 在第 3 章与第 4 章之间插入一章：把 weight>=3 的章节 weight+1（只改独行 `weight = N`，其余不动）
python3 - <<'PY'
import pathlib, re
for p in pathlib.Path("content/books/<slug>").glob("*.md"):
    t = p.read_text(encoding="utf-8")
    m = re.search(r"^weight = (\d+)$", t, re.M)
    if m and int(m.group(1)) >= 3:
        p.write_text(re.sub(r"^weight = (\d+)$",
                            lambda g: f"weight = {int(g.group(1)) + 1}",
                            t, flags=re.M), encoding="utf-8")
PY
python3 scripts/validate_content.py     # weight 为非负整数且书内唯一——重排正确性的最后防线
```

> 要点：`re.M` 精确匹配独行 `weight = N`，不会误改 `[extra]` 里的同名键；数字由 Python 解析、无八进制歧义；文件名不改 → 章节 URL/外链/读者书签恒定。删章同理（反向 -1）；缺号（如删章留空隙）允许——显示章号按 weight 派生仍正确，validate 只要求唯一与合法。`slug` 需书内唯一（validate 检查），重排不涉及文件名故天然满足。重排后跑 validate 再 commit。**区分"重排"与"改名"**：重排（只改 `weight`）不动文件名、URL 恒定；若手工改名章节文件（改 slug）则 URL 会变——须在 frontmatter 加 `aliases = [...]` 保留旧 URL 防死链（只改 weight 的重排不需要）。

### 2.9 站内搜索（Pagefind，中文可用的唯一可靠静态方案）

**为什么不用 Zola 内置搜索：** Zola 的 `build_search_index`（0.19+ 基于 Fuse.js）把文本按空白切词索引，**对无空格的 CJK 分词不可用**——中文整句输入时前后端分词不一致、命中率低，Fuse.js 也没有面向中文的分词调优。

中文小说站唯一可靠的静态搜索是 **Pagefind**（v1.5+ 原生 CJK 分词，构建时索引、浏览器端检索、分块加载，与 doc 03 推荐方案一致）：

```bash
zola build                          # 先生成 HTML
npx pagefind@1.5.2 --site public    # 再扫描 public/ 生成 public/pagefind/ 索引（固定版本；或 python3 -m pagefind，见 §2.3）
```

- 索引范围由 `data-pagefind-body` 决定（§2.7 章节正文已标记；`data-pagefind-ignore` 排除导航等噪音）。
- **草稿天然不进索引**：`draft=true` 不参与构建，Pagefind 只扫构建产物，与共享草稿铁律一致。
- `pagefind/` 产物生成在 `public/` 下，**不入库**（.gitignore 忽略整个 public/）。
- **依赖取舍**：见 §2.3——npx（Node）或 PyPI（Python）包装都自动用支持中文的 `pagefind_extended` 版；下载二进制必须选 extended 版。这是 Zola 方案唯一引入的外部搜索依赖——换取中文可用的全文搜索，值得。
- **本地 `zola serve` 不生成搜索索引**（pagefind 是构建后步骤）：调试搜索需 `zola build` + pagefind 后直接预览 `public/`。

**搜索页 `content/search.md`，`template = "search.html"`**，用 Pagefind 官方 JS API 手写一个最小实现（`textContent` 渲染天然防 XSS）。**完整模板见 [`mixtxt-zola/templates/search.html`](../../mixtxt-zola/templates/search.html)，核心套路仅三点：**
- 动态 `import("/pagefind/pagefind.js")` 且只初始化一次；
- 用递增请求序号做**竞态守卫**（只渲染最后一次输入的结果，避免乱序覆盖）；
- 结果标题用 `textContent`、摘要用 `DOMParser` 取纯文本——不把索引 HTML 注入页面。

> 更省事的做法：直接用 Pagefind 官方 UI 组件（`/pagefind/pagefind-ui.css` + 组件脚本），样式和结果面板现成；手写版的好处是零 UI 依赖、结构完全可控。若实测中文分词不理想（旧版行为），可对查询词做 bigram 预处理后再传给 `pagefind.search()`。

### 2.10 样式与阅读体验（Sass）

`compile_sass = true` 时，`sass/main.scss` 编译到 `public/main.css`。阅读体验变量（与 doc 03 §2.10 一致）：

```scss
:root {
  --color-bg: #f5f3ee;        /* 接近纸张的浅灰，不刺眼 */
  --color-surface: #ffffff;
  --color-text: #1f1d1a;
  --color-muted: #6b665e;
  --color-border: #e3dfd6;
  --color-accent: #8a5a2b;
  --reader-width: 720px;
  --reader-font-size: 18px;
  --reader-line-height: 1.8;
}
[data-theme="dark"] {
  --color-bg: #1a1816;
  --color-surface: #24211e;
  --color-text: #ece8e1;
  --color-muted: #9a938a;
  --color-border: #34302b;
}
.chapter { max-width: var(--reader-width); margin: 0 auto; }
.chapter p { font-size: var(--reader-font-size); line-height: var(--reader-line-height); }
```

阅读工具栏（字号/行距/主题/宽度）用原生 JS + `localStorage`（同 doc 03 §2.10），`zola build` 产出的纯静态页同样适用。**继续阅读进度**（同 doc 03 §2.10）：每本书记录 `localStorage["mixtxt.reader.lastChapter.{bookSlug}"]`，首页/书页显示"继续阅读"入口。

### 2.11 部署（Cloudflare Pages）

Cloudflare Pages **原生支持 Zola**（v2 构建环境内置 Zola，默认 0.22.1；`ZOLA_VERSION` 可覆盖为任意 ≥0.5 的版本）：

```text
Framework preset: 无（或 Zola）
Build command:    if [ "$CF_PAGES_BRANCH" = "main" ]; then ./scripts/build.sh; else ./scripts/build.sh --base-url "$CF_PAGES_URL"; fi
Build output:     public
Root directory:   mixtxt-zola   # 关键：站点在仓库子目录，必须指向 mixtxt-zola，否则找不到 scripts/ 且输出目录错配
Environment variables: ZOLA_VERSION = 0.23.3   # 固定版本，避免漂移（2026-08-12 官方稳定版，修复低危安全漏洞）
```

> **Root directory 必须设为 `mixtxt-zola`**：本仓库根 `mixtxt/` 下，`mixtxt-zola/` 才是 Zola 项目（含 `config.toml`/`content/`/`scripts/`）。若设为 `/`（仓库根），构建命令 `./scripts/build.sh` 会在仓库根找不到 `scripts/`（实际在 `mixtxt-zola/scripts/`），且 `zola build` 的输出 `public/` 会落错目录，与 Build output 设置错配。设成 `mixtxt-zola` 后，Cloudflare 以它为工作目录，`build.sh` 内的 `cd "$(dirname "$0")/.."` 也自定位到该目录，二者一致。

- 构建命令用 **Cloudflare 官方推荐的分支判断**：生产分支（main）用 `config.toml` 的 `base_url`；预览分支（PR 预览）用 `CF_PAGES_URL` 动态覆盖，避免预览页资源加载失败。**分支判断在面板、构建逻辑在 `scripts/build.sh`（§2.12）**——它内部先跑校验脚本、再 `zola check --skip-external-links` 查内部死链、再 `zola build "$@"`、再 pagefind，是校验+链接检查+构建+索引的**唯一入口**，保证生产构建永不漏跑内容门禁（此前直接内联 `zola build` 时校验脚本并不执行，是门禁缺口）。
- `static/_headers` 缓存策略同 doc 03 §2.12：HTML `max-age=3600`，`/covers/*`、`/images/*`、`/pagefind/*` 等设 `max-age=31536000, immutable`，并加安全响应头。
- 免费层限制（每项目 500 构建/月、20,000 文件、25 MiB）与构建频率策略同 doc 03 §1.5。

**可选 GitHub Actions 兜底**（push 前本地构建门控，避免坏构建上线）：

```yaml
# .github/workflows/build.yml
name: build
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: taiki-e/install-action@v2
        with: { tool: zola }
      - run: ./scripts/build.sh                 # 与 Cloudflare Pages 同一入口：validate + zola check + build + pagefind
      - uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CF_API_TOKEN }}
          accountId: ${{ secrets.CF_ACCOUNT_ID }}
          projectName: mixtxt
          directory: public
```

### 2.12 内容校验脚本（Python + tomllib，无依赖）

Zola 不像 Astro 有 Content Collections schema 强校验，所以用 `scripts/validate_content.py`（Python 3.11+ 内置 `tomllib`，零依赖）在构建前强制共享硬约束。**完整实现见 [`mixtxt-zola/scripts/validate_content.py`](../../mixtxt-zola/scripts/validate_content.py)，本文不再粘贴全文，只写规则与关键实现要点。**

**校验规则（与脚本逐条对应）：**
1. 每本书 section 必须有 `_index.md`；frontmatter 须以独占一行的 `+++` 闭合且 TOML 合法。
2. 版权硬约束：`copyrightStatus ∈ {unknown, private-draft}` 不允许公开构建；`private-draft` 时 `visibility` 必须 `hidden`；`hidden` 书必须设 section `draft=true`（整本书不进构建）。
3. 封面路径存在。
4. 每章：文件名（slug）合法且书内唯一（只作 URL、不承载章号）；**`weight` 为非负整数且书内唯一**（单一真源：显示章号/排序/顺序都由它派生）；`date` 格式合法；`createdAt ≤ updatedAt` 且 `updatedAt ≥ 发布日 date`；`aliases`（若有）为不含空白的非空字符串数组。
5. 已发布章节（`draft=false` 或缺省）不得挂在 `copyrightStatus ∈ {unknown, private-draft}` 的书下。

**关键实现要点（防踩坑）：**
- frontmatter 用 `tomllib.loads` 解析 `+++\n…\n+++`；`date` 用无引号 datetime（官方建议不要用引号包裹）。
- weight 与文件名解耦：校验**不**要求"文件名前缀==weight"，文件只作 slug——§2.8 重排只改 weight 不会破坏校验。
- 任一 error 累积后打印清单并以退出码 1 中断构建（旧版本保持在线）。

`scripts/build.sh` 是校验+链接检查+构建+索引的**唯一构建入口**（Cloudflare Pages 与 GitHub Actions 都调用它，保证门禁永不缺席），透传 `zola build` 参数。**完整内容见 [`mixtxt-zola/scripts/build.sh`](../../mixtxt-zola/scripts/build.sh)**，要点：先跑 `validate_content.py`（失败即中断、旧版保持在线）、再 `zola check --skip-external-links` 查**内部**死链（不发 HTTP、构建环境稳定）、再 `zola build "$@"`（透传如 `--base-url "$CF_PAGES_URL"`）、最后 `npx pagefind@1.5.2 --site public` 生成搜索索引。

> 校验未能覆盖的低风险规则（releases 的 semver、`ai.prompt` 引用）首版不进 `validate_content.py`：注意 `zola check` 只查链接、查不了这两类，留待有需要时再补规则。AI 实现项目时不要随意改字段名；改了必须同步模板与示例。

### 2.13 AI 创作工作流（Zola 适配）

首版不把 AI 接口接到站内，流程与共享模型一致：

1. 选原作与改编方向 → 用仓库根 `prompts/` 里的提示词模板生成章节草稿（`prompts/<slug>.md`，直接按路径读）。
2. 草稿写成 `.md`，默认 `draft = true`（不发布），`extra.ai` 记录模型/prompt/是否人工修订。
3. 作者本地 `zola serve --drafts` 预览草稿，修订事实/节奏/人物动机。
4. 确认无误后改 `draft = false`，`git commit` + `git push` 触发 Cloudflare Pages 构建。
5. 构建前 `validate_content.py` 门控版权/一致性/封面；`build.sh` 内已含 `zola check --skip-external-links` 查**内部**死链（不发 HTTP）。**外部**链接的全量检查策略见 §2.12（默认发 HTTP、构建环境不稳易红，正文外链多时本地手动查一次）。

> **发布判定**：Zola 用 `draft` 布尔表示发布（`false` = 已发布），等价于共享模型的 `status == "published"`。AI 自动化流水线可批量写 `draft=true` 草稿，再由人工（或受控脚本）翻 `draft=false`——**AI 负责生成草稿，人/受控步骤决定发布**，与 doc 03 §1.4 / §2.13 铁律一致。批量发布（受控翻草稿）走 §2.18 的 `--publish` 模式，不再手写 `sed`/shell。

**定时自动化接线**：详见 §2.18 harness 的定时确定性设计。四个原子步（生成/修订 → 攒稿 → `--publish` 翻发 → validate 通过才 push）串起来即完成定时任务；节流铁律、串行+幂等、台账自愈等设计决策均在 §2.18 中说明。

### 2.14 版本管理（同共享模型）

完全复用 doc 03 §1.4 三层模型，Git 即是正本版本系统：

```bash
git add content/books/sanguo-scifi/huangjin.md
git commit -m "feat: 黄巾初起"
git tag v0.2.0 && git push origin v0.2.0
```

给读者看版本变化用 `content/releases/` 版本说明页（不替代 Git 逐字历史）。按 Git tag 部署历史版本（子路径 `/versions/v0.1.0/`）属于第二阶段。

### 2.15 实施计划

- **Phase 0 初始化**：`zola init`、写 `config.toml`、基础 Sass、示例内容。验收：`zola serve` / `zola build` 通过。
- **Phase 1 内容结构与路由**：书 section + 章节 page、`book.html`/`chapter.html`、首页书籍列表、上下篇导航。验收：公开内容显示、草稿不显示、上/下一篇正确。
- **Phase 2 校验与质量**：`validate_content.py`、`zola check`、版权门控。验收：坏内容被拦截、死链被报出。
- **Phase 3 阅读体验**：Sass 变量、暗色/字号/行距/宽度、`localStorage`、移动端适配。
- **Phase 4 搜索与 SEO**：Pagefind 搜索页、RSS/feed、sitemap、canonical/OG meta。
- **Phase 5 部署**：连 Cloudflare Pages、固定 `ZOLA_VERSION`、自定义域名、缓存头、构建次数监控。

### 2.16 风险与应对

| 风险 | 应对 |
|------|------|
| Zola 无 schema 强校验，字段易乱 | `validate_content.py` 构建前门控（含 weight 唯一性） |
| 私有草稿误入公开构建 | 校验脚本拦截 `copyrightStatus=unknown/private-draft`；本地 `zola serve --drafts` 仅作者可见 |
| hidden 书被构建公开访问 | hidden 书必须设 section `draft=true`（整本书不进构建），validate 强制 |
| 草稿进入搜索/导航 | `draft=true` 自动被 Zola 排除；Pagefind 只扫构建产物 |
| 中文搜索不可用 | 内置搜索（Fuse.js）对无空格中文分词不佳 → 用 Pagefind（v1.5+ 原生 CJK），见 §2.9 |
| prompts 被当作页面渲染 | prompts 放 `content/` 之外的仓库根 `prompts/`，零 Zola 语义依赖 |
| 外链检查拖慢/中断构建 | `zola check --skip-external-links` 跳过外部链接（内部死链仍查） |
| Cloudflare 构建次数不够 | 本地预览后集中 push，控制频率（同 §1.5） |
| 文件数超限 | 控制历史版本页数量，必要时拆站 |
| 原作版权不清 | `unknown` 不允许公开构建 |
| 版本漂移 | 固定 `ZOLA_VERSION` 与 `pagefind@1.5.2`，升级前本地 `zola build` |
| 搜索用错标准版二进制 | 中文索引必须用 `pagefind_extended`（npx / PyPI 包装默认即 extended，见 §2.3） |
| 搜索索引含导航文字 | 章节导航 `data-pagefind-ignore`（否则搜"目录"命中所有章节，见 §2.7） |
| 构建失败读者看到旧版 | GitHub Actions 本地构建门控，push 前先跑 build |

### 2.17 与 Astro + Pages CMS / Hugo 的取舍

| 对比项 | Zola | Hugo | Astro + Pages CMS |
|--------|------|------|-------------------|
| 语言/依赖 | Rust 单文件，零依赖 | Go 单文件（extended） | Node 生态，较重 |
| 模板 | Tera（Jinja2 风，好写） | Go template（强但难读） | Astro 组件（最灵活） |
| 中文搜索 | ✅ Pagefind（npx / PyPI 包装或二进制，见 §2.3） | ❌ 需外接 | ✅ Pagefind（同） |
| 链接检查 | ✅ `zola check`（内外链） | ⚠️ 需插件 | ⚠️ 需自写 |
| schema 校验 | ⚠️ 需自写脚本 | ❌ 弱 | ✅ Content Collections 原生 |
| 网页编辑 UI | ❌ 需外接 | ❌ 需外接 | ✅ Pages CMS 集成 |
| 构建速度 | 秒级 | 更快（数千页亚秒） | 较快，慢于前两者 |
| 阅读器交互 | 模板可做到 | 模板可做，不如 Astro | 最自然 |
| AI 自动化（git 触发） | ✅ 同 Hugo | ✅ | ✅ |

**判断：**
- 想要 **Hugo 的极速 + 零依赖 + 更友好的模板 + 链接检查内建（中文搜索配 Pagefind）** → **Zola**。
- 想要 **网页编辑后台 + 内容结构强校验 + 最灵活阅读器** → **Astro + Pages CMS**（doc 03 推荐）。
- 只想 **最少折腾最快上线、且习惯 Go 生态** → **Hugo**。
- 出现 **付费/VIP/用户** → 完整业务切动态方案（doc 02）；仅少数章节收费可先混合付费墙（doc 01 §1.2）。

### 2.18 AI 内容生成 harness（把"让 AI 写 N 章"变成可执行脚本）

§2.13 只描述了"AI 能生成草稿"，这里补上**可直接运行**的生成套件：`scripts/generate_chapters.py`。

**关键设计（对抗性审查得出的稳健做法）：** 不让 AI 输出 frontmatter——**AI 只写正文 Markdown，frontmatter 由脚本统一生成**。原因：AI 输出 TOML 的格式不稳定（引号/字段名/日期格式极易飘），而脚本生成的 frontmatter 保证与 §2.6 示例、`validate_content.py` 的校验规则**逐字段一致**。AI 的活被压缩到"只写正文"这一件最擅长的事上。

**完整实现见 [`mixtxt-zola/scripts/generate_chapters.py`](../../mixtxt-zola/scripts/generate_chapters.py)**（Python 3.11+，零第三方依赖，OpenAI 兼容 API）。三种模式：
- **生成（追加新章）**：`--count N`，从现有最大 `weight+1` 起追加；或 `--weights 5,7` 精确生成指定章（重试补位用，章已存在则报错）。
- **修订（改已有章）**：`--weights 5,7 --revise`，保留 `weight`/slug/`date`/URL/`aliases` 等既有元数据，只重写正文并更新 `updatedAt`。注意：修订**保留原章 `draft` 状态**——修订已发布章会直接生效（不经草稿-审阅流程），敏感修订先用 `--dry-run` 确认，或改回 `draft=true` 复核后再发布。
- **发布（翻草稿）**：`--publish 5,6,7`，把指定章 `draft=true` 翻为 `false`（手术式替换，保留其余元数据；已发布章跳过）。不能与 `--count/--weights/--revise` 同用。

结构要点：
- `read_frontmatter()`：按 `+++\n…\n+++` 解析出 `(frontmatter, 正文)`，全脚本复用（书元数据/扫 weight/取种子/修订）。
- `render_frontmatter()`：渲染与 §2.6 逐字段一致的 frontmatter（`weight`/`draft`/无引号 TOML datetime/`[taxonomies].tags`/`[extra]`/`[extra.ai]`）；`--revise` 修订时透传原 `aliases`（防死链元数据）。`date` 保留原值、`updatedAt` 恒为今天——AI 只写正文、不碰 frontmatter。
- `llm_chat()`：调 `/chat/completions`；缺 `LLM_API_KEY` 报错退出（fail-fast）；429/5xx 退避重试（共 3 次）。
- `latest_published_seed()`：取最新章节（weight 最大且非草稿）结尾约 300 字作**续写前情种子**（多轮定时连载不脱节）；`--context` 可覆盖。
- `main()`：校验书 slug → fail-fast 版权门控（非 `public-domain`/`authorized` 拒绝）→ 目标判定（`--count` 追加 / `--weights` 精确寻址：修订须已存在、生成须未占用）→ 并发处理（单章失败不拖垮整批）→ 写 `runs/<book>.jsonl` 台账 → 失败时打印可复制的精确重试命令 → 跑 `validate_content.py` 兜底。

**为"定时自动化"设计的确定性：**
- 时间统一 `ZoneInfo("Asia/Shanghai")`（UTC+8 无夏令时），与运行机/CI 的本地时区（多为 UTC）无关，杜绝章 `date`/RSS 排序漂移。
- 每次运行追加 `runs/<book>.jsonl` 台账（时间/模式/目标/成功/失败+错误），无人值守可排障；`--weights` + 台账即精确重试依据，不再有"中段失败章被永久跳过留空档"。
- `--dry-run` 不调 LLM、不写文件，先看会处理哪些目标。

**使用前提与边界：**
- 书目录 `content/books/<slug>/_index.md` 必须已存在。**脚本生成前先读 `extra.copyrightStatus`**：非 `public-domain`/`authorized` 立即拒绝（fail-fast）——不调 LLM、不写文件，版权门控从"生成后被 validate 拦"提前到"生成前拒绝"。
- 生成的是 `draft=true` 草稿，不进构建/搜索/导航；作者 `zola serve --drafts` 预览修订后，改 `draft=false` 再 push 发布——**AI 负责生成草稿、人决定发布**的铁律由脚本结构强制保证。
- `date` 输出为**无引号 TOML datetime**（`2026-06-03T10:00:00+08:00`）——Zola 官方明确不要用引号包日期；这与 §2.6 章节示例一致。
- 缺 `LLM_API_KEY` 时直接报错退出（配置错误下所有章节都会失败，fail-fast）；429/5xx 自动退避重试（共 3 次）；`--title` 缺省时读 `_index.md` 真实书名（而非 slug）。**单章永久错误不中断整批**——其余继续，失败以退出码 1 + 精确重试命令收尾。
- 生成的文件名 `ch<weight>.md` 只是 **URL slug**（URL 为 `/books/<slug>/ch<weight>/`），不承载章号；想要语义化 URL，改名成 `huangjin.md` 即可，改后章号仍由 `weight` 决定。**`--revise` 不改文件名/slug → URL 恒定，外链/书签不失效。**
- `--weights` 语义：不带 `--revise`=生成该批新章（已存在则报错）；带 `--revise`=修订该批旧章（不存在则报错）——避免误覆盖。
- `--publish` 语义：只做 `draft=true→false` 的手术式替换，保留其余元数据（标题/`description`/`aliases`/`ai`）；已发布章跳过；失败记 `runs` 台账。
- `--parallel N` 并发调 LLM（默认 4，上百章建议 8-16）。
- 每章标题初始为"第 N 章"、`description` 取正文首行，`--revise` 修订标题沿用原 `title`——**这些仍需作者复核**，脚本故意不猜。

> 这个脚本的 frontmatter 与 §2.6 章节示例逐字段一致（`weight`/`draft`/`date`/`[taxonomies]`/`[extra]`/`[extra.ai]`），生成后必须通过 `validate_content.py` 才算完成闭环。若后续改用 Astro/Hugo（doc 03），同一思路换成各自 frontmatter 格式即可。

---

## 第三部分：一句话选择指引（场景 A 补充）

| 需求 | 选择 |
|------|------|
| 最快上线、最少折腾、纯 Git 工作流（Go 生态） | **Hugo + Git** |
| 同 Hugo 路线，但要 Rust 零依赖 + 更友好模板 + 链接检查内建（中文站配 Pagefind 搜索） | **Zola** |
| 网页编辑后台 + 内容结构校验 + 定制阅读器（综合首选） | **Astro + Pages CMS** |
| 组件化内容应用 + 编辑 UI、更强 schema 校验 | **Astro + Keystatic** |
| 出现付费/用户/VIP 需求 | 完整业务 → 动态方案（文档 02）；仅少数章节 → 混合付费墙（文档 01 §1.2） |
