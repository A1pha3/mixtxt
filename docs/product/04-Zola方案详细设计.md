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
> 文档版本：1.0 ｜ 创建：2026-08-17 ｜ 最后更新：2026-08-17

---

## 第一部分：Zola 与共享基础设计的字段映射

Zola 用「书 = section（目录 + `_index.md`）、章节 = page（`.md` 文件）」天然映射嵌套结构，因此共享模型里「books 用 JSON、chapters 用 MD」的拆分在 Zola 里被**合并**为一个目录树。字段映射如下：

| 共享模型（doc 03 §1.2） | Zola 实现 | 说明 |
|--------------------------|-----------|------|
| books（JSON 元数据） | 书目录下的 `_index.md` frontmatter | `title`/`description` 为顶层；`status`/`visibility`/`cover`/`copyrightStatus` 等自定义字段放 `[extra]` |
| chapters `status: published` | 章节 `draft = false` | Zola 无枚举；**已发布 = `draft=false`，其余（draft/review/archived）= `draft=true`（不参与构建）** |
| chapters `chapterNo: "002"` | 章节 `weight = 2`（整数升序） | Zola 用 `weight` 排序，前导零无必要 |
| chapters `summary` | 章节 `description`（顶层） | Zola 标准字段，自动用于 meta/feed |
| `visibility` / `copyrightStatus` | `extra.visibility` / `extra.copyrightStatus` | **`visibility=hidden` 的书 → 书 section `draft = true`**（Zola 官方：被 draft 的 section 其子孙页面一律不处理，见 §2.6 书示例）；构建期校验门控（见 §2.12） |
| `tags` | `[taxonomies] tags = [...]` | 在 config.toml 声明 taxonomy |
| releases（MD） | `content/releases/` section | 同结构 |
| prompts（MD，作者侧） | **仓库根 `prompts/`（在 `content/` 之外）** | 不是站点内容，不进构建/导航/搜索；AI 工作流直接读文件（见 §2.4/§2.13） |
| `seo`（共享模型可选字段） | **不逐章存储，由模板推导** | title/description block 已在 base.html/chapter.html 实现；存了反而造成"改 title 忘改 seo.title"的漂移 |
| site 配置（JSON） | `config.toml` + `config.extra` | 全站标题/描述/作者/GitHub 链接 |

**导航铁律不变**：章节导航不跨书，按 `weight` 升序算上一篇/下一篇（见 §2.8）。**草稿铁律不变**：`draft=true` 不参与 `zola build`、不进搜索索引、不进 sitemap/feed（共享铁律见 doc 03 §1.7，Zola 行为见 §2.8/§2.9）；**hidden 书 = 整本书 `draft=true`**（§2.6/§2.12）。**版权铁律不变**：`extra.copyrightStatus` 为 `unknown`/`private-draft` 的书籍，生产构建必须被校验脚本拦截（见 §2.12）。

---

## 第二部分：Zola 方案完整设计

### 2.1 结论与设计边界

```text
Zola + GitHub + Cloudflare Pages（单文件二进制、零依赖、Tera 模板、内置搜索索引）
```

保留的条件与共享模型一致：正文仍是 Markdown 文件、不需要数据库、只有你一个创建者、读者只读、Git 保存版本、Cloudflare Pages 自动构建发布。

**为什么 Zola 在这里是 Hugo 的更优平替：**
1. **单文件二进制、零依赖**：`zola build` 不需要 Go 工具链、不需要 Node、不需要插件生态；CI 里下一个二进制即可，比 Hugo extended 更轻。
2. **模板更友好**：Tera 是 Jinja2 风格，比 Go template 易读易写；作者/维护者更易改阅读器。
3. **内置能力齐全**：Sass 编译、代码高亮、`zola check` 链接检查（内/外链）全部内建；内置 Elasticlunr 搜索索引虽开箱即用，但**对中文分词不可用**（elasticlunr.js 2017 年后停更，中文站需外接 Pagefind，见 §2.9）——这是 Zola 唯一"内置但不适合中文"的能力。
4. **Git 工作流完全同 Hugo**：AI 生成 `.md` → `git push` → Cloudflare Pages 自动 `zola build` 发布。

