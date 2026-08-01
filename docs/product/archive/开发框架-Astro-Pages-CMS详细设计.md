# Astro + Pages CMS 小说创作网站详细设计

> 文档类型：完整架构设计与 AI 实施规格
>
> 目标需求：[AI改编小说网需求.md](./AI改编小说网需求.md)
>
> 推荐组合：Astro + Pages CMS + Pagefind + GitHub + Cloudflare Pages
>
> 关联文档：[AI改编小说网架构.md](./AI改编小说网架构.md)、[开发框架-Astro-Keystatic详细方案.md](./开发框架-Astro-Keystatic详细方案.md)、[开发框架方案对比与推荐.md](./开发框架方案对比与推荐.md)

## 一、结论

**这套方案的目标不是做一个复杂的小说平台，而是做一个足够优秀、足够轻、长期不容易后悔的单作者 AI 改编小说创作网站。**

最终推荐：

```text
Astro + Pages CMS + Pagefind + GitHub + Cloudflare Pages
```

它保留了你最在意的几个条件：

- 小说正文仍然是 Markdown 文件。
- 不需要数据库。
- 只有你一个创建者，读者只读。
- Git 保存版本历史。
- Cloudflare Pages 自动构建发布。

它比纯 Hugo 更好的地方在于：Astro 更适合做定制阅读器和内容应用；Pages CMS 给 GitHub 仓库里的内容补上网页编辑界面；Pagefind 让站内搜索不用后端服务也能做得像样。

一句话判断：

```text
如果 Hugo 是“最轻的静态小说展示站”，Astro + Pages CMS 就是“仍然静态，但已经具备优秀创作和阅读体验的小说内容应用”。
```

## 二、设计边界

这份文档默认项目处于第一阶段：单作者、免费公开阅读、无用户系统、无数据库。

### 2.1 本方案要做什么

| 目标 | 说明 |
|------|------|
| AI 改编小说内容管理 | 作者通过 Pages CMS 或本地编辑器维护书籍、章节、版本说明、提示词模板 |
| 公开阅读网站 | 读者可查看书籍列表、书籍详情、章节正文、上一章 / 下一章、搜索结果 |
| 静态构建发布 | Astro 构建 HTML，Pagefind 生成搜索索引，Cloudflare Pages 发布 |
| Git 版本管理 | 所有内容改动进入 Git commit，可回滚、可打 tag、可审计 |
| 优秀阅读体验 | 移动端适配、暗色模式、字号行距设置、目录导航、搜索、SEO |

### 2.2 本方案暂时不做什么

| 不做 | 原因 |
|------|------|
| 用户注册 / 登录 | 会引入服务端状态和权限系统 |
| 付费章节 / VIP | 静态站无法可靠保护内容 |
| 评论 / 点赞 / 收藏 | 需要数据库或第三方服务，后置 |
| 在线 AI 生成并保存 | 需要调用模型 API、鉴权、配额、存储，第二阶段再做 |
| 多作者协作后台 | Pages CMS 能编辑 Git 内容，但不是完整多角色 CMS |
| 读者查看逐字历史 diff | Git 能保存历史，但网页 diff 需要额外生成逻辑，后置 |

### 2.3 成功标准

第一版完成后，应满足：

- 作者可以通过 Pages CMS 新增书籍、章节、版本说明和提示词模板。
- 作者也可以绕过 CMS，直接在本地编辑 Markdown。
- 新增内容 push 到 GitHub 后，Cloudflare Pages 自动构建。
- 读者访问首页能看到书籍、最近更新、搜索入口。
- 读者进入书籍页能看到简介、标签、状态、章节目录。
- 读者进入章节页能顺畅阅读，并能跳转上一章 / 下一章。
- 草稿章节不会出现在公开页面、RSS、sitemap、搜索索引中。
- 搜索能查到已发布书籍和章节。
- 构建产物是静态文件，不依赖运行时数据库。

## 三、系统总览

这套系统有四条主线：创作、内容、构建、阅读。先把边界拆清楚，后面实现就不容易乱。

```mermaid
flowchart LR
    A["AI 生成草稿"] --> B["作者修订"]
    B --> C["Pages CMS 或本地编辑器"]
    C --> D["Markdown / JSON 文件"]
    D --> E["GitHub 仓库"]
    E --> F["Cloudflare Pages 构建"]
    F --> G["Astro 生成 HTML"]
    G --> H["Pagefind 生成搜索索引"]
    H --> I["Cloudflare CDN"]
    I --> J["读者阅读网站"]
```

### 3.1 模块职责

| 模块 | 职责 | 不负责 |
|------|------|--------|
| Astro | 路由、页面生成、组件、阅读器 UI、静态资源组织 | 内容编辑后台、数据库 |
| Astro Content Collections | 读取内容文件、校验 schema、提供类型安全的数据查询 | Git 提交、CMS UI |
| Pages CMS | 编辑 GitHub 仓库里的内容和媒体文件 | 生成页面、托管站点、用户权限系统 |
| Pagefind | 扫描构建后的 HTML，生成静态搜索索引 | 服务端搜索、权限过滤 |
| GitHub | 保存内容正本、版本历史、tag、分支 | 页面渲染 |
| Cloudflare Pages | 拉取仓库、执行构建、发布静态站 | 内容编辑、数据存储 |

### 3.2 一次章节发布如何流动

以作者新增一章为例：

1. 作者用 AI 生成章节草稿。
2. 作者在 Pages CMS 中新建章节，填写书籍、章节号、标题、slug、摘要、状态和正文。
3. Pages CMS 把章节保存为 `src/content/chapters/sanguo-scifi-002-huangjin.md`。
4. 保存动作写回 GitHub，产生一次 commit。
5. Cloudflare Pages 监听到仓库变化，触发 build。
6. Astro 读取 `chapters` collection，过滤 `status === "published"` 的章节。
7. Astro 生成书页、章节页、标签页、RSS、sitemap。
8. Pagefind 扫描 `dist`，只索引已构建出的公开页面。
9. Cloudflare CDN 发布新版本，读者看到新章节。

这条路径里没有数据库，也没有运行时后端。真正的状态都在 Git 仓库和静态文件里。

## 四、推荐技术栈

```text
前端框架:       Astro
内容读取:       Astro Content Collections
内容编辑:       Pages CMS
正文格式:       Markdown with YAML frontmatter
站内搜索:       Pagefind
版本管理:       Git + GitHub
部署平台:       Cloudflare Pages
样式:           原生 CSS / CSS variables（首版不强依赖 UI 框架）
交互状态:       localStorage（阅读设置、最近阅读）
未来动态能力:   Cloudflare Pages Functions + D1 / KV / R2（后置）
```

首版不要引入数据库、GraphQL、在线 AI 接口、复杂状态管理库。项目最重要的是内容结构稳定和阅读体验顺滑。

### 4.1 推荐依赖与初始化命令

实现时建议用当前稳定版初始化 Astro，并把 lockfile 提交到 GitHub。不要在文档里锁死具体小版本，实际项目以初始化当天的稳定版本为准。

```bash
npm create astro@latest mixtxt-astro
cd mixtxt-astro
npm install
npm install -D pagefind gray-matter
```

`package.json` 至少包含：

```json
{
  "scripts": {
    "dev": "astro dev",
    "validate:content": "node scripts/validate-content.mjs",
    "build": "npm run validate:content && astro build && pagefind --site dist",
    "preview": "astro preview"
  },
  "dependencies": {
    "astro": "latest"
  },
  "devDependencies": {
    "gray-matter": "latest",
    "pagefind": "latest"
  }
}
```

说明：

- `pagefind` 在 `astro build` 之后运行，负责给 `dist/` 生成静态搜索索引。
- `gray-matter` 只给内容校验脚本使用，用来可靠读取 Markdown frontmatter。
- 首版使用 `src/pages/sitemap.xml.ts` 自定义 sitemap，确保 draft、hidden、prompts 默认不进入 sitemap；如果后续改用 `@astrojs/sitemap`，必须重新确认过滤规则。
- 如果改用 pnpm，命令可替换为 `pnpm create astro@latest`、`pnpm add -D pagefind gray-matter`。