**它不能满足的（与 Hugo 一致）：** 网页后台在线编辑（需接 Decap CMS / 自写编辑 UI，或换 Astro+Pages CMS）、读者网页版本切换（需按 tag 额外构建）、逐章 diff 页面。**内置 Elasticlunr 搜索对中文站不可用**（见 §2.9，中文搜索需接 Pagefind——这是与 Hugo 相比唯一"内置但不适合中文"的能力）。

### 2.2 系统总览

```mermaid
flowchart LR
    A["AI 生成草稿（.md + TOML frontmatter）"] --> B["作者修订 / zola serve --drafts 预览"]
    B --> C["Git commit & push"]
    C --> D["Cloudflare Pages 触发 zola build"]
    D --> E["校验脚本门控（版权/一致性/封面）"]
    E --> F["Zola 生成 HTML"]
    F --> F2["Pagefind 生成搜索索引"]
    F2 --> G["Cloudflare CDN"]
    G --> H["读者阅读网站"]
```

**一次章节发布如何流动：** AI 生成草稿（含 `draft=true`）→ 作者本地 `zola serve --drafts` 预览（注意：Zola 的 `build` 与 `serve` 默认都不含草稿，看草稿必须显式 `--drafts`）→ 改 `draft=false` + 提交 Git → push 触发 Cloudflare Pages `zola build` → 校验脚本先跑（失败则中断构建，旧版本仍在线）→ Zola 按 `weight` 排序生成书页/章节页、过滤 `draft=true`、生成 sitemap/feed → `npx pagefind --site public` 生成搜索索引 → CDN 发布。

> 注：上方 Mermaid 图需支持 Mermaid 的渲染器（GitHub、部分 IDE 插件）；纯 Markdown 阅读器会显示源码，不影响其余内容。

### 2.3 技术栈

```text
生成器:       Zola（Rust 单文件二进制，零运行时依赖）
模板:         Tera（Jinja2 风格）
内容格式:     Markdown + TOML frontmatter（+++ 包裹）
样式:         原生 Sass（Zola 内置编译）
站内搜索:     Pagefind（构建后扫描 public/，v1.5+ 原生中文分词；见 §2.9）
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

> **搜索依赖取舍**：Pagefind 需要 Node（`npx pagefind`，Cloudflare Pages 构建环境自带 Node）或下载其预编译二进制。想保持"纯零 Node"也可用 Zola 内置 Elasticlunr——但**它对中文分词不可用**（见 §2.9）。中文小说站建议接受 Pagefind 这一个依赖。

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
│   │   └── sanguo-scifi/         # 一本书 = 一个 section
│   │       ├── _index.md         # 书页：简介 + 章节目录（extra.* + sort_by=weight）
│   │       ├── 001-prologue.md   # 章节（weight=1, draft=false）
│   │       ├── 002-huangjin.md
│   │       └── ...
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
│   └── build.sh                  # 校验 + zola build + pagefind 封装
├── .gitignore                    # 忽略 public/（含 pagefind/ 产物）
└── README.md
```

**为什么书用嵌套目录（而非平铺）：** Zola 的 section 机制天然把「一本书 = 一个目录」，`_index.md` 即书元数据、目录下 `.md` 即章节；导航/上下篇自动限制在当前 section 内，零额外代码。这与 doc 03 §1.3 的「按书嵌套目录（Hugo 风格）」一致。

**为什么 prompts 在 `content/` 之外：** `content/` 里任何 `.md` 都会被 Zola 当页面处理；section 的 `render = false` 只关掉 section 自身页面，**不阻止子页面渲染**（官方确认，且 `render=false` 的页面仍会出现在 taxonomy 页）。prompts 是作者侧资产而非站点内容，放在仓库根 `prompts/` 才是零歧义的隔离——AI 工作流（§2.13）直接按路径读文件即可。

### 2.5 配置 config.toml

```toml
base_url = "https://mixtxt.example.com"
title = "Mixtxt · AI 改编小说"
description = "AI 辅助改编小说的单作者阅读站"
default_language = "zh"

# 内建能力
compile_sass = true          # sass/main.scss -> public/main.css
build_search_index = false   # 搜索用 Pagefind（构建后生成索引）；内置 elasticlunr 对中文不可用，勿开
generate_feeds = true        # 自动 RSS/Atom（需页面有 date）
minify_html = true           # 压缩 HTML（可选，按需开启）

# 分类法：书籍/章节都可打 tags（自动生成 /tags/ 页，可自建 taxonomy_list/taxonomy_single 模板覆盖）
taxonomies = [
  { name = "tags", feed = true },
]

[markdown]
highlight_code = true
highlight_theme = "github-dark"   # 代码高亮主题（小说站可设 none）

[extra]
author = "matrix"
github = "https://github.com/your/mixtxt"
copyright = "改编内容版权归原作者与作者所有；非公版内容仅作私人草稿。"
```

> **构建命令**：`zola build` 输出到 `public/`（默认排除草稿）。`zola serve --drafts` 本地预览草稿（默认不含草稿，需显式 `--drafts`）。`zola check` 校验内部与外部链接——**外部链接默认会发 HTTP 请求**，正文外链多时可加 `--skip-external-links`（见 §2.12）。

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

**章节：`content/books/sanguo-scifi/002-huangjin.md`**（page frontmatter）

```toml
+++
title = "黄巾初起"
description = "巨鹿星区的张角点燃第一枚信标，旧帝国的边境开始瓦解。"   # = summary
weight = 2                  # 排序用；与 extra.chapterNo、文件名数字前缀三处一致（validate 强制）
draft = false               # false = 已发布；true = 草稿/未发布
date = 2026-06-03T10:00:00+08:00
in_search_index = true      # 章节进 Pagefind 索引（默认 true，显式声明更清晰）
[taxonomies]
tags = ["三国", "科幻", "AI改编"]
[extra]
book = "sanguo-scifi"       # 冗余校验用，实际归属由目录决定
chapterNo = "002"           # 显示用章号（三位，与前导零一致）
wordCount = 3200
createdAt = "2026-06-03"
updatedAt = "2026-06-03"
[extra.ai]
model = "manual-or-ai-assisted"
prompt = "rewrite-style-guide"
humanEdited = true
+++
```

> 正文在 `+++` 之后的 Markdown 中书写。Zola 只识别固定顶层键（`title`/`description`/`date`/`weight`/`draft`/`slug`/`template`/`sort_by`/`in_search_index`/`taxonomies`/`extra` 等）；`status`/`visibility`/`cover`/`copyrightStatus`/`wordCount`/`ai` 等自定义字段必须放 `[extra]`，模板里用 `page.extra.xxx` 访问。
>
> **不存 `[extra.seo]`**：页面 title/description 已由 base.html/chapter.html 的 block 推导（`{chapterNo} {title} - {book} - {site}`），逐章存 seo 是死数据且会漂移（改了 title 忘改 seo.title）。共享模型的 `seo` 是可选字段，Zola 用模板推导即等价实现。

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

**base.html（骨架）**

```html
<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}{{ config.title }}{% endblock %}</title>
  <meta name="description" content="{% block description %}{{ config.description }}{% endblock %}">
  <link rel="stylesheet" href="{{ get_url(path='main.css') }}">
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
    {% if not page.draft %}
    <li><a href="{{ page.permalink }}">{{ page.extra.chapterNo }} {{ page.title }}</a></li>
    {% endif %}
  {% endfor %}
  </ol>
</article>
{% endblock %}
```

**chapter.html（章节页：正文 + 上下篇导航）**

```html
{% extends "base.html" %}
{% block title %}{{ page.extra.chapterNo }} {{ page.title }} - {{ section.title }} - {{ config.title }}{% endblock %}
{% block description %}{{ page.description }}{% endblock %}
{% block content %}
<article class="chapter" data-pagefind-body>
  <header><h1>{{ page.extra.chapterNo }} {{ page.title }}</h1></header>
  {{ page.content | safe }}
  <nav class="chapter-nav">
    {% if page.lower %}<a href="{{ page.lower.permalink }}">← 上一章</a>{% endif %}
    <a href="{{ section.permalink }}">目录</a>
    {% if page.higher %}<a href="{{ page.higher.permalink }}">下一章 →</a>{% endif %}
  </nav>
</article>
{% endblock %}
```

> `data-pagefind-body`：Pagefind（§2.9）只索引显式标记的元素——章节正文才进搜索索引，导航/页脚/首页不索引。这是主搜索方案的必需标记，不是预留。