`astro.config.mjs` 至少包含：

```js
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://mixtxt.example.com",
  output: "static",
});
```

`site` 必须和 `src/data/site.json` 的 `baseUrl` 保持一致，用于 canonical URL、RSS 链接和 sitemap 链接生成。

## 五、仓库结构

推荐项目目录：

```text
mixtxt-astro/
├── .pages.yml
├── astro.config.mjs
├── package.json
├── package-lock.json 或 pnpm-lock.yaml
├── functions/          # Cloudflare Pages Functions（后置，第二阶段启用）
├── public/
│   ├── covers/
│   ├── images/
│   │   └── chapters/
│   ├── fonts/
│   ├── favicon.svg
│   ├── robots.txt
│   └── _headers
├── src/
│   ├── content.config.ts
│   ├── data/
│   │   └── site.json
│   ├── content/
│   │   ├── books/
│   │   │   └── sanguo-scifi.json
│   │   ├── chapters/
│   │   │   ├── sanguo-scifi-001-prologue.md
│   │   │   ├── sanguo-scifi-002-huangjin.md
│   │   │   └── sanguo-scifi-003-luoyang.md
│   │   ├── releases/
│   │   │   └── sanguo-scifi-v0-1-0.md
│   │   └── prompts/
│   │       └── rewrite-style-guide.md
│   ├── lib/
│   │   ├── content.ts
│   │   ├── site.ts
│   │   ├── seo.ts
│   │   ├── dates.ts
│   │   └── reading.ts
│   ├── layouts/
│   │   ├── BaseLayout.astro
│   │   ├── ReaderLayout.astro
│   │   └── BookLayout.astro
│   ├── components/
│   │   ├── AppHeader.astro
│   │   ├── AppFooter.astro
│   │   ├── BookCard.astro
│   │   ├── BookMeta.astro
│   │   ├── ChapterList.astro
│   │   ├── ChapterNav.astro
│   │   ├── ReaderToolbar.astro
│   │   ├── SearchBox.astro
│   │   ├── TagList.astro
│   │   └── VersionBadge.astro
│   ├── pages/
│   │   ├── index.astro
│   │   ├── books/
│   │   │   ├── index.astro
│   │   │   ├── [book].astro
│   │   │   └── [book]/
│   │   │       └── [chapter].astro
│   │   ├── tags/
│   │   │   └── [tag].astro
│   │   ├── releases/
│   │   │   └── index.astro
│   │   ├── search.astro
│   │   ├── about.astro
│   │   ├── rss.xml.ts
│   │   ├── sitemap.xml.ts
│   │   └── 404.astro
│   └── styles/
│       ├── global.css
│       ├── reader.css
│       └── tokens.css
└── README.md
```

### 5.1 为什么章节文件不按书籍嵌套

Pages CMS 可以编辑 collection 和 subfolders，但为了让 AI 和 CMS 都更容易稳定实现，首版建议把章节统一放到：

```text
src/content/chapters/
```

文件名使用：

```text
{book}-{chapterNo}-{slug}.md
```

示例：

```text
sanguo-scifi-002-huangjin.md
```

这样做的好处：

- Pages CMS 新建文件的 filename 模板更简单。
- Astro 只需要按 `book` 字段过滤章节。
- Git 里仍然能一眼看出章节所属书籍。
- 将来如果章节很多，再迁移到子目录结构也不难。

## 六、内容模型

内容正本分为五类。需要注意：`site.json` 是全站配置文件，不作为 Astro Content Collection 注册；其余四类才进入 `src/content.config.ts`。

| 类型 | 路径 | 格式 | 用途 |
|-----------|------|------|------|
| site config | `src/data/site.json` | JSON | 网站标题、描述、作者、社交链接 |
| books | `src/content/books/*.json` | JSON | 书籍元数据 |
| chapters | `src/content/chapters/*.md` | Markdown + YAML frontmatter | 章节正文 |
| releases | `src/content/releases/*.md` | Markdown + YAML frontmatter | 发布版本说明 |
| prompts | `src/content/prompts/*.md` | Markdown + YAML frontmatter | AI 改编提示词模板 |

### 6.1 site

`src/data/site.json`：

```json
{
  "title": "MixTXT",
  "description": "用 AI 改编经典小说的个人创作站。",
  "author": "matrix",
  "defaultLanguage": "zh-CN",
  "baseUrl": "https://mixtxt.example.com",
  "github": "https://github.com/a1pha3/mixtxt",
  "copyright": "本站只公开公版作品或已获得授权的改编内容。"
}
```

### 6.2 books

`src/content/books/sanguo-scifi.json`：

```json
{
  "title": "三国演义：星火纪元",
  "slug": "sanguo-scifi",
  "original": "三国演义",
  "author": "罗贯中",
  "adaptor": "matrix + AI",
  "status": "serializing",
  "visibility": "public",
  "summary": "把东汉末年的群雄割据改写成星际文明崩塌后的权力重组。",
  "cover": "/covers/sanguo-scifi.webp",
  "tags": ["三国", "科幻", "AI改编"],
  "copyrightStatus": "public-domain",
  "startedAt": "2026-06-03",
  "updatedAt": "2026-06-03",
  "seo": {
    "title": "三国演义：星火纪元",
    "description": "一个 AI 辅助改编的三国科幻版本。"
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 书名 |
| slug | string | 是 | URL 标识，只用小写英文、数字、短横线 |
| original | string | 否 | 原作名称 |
| author | string | 否 | 原作作者 |
| adaptor | string | 否 | 改编者 |
| status | enum | 是 | `planning`、`serializing`、`completed`、`paused` |
| visibility | enum | 是 | `public`、`hidden` |
| summary | text | 是 | 简介 |
| cover | string | 否 | 封面路径 |
| tags | string[] | 否 | 标签 |
| copyrightStatus | enum | 是 | `public-domain`、`authorized`、`private-draft`、`unknown` |
| startedAt | date | 是 | 开始日期 |
| updatedAt | date | 是 | 更新时间 |
| seo | object | 否 | SEO 标题和描述 |

**`copyrightStatus` 与 `visibility` 约束**：`copyrightStatus` 为 `private-draft` 时，`visibility` 必须为 `hidden`；`copyrightStatus` 为 `unknown` 时，`visibility` 不能为 `public`。构建校验脚本会强制检查这些规则，违反时构建失败。

### 6.3 chapters

`src/content/chapters/sanguo-scifi-002-huangjin.md`：

```markdown
---
book: "sanguo-scifi"
chapterNo: "002"
title: "黄巾初起"
slug: "huangjin"
status: "published"
summary: "巨鹿星区的张角点燃第一枚信标，旧帝国的边境开始瓦解。"
wordCount: 3200
createdAt: "2026-06-03"
updatedAt: "2026-06-03"
ai:
  model: "manual-or-ai-assisted"
  prompt: "rewrite-style-guide"
  humanEdited: true
seo:
  title: "黄巾初起 - 三国演义：星火纪元"
  description: "巨鹿星区起事，帝国边境开始瓦解。"
---

## 一、边境信标

巨鹿星区的夜空没有月亮，只有一圈报废轨道炮留下的蓝白色残光。
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| book | string | 是 | 对应 book slug |
| chapterNo | string | 是 | 三位章节号，如 `001` |
| title | string | 是 | 章节标题 |
| slug | string | 是 | 章节 URL 标识 |
| status | enum | 是 | `draft`、`review`、`published`、`archived` |
| summary | text | 是 | 章节摘要 |
| wordCount | number | 否 | 字数，由构建脚本自动计算 |
| createdAt | date | 是 | 创建日期 |
| updatedAt | date | 是 | 更新时间 |
| ai | object | 否 | AI 使用记录 |
| seo | object | 否 | SEO 信息 |
| body | Markdown | 是 | 正文 |