### 2.8 章节导航 prev/next（不跨书）

Zola 里章节是 book section 的子页面，排序由 `_index.md` 的 `sort_by = "weight"` 决定（升序）。在 `chapter.html` 中：

- `page.lower` → 当前 section 内排序值更小（`weight` 更小）的上一章
- `page.higher` → 当前 section 内排序值更大（`weight` 更大）的下一章

> **命名注意**：`lower`/`higher` 是 Zola 0.16+ 的正式命名（旧版叫 `earlier`/`later`，**0.16 起已移除**）。用对命名后方向固定：`lower`=上一章、`higher`=下一章，无需任何交换。

由于限制在当前 section，**天然不跨书**，与共享铁律一致。草稿（`draft=true`）不出现在 `lower`/`higher` 与 `section.pages` 中，因此导航永远指向已发布章节。

### 2.9 站内搜索（Pagefind，中文可用的唯一可靠静态方案）

**为什么不用 Zola 内置 Elasticlunr：** Zola 的 `build_search_index` 生成 Elasticlunr 索引，但：
- elasticlunr.js 前端库自 2017 年基本停更，**对中文分词不可用**（官方文档明确"非英语语言需额外引入对应 stemmer"；中文没有可用 stemmer，多位中文站点实测查询命中率不可用）；
- 它把查询按空格/连字符切词，中文整句输入时前后端分词不一致，结果随机。

中文小说站唯一可靠的静态搜索是 **Pagefind**（v1.5+ 原生 CJK 分词，构建时索引、浏览器端检索、分块加载，与 doc 03 推荐方案一致）：

```bash
zola build                          # 先生成 HTML
npx pagefind --site public          # 再扫描 public/ 生成 public/pagefind/ 索引
```

- 索引范围由 `data-pagefind-body` 决定（§2.7 章节正文已标记；`data-pagefind-ignore` 可排除特定元素）。
- **草稿天然不进索引**：`draft=true` 不参与构建，Pagefind 只扫构建产物，与共享草稿铁律一致。
- `pagefind/` 产物生成在 `public/` 下，**不入库**（.gitignore 忽略整个 public/）。
- **依赖取舍**：Pagefind 需要 Node（`npx`）或预编译二进制；Cloudflare Pages 构建环境自带 Node，本地装 Node 或下载二进制均可。这是 Zola 方案唯一引入的外部搜索依赖——换取中文可用的全文搜索，值得。

**搜索页 `content/search.md`（`template = "search.html"`）**，用 Pagefind 官方 JS API 手写一个最小实现（`textContent` 渲染天然防 XSS）：

```html
{% extends "base.html" %}
{% block content %}
<h1>搜索</h1>
<input id="q" type="search" placeholder="搜索章节标题或正文…" oninput="doSearch(this.value)">
<ul id="results"></ul>
<script>
async function doSearch(term) {
  const box = document.getElementById("results");
  term = term.trim();
  if (!term) { box.innerHTML = ""; return; }
  const pagefind = await import("/pagefind/pagefind.js");
  const { results } = await pagefind.search(term);
  box.innerHTML = "";
  for (const r of results.slice(0, 20)) {
    const data = await r.data();
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = data.url;
    a.textContent = data.meta.title;   // textContent 而非 innerHTML：防注入
    li.append(a);
    box.append(li);
  }
}
</script>
{% endblock %}
```

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

阅读工具栏（字号/行距/主题/宽度）用原生 JS + `localStorage`（同 doc 03 §2.10），`zola build` 产出的纯静态页同样适用。

### 2.11 部署（Cloudflare Pages）

Cloudflare Pages **原生支持 Zola**（v2 构建环境内置 Zola，默认 0.22.1；`ZOLA_VERSION` 可覆盖为任意 ≥0.5 的版本）：

```text
Framework preset: 无（或 Zola）
Build command:    if [ "$CF_PAGES_BRANCH" = "main" ]; then zola build && npx pagefind --site public; else zola build --base-url "$CF_PAGES_URL" && npx pagefind --site public; fi
Build output:     public
Root directory:   /
Environment variables: ZOLA_VERSION = 0.23.3   # 固定版本，避免漂移（2026-08-12 官方稳定版，修复低危安全漏洞）
```

- 构建命令用 **Cloudflare 官方推荐的分支判断**：生产分支（main）用 `config.toml` 的 `base_url`；预览分支（PR 预览）用 `CF_PAGES_URL` 动态覆盖，避免预览页资源加载失败。`&&` 串联 `pagefind` 生成搜索索引（构建环境自带 Node）。
- `static/_headers` 缓存策略同 doc 03 §2.12：HTML `max-age=3600`，`/covers/*`、`/images/*`、`/pagefind/*` 等设 `max-age=31536000, immutable`，并加安全响应头。
- 免费层限制（每项目 500 构建/月、20,000 文件、25 MiB）与构建频率策略同 doc 03 §1.5。

**可选 GitHub Actions 兜底**（本地先构建门控，避免坏构建上线）：

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
      - run: python3 scripts/validate_content.py
      - run: zola check
      - run: zola build
      - run: npx pagefind --site public
      - uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CF_API_TOKEN }}
          accountId: ${{ secrets.CF_ACCOUNT_ID }}
          projectName: mixtxt
          directory: public
```

### 2.12 内容校验脚本（Python + tomllib，无依赖）

Zola 不像 Astro 有 Content Collections schema 强校验，所以用 `scripts/validate_content.py`（Python 3.11+ 内置 `tomllib`，零依赖）在构建前强制共享硬约束。逻辑节选：

```python
import tomllib, pathlib, sys, re, datetime

ROOT = pathlib.Path(".")
content = ROOT / "content"
errors = []
chapterNo_re = re.compile(r"^[0-9]{3,}$")      # 至少三位，支持上千章（1000+）
slug_re = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
chapter_file_re = re.compile(r"^(?P<no>\d{3,})(?:-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*))?\.md$")

def parse_frontmatter(path: pathlib.Path) -> dict:
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
    """date 接受 TOML datetime 或 YYYY-MM-DD / RFC3339 字符串；官方建议不要用引号包 RFC3339"""
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

    # 章节校验
    seen_no = set()
    for ch in book_dir.glob("*.md"):
        if ch.name == "_index.md":
            continue
        fm = parse_frontmatter(ch)
        extra = fm.get("extra", {})
        no = extra.get("chapterNo", "")
        weight = fm.get("weight")
        # 文件名：{三位以上数字}(-slug)?.md
        fm_name = chapter_file_re.fullmatch(ch.name)
        if not fm_name:
            errors.append(f"{ch.name}: 文件名须为 {{章节号}}(-{{slug}}).md，如 002-huangjin.md")
            continue
        slug_part = fm_name.group("slug")
        if slug_part and not slug_re.fullmatch(slug_part):
            errors.append(f"{ch.name}: 文件名 slug 部分不合法（仅小写字母/数字/连字符）")
        no_ok = bool(no) and bool(chapterNo_re.fullmatch(no))
        if not no_ok:
            errors.append(f"{ch}: chapterNo 必须为至少三位数字 {no!r}")
        if not isinstance(weight, int):
            errors.append(f"{ch}: 缺少 weight 或非整数（排序必需，须与 chapterNo 一致）")
        elif no_ok:
            # 单一真源：文件名前缀 == weight == chapterNo，三者漂移会让排序/URL/显示编号错位
            if int(no) != weight or fm_name.group("no") != no:
                errors.append(f"{ch}: 文件名前缀({fm_name.group('no')})/weight({weight})/chapterNo({no}) 三者必须一致")
        if no in seen_no:
            errors.append(f"{ch}: 同书重复 chapterNo {no}")
        seen_no.add(no)
        # 日期（feed/sitemap 需要）
        if "date" in fm:
            check_date(ch, fm["date"])
        # 已发布章节（draft=false 或缺省）必须挂在可公开的书下；草稿（draft=true）不受此限
        is_published = (fm.get("draft", False) is False)
        if is_published and cr in ("unknown", "private-draft"):
            errors.append(f"{ch}: 已发布章节但所属书 copyrightStatus={cr} 不允许公开构建")

if errors:
    print("内容校验失败：")
    print("\n".join(f"- {e}" for e in errors))
    sys.exit(1)