公开页面只渲染 `status === "published"` 的章节。`draft`、`review`、`archived` 不能进入公开页面、RSS、sitemap 和 Pagefind 索引。

### 6.4 releases

`src/content/releases/sanguo-scifi-v0-1-0.md`：

```markdown
---
book: "sanguo-scifi"
version: "v0.1.0"
versionSlug: "v0-1-0"
title: "前三章试读版"
date: "2026-06-03"
gitTag: "v0.1.0"
---

这一版完成了世界观设定、楔子和黄巾初起两章。

后续版本会继续补齐洛阳线和曹操登场线。
```

版本说明只给读者看重要发布节点，不替代 Git 的逐字历史。

### 6.5 prompts

`src/content/prompts/rewrite-style-guide.md`：

```markdown
---
title: "经典小说科幻改写提示词"
slug: "rewrite-style-guide"
category: "rewrite"
status: "active"
updatedAt: "2026-06-03"
---

你是一名严肃文学改编作者。请保留原作人物关系和核心冲突，但把时代背景改写为星际文明衰退期。

要求：

- 不要照搬原文句子。
- 保留人物动机。
- 每章必须有明确场景推进。
- 避免解释设定，优先让设定从行动中出现。
```

提示词模板是作者侧内容，首版默认不公开；`prompts` collection 只服务创作管理和章节 `ai.prompt` 记录。未来如果公开，应作为“创作方法”页面展示，而不是把完整私有工作流直接暴露给读者。

## 七、Astro Content Collections

`src/content.config.ts`：

```ts
import { defineCollection } from "astro:content";
import { z } from "astro/zod";
import { glob } from "astro/loaders";

const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const chapterNoPattern = /^[0-9]{3}$/;

const seoSchema = z
  .object({
    title: z.string().optional(),
    description: z.string().optional(),
  })
  .optional();

const books = defineCollection({
  loader: glob({ pattern: "*.json", base: "./src/content/books" }),
  schema: z.object({
    title: z.string(),
    slug: z.string().regex(slugPattern),
    original: z.string().optional(),
    author: z.string().optional(),
    adaptor: z.string().optional(),
    status: z.enum(["planning", "serializing", "completed", "paused"]),
    visibility: z.enum(["public", "hidden"]).default("public"),
    summary: z.string(),
    cover: z.string().optional(),
    tags: z.array(z.string()).default([]),
    copyrightStatus: z.enum([
      "public-domain",
      "authorized",
      "private-draft",
      "unknown",
    ]),
    startedAt: z.string(),
    updatedAt: z.string(),
    seo: seoSchema,
  }),
});

const chapters = defineCollection({
  loader: glob({ pattern: "*.md", base: "./src/content/chapters" }),
  schema: z.object({
    book: z.string().regex(slugPattern),
    chapterNo: z.string().regex(chapterNoPattern),
    title: z.string(),
    slug: z.string().regex(slugPattern),
    status: z.enum(["draft", "review", "published", "archived"]),
    summary: z.string(),
    wordCount: z.number().int().nonnegative().optional(),
    createdAt: z.string(),
    updatedAt: z.string(),
    ai: z
      .object({
        model: z.string().optional(),
        prompt: z.string().optional(),
        humanEdited: z.boolean().default(true),
      })
      .optional(),
    seo: seoSchema,
  }),
});

const releases = defineCollection({
  loader: glob({ pattern: "*.md", base: "./src/content/releases" }),
  schema: z.object({
    book: z.string().regex(slugPattern),
    version: z.string(),
    versionSlug: z.string().regex(slugPattern),
    title: z.string(),
    date: z.string(),
    gitTag: z.string().optional(),
  }),
});

const prompts = defineCollection({
  loader: glob({ pattern: "*.md", base: "./src/content/prompts" }),
  schema: z.object({
    title: z.string(),
    slug: z.string().regex(slugPattern),
    category: z.enum(["rewrite", "style", "outline", "character", "review"]),
    status: z.enum(["active", "archived"]),
    updatedAt: z.string(),
  }),
});

export const collections = {
  books,
  chapters,
  releases,
  prompts,
};
```

这段 schema 是实现时的硬约束。AI 实现项目时，不应随意改字段名；如果要改，必须同时更新 Pages CMS 配置、页面查询逻辑和示例内容。

`src/data/site.json` 不在这里注册。它由 `src/lib/site.ts` 直接读取；字段完整性由 `scripts/validate-content.mjs` 检查。

## 八、内容查询工具

建议把全站配置和 collection 查询分开：`site.json` 通过普通 JSON import 读取，books、chapters、releases、prompts 通过 Astro Content Collections 查询。这样可以避免把单个配置文件误当成 collection，后续页面类型也更清楚。

`src/lib/site.ts`：

```ts
import site from "../data/site.json";

export function getSiteConfig() {
  return site;
}
```

`src/lib/content.ts` 只处理 collection，不要在每个页面里重复写过滤和排序。

```ts
import { getCollection } from "astro:content";

export async function getPublicBooks() {
  const books = await getCollection("books");
  return books
    .filter((book) => book.data.visibility === "public")
    .sort((a, b) => b.data.updatedAt.localeCompare(a.data.updatedAt));
}

export async function getBookBySlug(slug: string) {
  const books = await getCollection("books");
  return books.find(
    (book) => book.data.slug === slug && book.data.visibility === "public"
  );
}

export async function getPublishedChapters(bookSlug?: string) {
  const chapters = await getCollection("chapters");
  return chapters
    .filter((chapter) => chapter.data.status === "published")
    .filter((chapter) => !bookSlug || chapter.data.book === bookSlug)
    .sort((a, b) => a.data.chapterNo.localeCompare(b.data.chapterNo));
}

export async function getRecentChapters(limit = 10) {
  const chapters = await getPublishedChapters();
  return chapters
    .sort((a, b) => b.data.updatedAt.localeCompare(a.data.updatedAt))
    .slice(0, limit);
}

export async function getChapterNav(bookSlug: string, chapterSlug: string) {
  const chapters = await getPublishedChapters(bookSlug);
  const index = chapters.findIndex((chapter) => chapter.data.slug === chapterSlug);
  return {
    current: chapters[index] ?? null,
    prev: index > 0 ? chapters[index - 1] : null,
    next: index >= 0 && index < chapters.length - 1 ? chapters[index + 1] : null,
    chapters,
  };
}

export async function getAllTags() {
  const books = await getPublicBooks();
  return [...new Set(books.flatMap((book) => book.data.tags))].sort();
}
```

所有公开页面都必须使用这些工具函数，确保草稿过滤规则一致。

## 九、Pages CMS 配置

Pages CMS 通过仓库根目录的 `.pages.yml` 读取配置。它只负责编辑文件，不替代 Astro、GitHub 或 Cloudflare Pages。

### 9.1 完整 `.pages.yml`