print("content validation passed")
```

`scripts/build.sh` 串联校验、构建与搜索索引：

```bash
#!/usr/bin/env bash
set -euo pipefail
python3 scripts/validate_content.py   # 失败则中断，旧版本保持在线
zola build
npx pagefind --site public            # 生成搜索索引（需 Node；或换成 pagefind 二进制）
```

> 实际覆盖清单（与脚本逐条对应）：frontmatter 闭合与 TOML 合法、文件名 `{三位以上数字}(-slug)?.md`、slug 合法、无重复 chapterNo、**文件名前缀/weight/chapterNo 三者一致**、hidden 书必须设 section `draft=true`、copyrightStatus/visibility 约束、封面存在、date 格式（TOML datetime 或字符串）。共享模型里 releases 的 semver、`ai.prompt` 引用等低风险规则首版不在此脚本硬拦（由目录结构与 `zola check` 兜底），需要时再加。AI 实现项目时不要随意改字段名；改了必须同步模板与示例。

### 2.13 AI 创作工作流（Zola 适配）

首版不把 AI 接口接到站内，流程与共享模型一致：

1. 选原作与改编方向 → 用仓库根 `prompts/` 里的提示词模板生成章节草稿（`prompts/<slug>.md`，直接按路径读）。
2. 草稿写成 `.md`，默认 `draft = true`（不发布），`extra.ai` 记录模型/prompt/是否人工修订。
3. 作者本地 `zola serve --drafts` 预览草稿，修订事实/节奏/人物动机。
4. 确认无误后改 `draft = false`，`git commit` + `git push` 触发 Cloudflare Pages 构建。
5. 构建前 `validate_content.py` 门控版权/一致性/封面，`zola check` 查死链（**默认连外部链接也检查**——会发 HTTP 请求，正文外链多时 CI/本地可用 `zola check --skip-external-links`）。

> **发布判定**：Zola 用 `draft` 布尔表示发布（`false` = 已发布），等价于共享模型的 `status == "published"`。AI 自动化流水线可批量写 `draft=true` 草稿，再由人工（或受控脚本）翻 `draft=false`——**AI 负责生成草稿，人/受控步骤决定发布**，与 doc 03 §1.4 / §2.13 铁律一致。

### 2.14 版本管理（同共享模型）

完全复用 doc 03 §1.4 三层模型，Git 即是正本版本系统：

```bash
git add content/books/sanguo-scifi/002-huangjin.md
git commit -m "feat: 黄巾初起"
git tag v0.2.0 && git push origin v0.2.0
```

给读者看版本变化用 `content/releases/` 版本说明页（不替代 Git 逐字历史）。按 Git tag 部署历史版本（子路径 `/versions/v0.1.0/`）属于第二阶段。

### 2.15 实施计划

- **Phase 0 初始化**：`zola init`、写 `config.toml`、基础 Sass、示例内容。验收：`zola serve` / `zola build` 通过。
- **Phase 1 内容结构与路由**：书 section + 章节 page、`book.html`/`chapter.html`、首页书籍列表、上下篇导航。验收：公开内容显示、草稿不显示、上/下一篇正确。
- **Phase 2 校验与质量**：`validate_content.py`、`zola check`、版权门控。验收：坏内容被拦截、死链被报出。
- **Phase 3 阅读体验**：Sass 变量、暗色/字号/行距/宽度、`localStorage`、移动端适配。
- **Phase 4 搜索与 SEO**：内置搜索页、RSS/feed、sitemap、meta/OG。
- **Phase 5 部署**：连 Cloudflare Pages、固定 `ZOLA_VERSION`、自定义域名、缓存头、构建次数监控。

### 2.16 风险与应对

| 风险 | 应对 |
|------|------|
| Zola 无 schema 强校验，字段易乱 | `validate_content.py` 构建前门控（含文件名/weight/chapterNo 一致性） |
| 私有草稿误入公开构建 | 校验脚本拦截 `copyrightStatus=unknown/private-draft`；本地 `zola serve --drafts` 仅作者可见 |
| hidden 书被构建公开访问 | hidden 书必须设 section `draft=true`（整本书不进构建），validate 强制 |
| 草稿进入搜索/导航 | `draft=true` 自动被 Zola 排除；Pagefind 只扫构建产物 |
| 中文搜索不可用 | 内置 Elasticlunr 对中文分词不可用 → 用 Pagefind（v1.5+ 原生 CJK），见 §2.9 |
| prompts 被当作页面渲染 | prompts 放 `content/` 之外的仓库根 `prompts/`，零 Zola 语义依赖 |
| 外链检查拖慢/中断构建 | `zola check --skip-external-links` 跳过外部链接（内部死链仍查） |
| Cloudflare 构建次数不够 | 本地预览后集中 push，控制频率（同 §1.5） |
| 文件数超限 | 控制历史版本页数量，必要时拆站 |
| 原作版权不清 | `unknown` 不允许公开构建 |
| 版本漂移 | 固定 `ZOLA_VERSION`，升级前本地 `zola build` |
| 构建失败读者看到旧版 | GitHub Actions 本地构建门控，push 前先跑 build |

### 2.17 与 Astro + Pages CMS / Hugo 的取舍

| 对比项 | Zola | Hugo | Astro + Pages CMS |
|--------|------|------|-------------------|
| 语言/依赖 | Rust 单文件，零依赖 | Go 单文件（extended） | Node 生态，较重 |
| 模板 | Tera（Jinja2 风，好写） | Go template（强但难读） | Astro 组件（最灵活） |
| 中文搜索 | ✅ Pagefind（需 Node/二进制） | ❌ 需外接 | ✅ Pagefind（同） |
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

```python
#!/usr/bin/env python3
"""AI 章节生成 harness（Python 3.11+，零第三方依赖）。

用法（OpenAI 兼容 API）：
  LLM_API_KEY=sk-... LLM_MODEL=gpt-4o-mini \
    python3 scripts/generate_chapters.py --book sanguo-scifi --count 3 \
    --style "节奏明快，每章 3000 字左右"
  # --dry-run：只打印将生成的文件与 frontmatter 模板，不调用 LLM
"""
import argparse, datetime, json, os, pathlib, re, subprocess, sys, tomllib, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(".")
BOOKS = ROOT / "content" / "books"
ALLOWED_COPYRIGHT = ("public-domain", "authorized")
SYSTEM_PROMPT = """你是小说章节作者。只输出章节正文（Markdown），
不要输出 frontmatter、不要解释、不要用代码块包裹正文。
要求：{style}
正文不超过 4000 字，结尾留钩子便于下一章衔接。"""