```yaml
media:
  - name: covers
    label: Covers
    input: public/covers
    output: /covers
    rename: safe
    extensions: [jpg, jpeg, png, webp]
  - name: chapter_images
    label: Chapter Images
    input: public/images/chapters
    output: /images/chapters
    rename: safe
    extensions: [jpg, jpeg, png, webp, svg]

components:
  seo:
    type: object
    label: SEO
    fields:
      - name: title
        label: SEO 标题
        type: string
      - name: description
        label: SEO 描述
        type: text

content:
  - name: site
    label: 网站设置
    type: file
    path: src/data/site.json
    format: json
    fields:
      - name: title
        label: 网站名称
        type: string
        required: true
      - name: description
        label: 网站描述
        type: text
        required: true
      - name: author
        label: 作者
        type: string
        required: true
      - name: defaultLanguage
        label: 默认语言
        type: string
      - name: baseUrl
        label: 站点地址
        type: string
        required: true
      - name: github
        label: GitHub 地址
        type: string
      - name: copyright
        label: 版权说明
        type: text

  - name: books
    label: 书籍
    type: collection
    path: src/content/books
    format: json
    filename: "{slug}.json"
    view:
      fields: [title, status, visibility, updatedAt]
      primary: title
      sort: [updatedAt, title]
      search: [title, slug, summary]
      default:
        sort: updatedAt
        order: desc
    fields:
      - name: title
        label: 书名
        type: string
        required: true
      - name: slug
        label: Slug
        type: string
        required: true
        pattern:
          regex: "^[a-z0-9]+(-[a-z0-9]+)*$"
          message: "只能使用小写英文、数字和短横线"
      - name: original
        label: 原作
        type: string
      - name: author
        label: 原作作者
        type: string
      - name: adaptor
        label: 改编者
        type: string
      - name: status
        label: 连载状态
        type: select
        required: true
        options:
          values:
            - name: planning
              label: 计划中
            - name: serializing
              label: 连载中
            - name: completed
              label: 已完结
            - name: paused
              label: 暂停
      - name: visibility
        label: 可见性
        type: select
        required: true
        options:
          values:
            - name: public
              label: 公开
            - name: hidden
              label: 隐藏
      - name: summary
        label: 简介
        type: text
        required: true
      - name: cover
        label: 封面
        type: image
        options:
          media: covers
      - name: tags
        label: 标签
        type: string
        options:
          multiple: true
        # 自由输入标签，不限制选项；如需预设标签可改回 select + values
      - name: copyrightStatus
        label: 版权状态
        type: select
        required: true
        options:
          values:
            - name: public-domain
              label: 公版
            - name: authorized
              label: 已授权
            - name: private-draft
              label: 私人草稿
            - name: unknown
              label: 未确认
      - name: startedAt
        label: 开始日期
        type: date
        required: true
      - name: updatedAt
        label: 更新日期
        type: date
        required: true
        readonly: true
        # 由构建脚本自动更新，作者无需手动修改
      - name: seo
        label: SEO
        component: seo

  - name: chapters
    label: 章节
    type: collection
    path: src/content/chapters
    format: yaml-frontmatter
    filename: "{book}-{chapterNo}-{slug}.md"
    view:
      fields: [title, book, chapterNo, status, updatedAt]
      primary: title
      sort: [book, updatedAt]
      search: [title, summary, book]
      default:
        sort: updatedAt
        order: desc
    fields:
      - name: book
        label: 所属书籍
        type: reference
        required: true
        options:
          collection: books
          search: "title,slug,summary"
          value: "{slug}"
          label: "{title}"
      - name: chapterNo
        label: 章节号
        type: string
        required: true
        pattern:
          regex: "^[0-9]{3}$"
          message: "使用三位数字，例如 001"
      - name: title
        label: 章节标题
        type: string
        required: true
      - name: slug
        label: Slug
        type: string
        required: true
        pattern:
          regex: "^[a-z0-9]+(-[a-z0-9]+)*$"
          message: "只能使用小写英文、数字和短横线"
      - name: status
        label: 状态
        type: select
        required: true
        options:
          values:
            - name: draft
              label: 草稿
            - name: review
              label: 待检查
            - name: published
              label: 已发布
            - name: archived
              label: 已归档
      - name: summary
        label: 摘要
        type: text
        required: true
      - name: wordCount
        label: 字数
        type: number
        hidden: true
        # 由构建脚本自动计算，作者无需手动填写
      - name: createdAt
        label: 创建日期
        type: date
        required: true
      - name: updatedAt
        label: 更新日期
        type: date
        required: true
        readonly: true
        # 由构建脚本自动更新，作者无需手动修改
      - name: ai
        label: AI 使用记录
        type: object
        fields:
          - name: model
            label: 模型或来源
            type: string
          - name: prompt
            label: 使用的提示词 slug
            type: string
          - name: humanEdited
            label: 已人工修订
            type: boolean
      - name: seo
        label: SEO
        component: seo
      - name: body
        label: 正文
        type: rich-text
        required: true
        options:
          format: markdown
          media: chapter_images
          switcher: true

  - name: releases
    label: 版本说明
    type: collection
    path: src/content/releases
    format: yaml-frontmatter
    filename: "{book}-{versionSlug}.md"
    view:
      fields: [title, book, version, date]
      primary: title
      sort: [date, book]
      default:
        sort: date
        order: desc
    fields:
      - name: book
        label: 所属书籍
        type: reference
        required: true
        options:
          collection: books
          value: "{slug}"
          label: "{title}"
      - name: version
        label: 版本号
        type: string
        required: true
      - name: versionSlug
        label: 版本 Slug
        type: string
        required: true
        pattern:
          regex: "^[a-z0-9]+(-[a-z0-9]+)*$"
          message: "只能使用小写英文、数字和短横线"
      - name: title
        label: 标题
        type: string
        required: true
      - name: date
        label: 发布日期
        type: date
        required: true
      - name: gitTag
        label: Git tag
        type: string
      - name: body
        label: 版本说明
        type: rich-text
        options:
          format: markdown
          media: false

  - name: prompts
    label: AI 提示词
    type: collection
    path: src/content/prompts
    format: yaml-frontmatter
    filename: "{slug}.md"
    view:
      fields: [title, category, status, updatedAt]
      primary: title
      sort: [updatedAt, title]
      search: [title, category]
      default:
        sort: updatedAt
        order: desc
    fields:
      - name: title
        label: 标题
        type: string
        required: true
      - name: slug
        label: Slug
        type: string
        required: true
        pattern:
          regex: "^[a-z0-9]+(-[a-z0-9]+)*$"
          message: "只能使用小写英文、数字和短横线"
      - name: category
        label: 类型
        type: select
        required: true
        options:
          values:
            - name: rewrite
              label: 改写
            - name: style
              label: 风格
            - name: outline
              label: 大纲
            - name: character
              label: 角色
            - name: review
              label: 审稿
      - name: status
        label: 状态
        type: select
        required: true
        options:
          values:
            - name: active
              label: 启用
            - name: archived
              label: 归档
      - name: updatedAt
        label: 更新日期
        type: date
        required: true
      - name: body
        label: 提示词正文
        type: rich-text
        options:
          format: markdown
          media: false
```

### 9.2 Pages CMS 使用约束

实现时必须遵守：

- `.pages.yml` 中的字段名必须和 Astro schema 一致。
- `chapters.body` 是特殊字段，会写到 frontmatter 下面的 Markdown 正文。
- `status` 默认新建时应选 `draft`，发布前人工改成 `published`。
- `book` 字段通过 reference 选择书籍，保存值为 book slug。
- 封面图写入 `/covers/...`，章节插图写入 `/images/chapters/...`。
- 不要让 Pages CMS 管理 `src/pages`、`src/components` 等代码文件。
- Pages CMS 不支持 `type: group`，因此 `books`、`chapters`、`releases`、`prompts` 四个 collection 直接放在 `content` 顶层，与 `site` 同级。如果后续 Pages CMS 新增 group 支持，可以按侧栏分组重新组织。

## 十、页面设计

### 10.1 首页 `/`

目标：让读者第一眼看到“有哪些书”和“最近更新到哪里”。

页面模块：

- 顶部导航：站名、书籍、搜索、关于。
- 最近更新：展示最近 8-10 个 published 章节。
- 书籍列表：展示所有 public 书籍。
- 标签入口：展示常用标签。
- 版权提示：说明只公开公版或授权内容。

数据来源：

- `getPublicBooks()`
- `getRecentChapters(10)`
- `getAllTags()`

验收：

- 草稿书籍不显示。
- 隐藏书籍不显示。
- 最近更新只显示 published 章节。
- 移动端第一屏能看到至少 1 本书或最近更新。