def llm_chat(system: str, user: str) -> str:
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    key = os.environ["LLM_API_KEY"]
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
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"LLM API 错误 {e.code}：{e.read().decode(errors='replace')[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"LLM 调用失败：{e}")
        sys.exit(1)
    return data["choices"][0]["message"]["content"].strip()

def toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') \
                 .replace("\n", "\\n") + '"'

def book_copyright(book_dir: pathlib.Path) -> str:
    """读书 _index.md 的 extra.copyrightStatus；解析失败按 unknown 处理（拒绝生成）。"""
    m = re.match(r"^\+\+\+\s*\n(.*?)\n\+\+\+",
                 (book_dir / "_index.md").read_text(encoding="utf-8"), re.S)
    if not m:
        return "unknown"
    try:
        return tomllib.loads(m.group(1)).get("extra", {}).get("copyrightStatus", "unknown")
    except tomllib.TOMLDecodeError:
        return "unknown"

def make_frontmatter(weight: int, title: str, desc: str, body: str,
                     book: str, now: datetime.datetime) -> str:
    fmt = (
        "+++\n"
        'title = {title}\n'
        'description = {desc}\n'
        "weight = {weight}\n"
        "draft = true\n"
        "date = {date}\n"          # 无引号 TOML datetime（Zola 官方：不要用引号包日期）
        "in_search_index = true\n"
        "[taxonomies]\n"
        'tags = ["AI改编"]\n'
        "[extra]\n"
        'book = "{book}"\n'
        'chapterNo = "{no:03d}"\n'
        "wordCount = {words}\n"
        'createdAt = "{ymd}"\n'
        'updatedAt = "{ymd}"\n'
        "[extra.ai]\n"
        'model = "{model}"\n'
        'prompt = "harness-cli"\n'
        "humanEdited = false\n"
        "+++\n"
    )
    return fmt.format(
        title=toml_str(title), desc=toml_str(desc),
        weight=weight, date=now.isoformat(timespec="seconds"),
        book=book, no=weight, words=len(body),
        ymd=now.date().isoformat(),
        model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
    )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True, help="书 slug，对应 content/books/<slug>/")
    ap.add_argument("--count", type=int, required=True, help="生成章节数")
    ap.add_argument("--title", help="书标题（默认读 _index.md 的 title）")
    ap.add_argument("--style", default="节奏明快，每章 3000 字左右",
                    help="风格要求，会拼进系统提示词")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--parallel", type=int, default=4,
                    help="并发生成数（默认 4，上百章时建议 8-16）")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9-]+", args.book):
        print(f"书 slug 非法：{args.book}（只允许小写字母/数字/连字符）")
        return 1

    book_dir = BOOKS / args.book
    idx = book_dir / "_index.md"
    if not idx.exists():
        print(f"书不存在：{idx}（先建书目录与 _index.md）")
        return 1

    # fail-fast：版权未确认的书直接拒绝——不调用 LLM、不写文件，
    # 避免白花 API 费用后才发现生成的文件注定被 validate_content.py 拦下
    cr = book_copyright(book_dir)
    if cr not in ALLOWED_COPYRIGHT:
        print(f"书 {args.book} 的 copyrightStatus={cr}，不允许 AI 生成（需 public-domain/authorized）")
        return 1

    # 起始序号 = 现有章节最大 weight + 1（兼容 003.md 与 003-huangjin.md 命名）
    weights = [int(p.stem.split("-")[0])
               for p in book_dir.glob("*.md")
               if p.name != "_index.md" and p.stem.split("-")[0].isdigit()]
    start = max(weights, default=0) + 1

    if args.dry_run:
        for w in range(start, start + args.count):
            print(f"[dry-run] 将生成 {book_dir.name}/{w:03d}.md（draft=true）")
        print(make_frontmatter(start, "示例章标题", "示例摘要", "正文…",
                               args.book, datetime.datetime.now().astimezone()))
        return 0

    now = datetime.datetime.now().astimezone()

    def gen_one(w: int) -> int:
        body = llm_chat(
            SYSTEM_PROMPT.format(style=args.style),
            f"这是《{args.title or args.book}》的第 {w} 章，请写正文。",
        )
        title = f"第 {w} 章"          # 人工修订时可改成真实标题
        desc = (body.split("\n")[0][:60] or f"第 {w} 章")
        (book_dir / f"{w:03d}.md").write_text(
            make_frontmatter(w, title, desc, body, args.book, now)
            + "\n" + body, encoding="utf-8")
        return w

    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        futures = [pool.submit(gen_one, w) for w in range(start, start + args.count)]
        for fut in as_completed(futures):
            print(f"[{fut.result():03d}] 完成")

    print("生成完成，运行校验：")
    return subprocess.run([sys.executable, "scripts/validate_content.py"]).returncode