### 10.2 书籍列表 `/books/`

页面模块：

- 筛选：状态、标签。
- 排序：最近更新、书名、完结优先。
- 卡片：封面、书名、简介、状态、章节数、最近更新。

首版筛选可以用纯前端 JavaScript；不需要服务端。

### 10.3 书籍详情 `/books/[book]/`

页面模块：

- 书籍封面和元信息。
- 简介、标签、版权状态。
- 章节目录。
- 最近版本说明。
- 开始阅读按钮。

章节目录规则：

- 只显示 `status === "published"` 的章节。
- 按 `chapterNo` 升序。
- 标题显示格式：`chapterNo + title`。

### 10.4 章节页 `/books/[book]/[chapter]/`

页面模块：

- 章节标题、摘要、更新时间。
- 正文阅读区。
- 上一章 / 下一章。
- 当前书目录抽屉。
- 阅读工具栏。
- 返回书页。

阅读工具栏首版功能：

- 字号：小 / 中 / 大。
- 行距：紧凑 / 标准 / 宽松。
- 主题：浅色 / 暗色 / 跟随系统。
- 页面宽度：标准 / 宽。

设置保存到 `localStorage`，不引入数据库。

正文区域建议：

```html
<article class="reader-content" data-pagefind-body>
  ...
</article>
```

首版只要求 `data-pagefind-body`，让 Pagefind 索引正文阅读区。后续如果要做按书籍、类型过滤，再补 `data-pagefind-filter` 和 `data-pagefind-meta`，不要在第一版同时把搜索 UI 做复杂。

### 10.5 搜索页 `/search/`

页面模块：

- 搜索框。
- 结果列表。
- 搜索结果显示标题、摘要、所属书籍、章节号。
- 空结果提示。

搜索来源：

- Pagefind 生成的静态索引。
- 不接数据库。

### 10.6 标签页 `/tags/[tag]/`

展示某个标签下的书籍。首版只对书籍打标签，不对章节单独打标签。

### 10.7 版本页 `/releases/`

展示所有版本说明，按日期倒序。

可按书籍过滤。每条版本说明链接到对应 Git tag 时，如果没有 tag，也不要报错。

### 10.8 提示词内容

首版默认不实现公开 `/prompts/` 页面。提示词是作者侧创作资产，保存在 `src/content/prompts/`，用于：

- Pages CMS 中维护常用改写模板。
- 章节 frontmatter 的 `ai.prompt` 记录使用过的 prompt slug。
- 后续复盘创作流程。

如果未来决定公开提示词，需要同时处理：

- 新增 `/prompts/` 路由和导航入口。
- 只展示 `status === "active"` 的内容。
- 决定是否加入 sitemap 和 Pagefind。
- 如果只给读者看创作方法摘要，不想被搜索引擎索引，应给页面加 `noindex`。

### 10.9 关于页 `/about/`

内容：

- 项目说明。
- AI 辅助创作说明。
- 版权边界。
- 联系方式或 GitHub 链接。

## 十一、路由实现规范

### 11.1 书籍页 getStaticPaths

```ts
export async function getStaticPaths() {
  const books = await getPublicBooks();
  return books.map((book) => ({
    params: { book: book.data.slug },
    props: { book },
  }));
}
```

### 11.2 章节页 getStaticPaths

```ts
export async function getStaticPaths() {
  const books = await getPublicBooks();
  const paths = [];

  for (const book of books) {
    const chapters = await getPublishedChapters(book.data.slug);
    for (const chapter of chapters) {
      paths.push({
        params: {
          book: book.data.slug,
          chapter: chapter.data.slug,
        },
        props: {
          book,
          chapter,
        },
      });
    }
  }

  return paths;
}
```

### 11.3 章节导航

```ts
const nav = await getChapterNav(book.data.slug, chapter.data.slug);
```

`ChapterNav.astro` 接收：

```ts
interface Props {
  prev: ChapterEntry | null;
  next: ChapterEntry | null;
  bookSlug: string;
}
```

组件输出：

- 无上一章时按钮 disabled。
- 无下一章时按钮 disabled。
- 链接格式为 `/books/${bookSlug}/${chapter.data.slug}/`。

## 十二、组件规格

### 12.1 BaseLayout

职责：

- 输出 HTML 文档结构。
- 注入 SEO meta。
- 注入全局 CSS。
- 提供 header、main、footer。

Props：

```ts
interface Props {
  title: string;
  description?: string;
  canonical?: string;
  ogImage?: string;
  noindex?: boolean;
}
```

### 12.2 ReaderLayout

职责：

- 包裹章节正文。
- 提供阅读宽度、字号、行距 CSS 变量。
- 提供阅读设置脚本挂载点。

不要把章节查询逻辑放进 layout；layout 只处理展示。

### 12.3 BookCard

展示：

- 封面。
- 书名。
- 简介。
- 状态 badge。
- 标签。
- 最近更新时间。

状态 badge 映射：

| status | 文案 |
|--------|------|
| planning | 计划中 |
| serializing | 连载中 |
| completed | 已完结 |
| paused | 暂停 |

### 12.4 ChapterList

Props：

```ts
interface Props {
  bookSlug: string;
  chapters: ChapterEntry[];
}
```

展示：

- 章节号。
- 标题。
- 摘要。
- 更新时间。

### 12.5 ReaderToolbar

职责：

- 控制阅读设置。
- 读取和写入 `localStorage`。
- 给 `document.documentElement` 设置 data attributes。

本地存储 key：

```text
mixtxt.reader.theme
mixtxt.reader.fontSize
mixtxt.reader.lineHeight
mixtxt.reader.width
mixtxt.reader.lastChapter

阅读进度记忆：每次进入章节页时，将 `{bookSlug}/{chapterSlug}` 写入 `mixtxt.reader.lastChapter.{bookSlug}`。首页和书籍详情页可以读取此值，显示"继续阅读"入口。

### 12.6 SearchBox

职责：

- 加载 Pagefind UI 或自定义搜索逻辑。
- 输入关键字。
- 展示结果。

首版可以直接使用 Pagefind UI；如果 UI 风格不合适，再封装自定义组件。

首版默认 UI 可以这样接入：

```astro
---
---

<link href="/pagefind/pagefind-component-ui.css" rel="stylesheet" />
<script src="/pagefind/pagefind-component-ui.js" type="module"></script>

<pagefind-modal-trigger></pagefind-modal-trigger>
<pagefind-modal></pagefind-modal>
```

`/pagefind/...` 文件只会在 `pagefind --site dist` 之后生成；本地 `astro dev` 阶段看不到完整搜索结果是正常现象。

## 十三、样式与阅读体验

阅读体验优先级高于视觉装饰。

### 13.1 基础视觉

建议：

- 页面背景不要纯白刺眼，可用接近纸张的浅灰。
- 正文字体优先系统中文字体。
- 正文字号默认 18px 左右。
- 正文行高默认 1.8。
- 阅读区最大宽度 720px。
- 段落间距稳定，不要一屏塞太多 UI。

### 13.2 CSS token

`src/styles/tokens.css`：

```css
:root {
  --color-bg: #f7f7f4;
  --color-surface: #ffffff;
  --color-text: #222222;
  --color-muted: #666666;
  --color-border: #deded8;
  --color-accent: #2f5f8f;
  --reader-width: 720px;
  --reader-font-size: 18px;
  --reader-line-height: 1.8;
}

[data-theme="dark"] {
  --color-bg: #151515;
  --color-surface: #1f1f1f;
  --color-text: #eeeeee;
  --color-muted: #aaaaaa;
  --color-border: #333333;
  --color-accent: #8bb8ff;
}
```

不要做单色系大面积渐变。小说站要稳、耐看、长时间阅读不累。

### 13.3 移动端

移动端要求：

- 顶部导航不能遮挡正文。
- 章节页底部必须有上一章 / 下一章。
- 阅读设置面板应可收起。
- 正文宽度使用 `min(100%, var(--reader-width))`。
- 封面图不应挤压正文入口。

## 十四、Pagefind 搜索

### 14.1 构建命令

构建脚本必须先校验内容，再构建 Astro，最后运行 Pagefind：

```json
{
  "scripts": {
    "dev": "astro dev",
    "validate:content": "node scripts/validate-content.mjs",
    "build": "npm run validate:content && astro build && pagefind --site dist",
    "preview": "astro preview"
  }
}
```

### 14.2 索引范围

只让公开页面进入索引。因为 Astro 只构建 published 章节，所以草稿默认不会进入 Pagefind。

需要明确：

- 不要在页面里渲染草稿内容后再用 CSS 隐藏。
- 不要让 hidden 书籍参与路由。
- 不要把 private draft 放入 public 静态目录。
- 首版在章节正文 `<article>` 上添加 `data-pagefind-body`。一旦站内使用了这个属性，其他想进入搜索的页面也要显式添加，否则 Pagefind 不会索引它们。
- 首页、书籍页、版本页是否进入搜索要单独决定；不要默认把导航、页脚和管理说明一起索引。

Pagefind 索引决策表：

| 页面类型 | 是否索引 | 需要添加的 data 属性 |
|---------|---------|-------------------|
| 章节页正文 | 是 | `data-pagefind-body` |
| 章节页标题 | 是 | `data-pagefind-meta="title"` |
| 书籍详情页简介 | 否 | 不添加（书籍信息通过章节间接可搜） |
| 首页 | 否 | 不添加 |
| 版本页 | 否 | 不添加 |
| 搜索页 | 否 | `data-pagefind-ignore` |
| 导航、页脚 | 否 | `data-pagefind-ignore` |

一旦站内使用了 `data-pagefind-body`，Pagefind 只索引显式标记了该属性的元素。因此上表中的"否"意味着不添加 `data-pagefind-body`，该页面内容不会进入搜索索引。

### 14.3 搜索结果体验

结果项显示：

- 标题。
- 摘要片段。
- 所属书籍。
- 类型：书籍 / 章节 / 版本说明。

如果 Pagefind 默认 UI 难以满足这些字段，首版可以先使用默认 UI，第二版再接自定义结果组件。

## 十五、SEO、RSS 和 sitemap

### 15.1 SEO

每个页面必须有：

- `<title>`
- `description`
- canonical URL
- Open Graph title / description

章节页 title 格式：

```text
{chapterNo} {chapterTitle} - {bookTitle} - {siteTitle}
```

书籍页 title 格式：

```text
{bookTitle} - {siteTitle}
```

### 15.2 RSS

RSS 只包含最近发布章节：

- 标题：`{bookTitle}: {chapterNo} {chapterTitle}`
- 链接：章节 URL
- 日期：`updatedAt`
- 描述：`summary`

RSS 实现参考（`src/pages/rss.xml.ts`）：

```ts
import type { APIRoute } from "astro";
import { getPublishedChapters, getPublicBooks } from "../lib/content";
import { getSiteConfig } from "../lib/site";

export const GET: APIRoute = async ({ site }) => {
  const config = getSiteConfig();
  const chapters = await getPublishedChapters();
  const books = await getPublicBooks();
  const bookMap = new Map(books.map((b) => [b.data.slug, b]));

  const items = chapters.slice(0, 20).map((ch) => {
    const book = bookMap.get(ch.data.book);
    return `
    <item>
      <title><![CDATA[${book?.data.title ?? ""}: ${ch.data.chapterNo} ${ch.data.title}]]></title>
      <link>${site}books/${ch.data.book}/${ch.data.slug}/</link>
      <guid isPermaLink="true">${site}books/${ch.data.book}/${ch.data.slug}/</guid>
      <description><![CDATA[${ch.data.summary}]]></description>
      <pubDate>${new Date(ch.data.updatedAt).toUTCString()}</pubDate>
    </item>`;
  });

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title><![CDATA[${config.title}]]></title>
    <description><![CDATA[${config.description}]]></description>
    <link>${site}</link>
    <atom:link href="${site}rss.xml" rel="self" type="application/rss+xml"/>
    <language>${config.defaultLanguage}</language>
    ${items.join("")}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
};
```

注意：Astro 的 RSS 也可以使用 `@astrojs/rss` 包简化生成，首版如果不想手写 XML，可以改用该包。无论哪种方式，都必须只包含 `published` 状态的章节。

### 15.3 sitemap

sitemap 包含：

- 首页。
- 书籍列表页。
- 公开书籍页。
- published 章节页。
- 标签页。
- 版本页。

不包含：

- draft 章节。
- review 章节。
- hidden 书籍。
- prompts 页面，如果不公开。

### 15.4 robots.txt

首版可以允许索引公开页面：

```text
User-agent: *
Allow: /