if __name__ == "__main__":
    sys.exit(main())
```

**使用前提与边界：**
- 书目录 `content/books/<slug>/_index.md` 必须已存在。**脚本生成前先读 `extra.copyrightStatus`**：非 `public-domain`/`authorized` 立即拒绝（fail-fast）——不调 LLM、不写文件，版权门控从"生成后被 validate 拦"提前到"生成前拒绝"。
- 生成的是 `draft=true` 草稿，不进构建/搜索/导航；作者 `zola serve --drafts` 预览修订后，改 `draft=false` 再 push 发布——**AI 负责生成草稿、人决定发布**的铁律由脚本结构强制保证。
- `date` 输出为**无引号 TOML datetime**（`2026-06-03T10:00:00+08:00`）——Zola 官方明确不要用引号包日期；这与 §2.6 章节示例一致。
- 文件名是 `{weight:03d}.md`（URL 为 `/books/<slug>/<weight>/`）；想要语义化 URL，把文件名改成 `003-huangjin.md` 即可（slug 取自文件名）。validate 强制文件名前缀/weight/chapterNo 三者一致，改名后记得同步 chapterNo 与 weight。
- `--dry-run` 不调用 LLM、不写文件，用于先看会生成什么。
- `--parallel N` 并发调用 LLM（默认 4，上百章建议 8-16）——并发下完成顺序不定，但章节号由脚本统一分配，结果一致。
- 每章标题初始为"第 N 章"，`description` 取正文首行——**这两处都需要作者修订**，脚本故意不猜。

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