Sitemap: https://mixtxt.example.com/sitemap.xml
```

如果不希望全文被搜索引擎索引，就不要公开章节全文。静态站一旦公开 HTML，就不能可靠阻止复制。

## 十六、Cloudflare Pages 部署

### 16.1 项目设置

```text
Framework preset: Astro
Build command: npm run build
Build output directory: dist
Root directory: /
Environment variables: NODE_VERSION 使用当前 Node.js LTS
```

如果使用 pnpm：

```text
Build command: pnpm build
Build output directory: dist
```

### 16.2 构建频率

你现有 Cloudflare Pages 项目每月约 300 次 build。截至 2026-06-03，Cloudflare Pages Free plan 每月 500 次 build，且免费层同一时间 1 个构建任务。实务上应按账号维度管理总构建量，不要假定每个 Pages 项目都有独立 500 次额度。

小说站建议：

- 本地预览，不要每改一段就 push。
- 每天集中 push 1-3 次。
- 每月新增 build 控制在 30-90 次。
- 合计约 330-390 次，仍在免费层内。

### 16.3 文件数量

截至 2026-06-03，Cloudflare Pages Free plan 单站最多 20,000 个文件，单文件最大 25 MiB。小说站通常不会马上触碰这些限制。

估算：

```text
100 本书 * 每本 100 章 = 10,000 个章节页
加上索引、标签、搜索资源、静态资源，仍大概率低于 20,000
```

如果未来超过：

- 按书拆分多个站点。
- 删除不必要的历史版本静态页。
- 升级 Cloudflare plan。
- 改用对象存储托管大文件。

### 16.4 `_headers`

`public/_headers`：

```text
/*
  Cache-Control: public, max-age=3600
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin

/_astro/*
  Cache-Control: public, max-age=31536000, immutable

/covers/*
  Cache-Control: public, max-age=31536000, immutable

/images/*
  Cache-Control: public, max-age=31536000, immutable

/pagefind/*
  Cache-Control: public, max-age=31536000, immutable
```

不要给 HTML 设置过长缓存，避免章节发布后读者长期看到旧内容。

## 十七、Git 版本管理

版本分三层：

| 层级 | 面向谁 | 实现 |
|------|--------|------|
| 编辑历史 | 作者 | Pages CMS / 本地编辑产生 Git commit |
| 发布版本 | 作者和读者 | Git tag + release note |
| 逐字 diff | 作者 | Git diff；网页展示后置 |

推荐 commit message：

```text
feat(book): add sanguo-scifi
feat(chapter): add sanguo-scifi 002 huangjin
edit(chapter): revise sanguo-scifi 002
chore(media): add cover sanguo-scifi
release(book): sanguo-scifi v0.1.0
```

发布版本：

```bash
git tag v0.1.0
git push origin main --tags
```

读者看到的是 releases 页面，不直接看 Git log。

## 十八、AI 创作工作流

这个网站是 AI 改编小说网站，但首版不把 AI 接口接到站内。AI 生成仍在站外完成，站内负责整理、保存和发布。

### 18.1 推荐流程

```text
选择原作和改编方向
-> 使用 prompts 模板生成章节草稿
-> 人工修订事实、节奏、人物动机
-> Pages CMS 新建章节，状态设为 draft
-> 本地预览或 Cloudflare preview 检查
-> 状态改为 published
-> push / 保存触发构建
```

### 18.2 AI 使用记录

每章 frontmatter 的 `ai` 字段记录：

- 使用的 prompt slug。
- 模型或来源。
- 是否人工修订。

不要把完整模型输出历史塞进章节 frontmatter。需要保留时，另存到私有笔记或 Git ignored 文件。

### 18.3 版权检查

发布前必须确认：

- 原作是否公版。
- 是否有授权。
- 是否只是私人草稿。
- 是否涉及商用传播。

`copyrightStatus === "unknown"` 的书籍不应公开。实现时可以在构建中加入检查：公开书籍如果版权状态为 `unknown`，构建失败。

## 十九、测试与验收

### 19.1 内容校验

必须验证：

- `npm run build` 成功。
- `site.json` 必须包含 title、description、author、defaultLanguage、baseUrl。
- 没有重复 book slug。
- 同一本书内没有重复 chapter slug。
- 同一本书内没有重复 chapterNo。
- published 章节所属 book 必须存在。
- public book 的 `copyrightStatus` 不能是 `unknown`。
- `copyrightStatus` 为 `private-draft` 时，`visibility` 必须为 `hidden`。
- releases 的 `version` 格式应为 semver（如 `v0.1.0`）。
- chapters 的 `ai.prompt` 引用的 slug 必须在 prompts collection 中存在。
- books 的 `startedAt` 和 `updatedAt` 必须是合法日期格式（`YYYY-MM-DD`）。
- chapters 的 `createdAt` 不应晚于 `updatedAt`。

必须提供一个内容校验脚本：

```text
scripts/validate-content.mjs
```

并让 build 先跑：

```json
{
  "scripts": {
    "validate:content": "node scripts/validate-content.mjs",
    "build": "npm run validate:content && astro build && pagefind --site dist"
  }
}
```

`scripts/validate-content.mjs` 应实现以下规则。脚本可以直接读文件，不依赖 Astro 运行时：

```js
import { access, readdir, readFile } from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";

const root = process.cwd();
const contentDir = path.join(root, "src/content");
const errors = [];

function fail(message) {
  errors.push(message);
}

async function exists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

async function readJsonDir(dir) {
  const fullDir = path.join(contentDir, dir);
  const files = (await readdir(fullDir)).filter((file) => file.endsWith(".json"));
  return Promise.all(
    files.map(async (file) => ({
      file,
      path: path.join(fullDir, file),
      data: JSON.parse(await readFile(path.join(fullDir, file), "utf8")),
    }))
  );
}

async function readJsonFile(file) {
  const fullPath = path.join(root, "src/data", file);
  return JSON.parse(await readFile(fullPath, "utf8"));
}

async function readMarkdownDir(dir) {
  const fullDir = path.join(contentDir, dir);
  const files = (await readdir(fullDir)).filter((file) => file.endsWith(".md"));
  return Promise.all(
    files.map(async (file) => {
      const raw = await readFile(path.join(fullDir, file), "utf8");
      const parsed = matter(raw);
      return { file, path: path.join(fullDir, file), data: parsed.data, body: parsed.content };
    })
  );
}

const books = await readJsonDir("books");
const chapters = await readMarkdownDir("chapters");
const releases = await readMarkdownDir("releases");
const prompts = await readMarkdownDir("prompts");

const site = await readJsonFile("site.json");
for (const key of ["title", "description", "author", "defaultLanguage", "baseUrl"]) {
  if (!site[key]) fail(`site.json: 缺少 ${key}`);
}
try {
  new URL(site.baseUrl);
} catch {
  fail("site.json: baseUrl 必须是完整 URL");
}

const bookBySlug = new Map();
for (const book of books) {
  const slug = book.data.slug;
  if (!slug) fail(`${book.file}: 缺少 slug`);
  if (bookBySlug.has(slug)) fail(`重复 book slug: ${slug}`);
  bookBySlug.set(slug, book);

  if (book.file !== `${slug}.json`) {
    fail(`${book.file}: 文件名必须是 ${slug}.json`);
  }

  if (book.data.visibility === "public" && ["unknown", "private-draft"].includes(book.data.copyrightStatus)) {
    fail(`${book.file}: public book 不能使用 copyrightStatus=${book.data.copyrightStatus}`);
  }

  if (book.data.cover) {
    const coverPath = path.join(root, "public", book.data.cover.replace(/^\//, ""));
    if (!(await exists(coverPath))) fail(`${book.file}: cover 文件不存在: ${book.data.cover}`);
  }
}

const chapterSlugSet = new Set();
const chapterNoSet = new Set();
for (const chapter of chapters) {
  const { book, chapterNo, slug, status } = chapter.data;
  if (!bookBySlug.has(book)) fail(`${chapter.file}: book 不存在: ${book}`);

  const expected = `${book}-${chapterNo}-${slug}.md`;
  if (chapter.file !== expected) fail(`${chapter.file}: 文件名必须是 ${expected}`);

  const slugKey = `${book}:${slug}`;
  const noKey = `${book}:${chapterNo}`;
  if (chapterSlugSet.has(slugKey)) fail(`重复 chapter slug: ${slugKey}`);
  if (chapterNoSet.has(noKey)) fail(`重复 chapterNo: ${noKey}`);
  chapterSlugSet.add(slugKey);
  chapterNoSet.add(noKey);

  const parentBook = bookBySlug.get(book);
  if (status === "published") {
    if (parentBook?.data.visibility !== "public") fail(`${chapter.file}: published 章节所属书籍不是 public`);
    if (["unknown", "private-draft"].includes(parentBook?.data.copyrightStatus)) {
      fail(`${chapter.file}: published 章节所属书籍版权状态不可公开`);
    }
  }
}

for (const release of releases) {
  if (!bookBySlug.has(release.data.book)) fail(`${release.file}: release book 不存在: ${release.data.book}`);
}

const promptSlugs = new Set();
for (const prompt of prompts) {
  if (promptSlugs.has(prompt.data.slug)) fail(`重复 prompt slug: ${prompt.data.slug}`);
  promptSlugs.add(prompt.data.slug);
}

// 校验 ai.prompt 引用一致性
for (const chapter of chapters) {
  if (chapter.data.ai?.prompt && !promptSlugs.has(chapter.data.ai.prompt)) {
    fail(`${chapter.file}: ai.prompt 引用的 prompt 不存在: ${chapter.data.ai.prompt}`);
  }
}

// 校验 copyrightStatus 与 visibility 约束
for (const book of books) {
  if (book.data.copyrightStatus === "private-draft" && book.data.visibility !== "hidden") {
    fail(`${book.file}: copyrightStatus=private-draft 时 visibility 必须为 hidden`);
  }
}

// 校验版本号格式
const semverPattern = /^v?\d+\.\d+\.\d+$/;
for (const release of releases) {
  if (!semverPattern.test(release.data.version)) {
    fail(`${release.file}: version 格式应为 semver，如 v0.1.0`);
  }
}

// 校验日期格式
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
for (const book of books) {
  if (!datePattern.test(book.data.startedAt)) fail(`${book.file}: startedAt 日期格式不合法`);
  if (!datePattern.test(book.data.updatedAt)) fail(`${book.file}: updatedAt 日期格式不合法`);
}
for (const chapter of chapters) {
  if (!datePattern.test(chapter.data.createdAt)) fail(`${chapter.file}: createdAt 日期格式不合法`);
  if (!datePattern.test(chapter.data.updatedAt)) fail(`${chapter.file}: updatedAt 日期格式不合法`);
  if (chapter.data.createdAt > chapter.data.updatedAt) {
    fail(`${chapter.file}: createdAt 不应晚于 updatedAt`);
  }
}

if (errors.length > 0) {
  console.error(errors.map((error) => `- ${error}`).join("\n"));
  process.exit(1);
}

console.log("content validation passed");
```

这段脚本是实现参考，不要求逐字照抄，但最终项目必须覆盖同等规则。不要用正则手写 frontmatter 解析；Markdown frontmatter 统一交给 `gray-matter`。

### 19.2 页面验收

| 页面 | 验收点 |
|------|--------|
| 首页 | 书籍和最近更新正确展示 |
| 书籍页 | 章节按 chapterNo 排序，草稿不显示 |
| 章节页 | 上一章 / 下一章正确，不能跨书 |
| 搜索页 | 能搜到 published 章节，搜不到草稿 |
| 标签页 | 标签下书籍正确 |
| RSS | 只包含公开章节 |
| sitemap | 不包含草稿和 hidden 内容 |

### 19.3 浏览器验收

需要用 Playwright 或手工检查：

- 桌面 1440px。
- 平板 768px。
- 手机 390px。
- 暗色模式。
- 阅读设置刷新后仍保留。
- 长章节不会出现布局溢出。

### 19.4 性能验收

首版目标：

- 首页 Lighthouse Performance 90+。
- 章节页首屏不加载不必要 JS。
- 阅读器 JS 只处理设置，不阻塞正文。
- 封面图使用 webp，并设置合理尺寸。

## 二十、实施计划

### Phase 0：初始化

1. 创建 Astro 项目。
2. 安装 Pagefind。
3. 配置基本 CSS。
4. 创建示例内容。

验收：

- `npm run dev` 可运行。
- `npm run build` 可通过。

### Phase 1：内容模型和路由

1. 编写 `src/content.config.ts`。
2. 创建 `site.json`、books、chapters、releases、prompts 示例。
3. 编写 `src/lib/content.ts`。
4. 实现首页、书籍页、章节页。

验收：

- 公开书籍和章节显示正确。
- 草稿不显示。
- 上一章 / 下一章正确。

### Phase 2：Pages CMS

1. 添加 `.pages.yml`。
2. 在 Pages CMS 中连接 GitHub 仓库。
3. 测试新增书籍。
4. 测试新增章节。
5. 测试上传封面。

验收：

- Pages CMS 保存内容后，Astro build 仍通过。
- 新增章节文件名符合 `{book}-{chapterNo}-{slug}.md`。
- CMS 字段和 Astro schema 对齐。

### Phase 3：阅读器体验

1. 实现 ReaderLayout。
2. 实现 ReaderToolbar。
3. 实现目录抽屉。
4. 实现暗色模式、字号、行距、宽度设置。
5. 做移动端适配。

验收：

- 长时间阅读舒适。
- 设置写入 localStorage。
- 手机端不遮挡正文。

### Phase 4：搜索和 SEO

1. 接 Pagefind。
2. 实现 search 页面。
3. 实现 RSS。
4. 实现 sitemap。
5. 完成 meta / Open Graph。

验收：

- 搜索能找到已发布章节。
- 搜索找不到草稿。
- sitemap 不包含草稿。

### Phase 5：部署

1. GitHub 连接 Cloudflare Pages。
2. 配置 build command。
3. 设置自定义域名。
4. 检查 build 次数。
5. 检查缓存 headers。

验收：

- Cloudflare Pages 构建成功。
- 自定义域名可访问。
- 移动端和桌面端页面正常。

## 二十一、AI 实施守则

如果让 AI 根据本文档实现项目，必须遵守：

1. 不要引入数据库。
2. 不要引入用户登录。
3. 不要把草稿渲染到公开页面。
4. 不要改动本文档定义的核心字段名。
5. 所有内容查询集中到 `src/lib/content.ts`。
6. 所有页面都通过工具函数获取内容。
7. 章节导航必须按同一本书内的 `chapterNo` 计算。
8. 搜索索引只能来自构建后的公开页面。
9. Pages CMS 配置和 Astro schema 必须同步。
10. 实现完成后必须跑 `npm run build`。

优先实现顺序：

```text
内容模型 -> 内容查询 -> 页面路由 -> 阅读器 -> CMS 配置 -> 搜索 -> 部署
```

不要先做复杂视觉效果。小说站的核心是内容结构、阅读体验和发布稳定性。

## 二十二、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Pages CMS 字段和 Astro schema 不一致 | 保存后构建失败 | 字段名统一，build 前跑内容校验 |
| Cloudflare build 次数不够 | 免费额度耗尽 | 本地预览后集中 push，减少 preview build |
| 草稿进入公开页面 | 内容泄露 | 统一使用 `getPublishedChapters()` |
| Pagefind 索引草稿 | 私有内容可搜索 | 草稿不参与静态构建 |
| 文件数超过限制 | Cloudflare Pages 部署失败 | 控制历史版本页数量，必要时拆站或升级 |
| 原作版权不清 | 网站无法公开运营 | `unknown` 不允许公开构建 |
| 依赖升级破坏构建 | 发布中断 | 固定 lockfile，升级前本地构建 |
| 构建失败 | 读者看到旧版本 | Cloudflare Pages 构建失败时旧版本仍在线；建议配置 GitHub Actions 本地构建门控，push 前自动跑 `npm run build`；构建失败时 Cloudflare 会发邮件通知 |

## 二十三、最终判断

这套方案是当前需求下最平衡的选择：

- 比 Hugo 更适合做定制小说阅读器。
- 比 Astro + Keystatic 更少工程化配置负担。
- 比 Next.js / Payload / D1 更轻，不提前引入数据库。
- 比纯 Git 写作更友好，因为 Pages CMS 给了网页编辑入口。

如果第一版目标是“一个人创作、所有人阅读、Markdown 保存、Git 管版本、成本低、体验好”，就按这个方案做。

## 附录 A：官方参考

- [Pages CMS Introduction](https://pagescms.org/docs/)：确认 Pages CMS 是面向 GitHub 静态站的开源 CMS，直接编辑仓库文件，不替代站点生成器。
- [Pages CMS Content](https://pagescms.org/docs/configuration/content/)：确认 `content` 可以定义 collection、file，以及 `format`、`filename`、`view`、`actions` 等配置。
- [Pages CMS Fields](https://pagescms.org/docs/configuration/content/fields/)：确认 `body` 在 frontmatter 文件中映射到正文，字段支持 `required`、`pattern`、`hidden`、`readonly` 等选项。
- [Pages CMS Media](https://pagescms.org/docs/configuration/media/)：确认 media 的 `input`、`output`、`rename`、`extensions`、`categories` 配置。
- [Astro Pages CMS Guide](https://docs.astro.build/en/guides/cms/pages-cms/)：确认 Pages CMS 可用于管理 Astro 项目的 Git-based 内容。
- [Astro Content Collections](https://docs.astro.build/en/guides/content-collections/)：确认 Astro 可用 collection 和 schema 管理内容。
- [Astro Pages](https://docs.astro.build/en/basics/astro-pages/)：确认 Astro 的文件路由和动态路由能力。
- [Pagefind Getting Started](https://pagefind.app/docs/)：确认 Pagefind 在静态站生成后扫描 HTML 并生成搜索索引，且提供默认搜索 UI。
- [Pagefind Indexing](https://pagefind.app/docs/indexing/)：确认可用 `data-pagefind-body` 控制哪些 HTML 区域进入索引。
- [Pagefind Metadata](https://pagefind.app/docs/metadata/)：确认后续可用 `data-pagefind-meta` 给搜索结果补元数据。
- [Cloudflare Pages Astro Guide](https://developers.cloudflare.com/pages/framework-guides/deploy-an-astro-site/)：确认 Astro 部署到 Cloudflare Pages 的构建配置。
- [Cloudflare Pages Limits](https://developers.cloudflare.com/pages/platform/limits/)：确认免费层 build 次数、文件数量和单文件大小限制。
