# Astro + Keystatic 方案详细设计

> 文档类型：架构设计与落地方案
>
> 目标需求：[AI改编小说网需求.md](./AI改编小说网需求.md)
>
> 关联文档：[AI改编小说网架构.md](./AI改编小说网架构.md)、[开发框架-Hugo方案可行性评估.md](./开发框架-Hugo方案可行性评估.md)、[开发框架方案对比与推荐.md](./开发框架方案对比与推荐.md)

## 一、结论

**如果你想保留“Markdown 正本 + 无数据库 + 静态发布”，但又希望有更强的内容结构校验、网页编辑入口和前端交互能力，Astro + Keystatic 是比纯 Hugo 更完整的方案。**

它不是为了替代所有场景下的 Hugo。Hugo 的优势仍然是极快、极轻、命令简单；Astro 的优势是把小说站做成一个更像“内容应用”的静态站：书籍和章节有明确 schema，章节页可以组件化，阅读器可以逐步增强，作者也能通过 Keystatic 获得一个网页编辑界面。

这套方案的推荐组合是：

```text
Astro + Keystatic + Pagefind + GitHub + Cloudflare Pages
```

各部分职责很清楚：

| 模块 | 职责 | 是否有数据库 |
|------|------|--------------|
| Astro | 生成书籍页、章节页、索引页、阅读器 UI | 否 |
| Content Collections | 管理书籍、章节、版本说明等结构化内容 | 否 |
| Keystatic | 提供作者编辑 UI，把内容保存回 Git 仓库 | 否 |
| Pagefind | 构建后生成静态站内搜索索引 | 否 |
| GitHub | 保存 Markdown、版本历史、分支、tag | 否 |
| Cloudflare Pages | 自动构建和发布静态站点 | 否 |

这不是付费小说平台方案。只要出现用户登录、付费章节、订单、读者私有书架、服务端 AI 生成并保存等需求，就应该切到动态架构，例如 Next.js + 数据库、Payload CMS 或 Cloudflare Workers + D1。

## 二、为什么这个方案值得单独考虑

Hugo 方案的核心优点是“轻”。但你的需求里有两个词值得重新看：**管理**和**所有章节关联**。如果管理只是本地改 Markdown，Hugo 很顺；如果管理希望有一点网页后台味道，Hugo 就要额外接 CMS。Astro + Keystatic 正好卡在中间：仍然不需要数据库，但内容管理体验比纯 Hugo 细。

Astro 对这个项目的价值主要有四个：

1. **章节元数据更不容易乱**  
   Astro Content Collections 可以给 Markdown front matter 加 schema。比如每章必须有 `book`、`order`、`title`、`summary`、`draft`，构建时就能发现字段缺失或类型错误。

2. **阅读体验更容易组件化**  
   字号切换、暗色模式、章节抽屉、阅读进度、本地收藏、目录高亮、封面卡片，这些前端体验用 Astro 组件做会比 Hugo 模板自然。

3. **网页编辑入口更顺**  
   Keystatic 可以加到 Astro 项目里，作者通过一个管理 UI 编辑内容，保存后仍然落到 Git 仓库。内容正本还是文件，不引入 CMS 数据库。

4. **后续扩展路径更平滑**  
   如果未来要接 Cloudflare Pages Functions、D1、KV、R2，Astro 的前端应用结构比 Hugo 更容易承接这些增强。

但它也有代价：Node 工具链更重，依赖更多，构建速度通常不如 Hugo，首次配置 Keystatic 和 schema 也要多花一点时间。

## 三、总览架构

先把系统拆成四条线：写作线、内容线、构建线、读者线。

```mermaid
flowchart LR
    A["AI 生成草稿"] --> B["作者修订"]
    B --> C["Keystatic 编辑 UI 或本地编辑器"]
    C --> D["Markdown / JSON 内容文件"]
    D --> E["Git commit / tag"]
    E --> F["GitHub 仓库"]
    F --> G["Cloudflare Pages 构建"]
    G --> H["Astro 生成静态 HTML"]
    H --> I["Pagefind 生成搜索索引"]
    I --> J["Cloudflare CDN 发布"]
    J --> K["读者浏览书籍和章节"]
```

这个方案里没有运行时数据库，也没有常驻后端。Keystatic 的作用是编辑文件，不是替代 Git；Pagefind 的作用是给已经生成的 HTML 做静态索引，不是提供搜索服务端。

## 四、需求逐条对照 Astro

| 需求 | Astro 方案是否满足 | 说明 |
|------|------------------|------|
| 保存 AI 改编小说 | 满足 | 章节保存为 Markdown / MDX 文件 |
| Markdown 格式保存 | 满足 | 建议优先使用 `.md`；如需组件化再考虑 `.mdx` |
| 不需要数据库 | 满足 | 内容、元数据、搜索索引都可以是静态文件 |
| 文本文件形式保存 | 满足 | 书籍元数据可用 JSON / YAML，章节正文用 Markdown |
| 只有一个创建者 | 满足 | Keystatic 后台只给作者使用 |
| 其他用户只能查看不能编辑 | 满足 | 读者访问构建后的静态页面，不接触 Git 写权限 |
| 作者网页管理 | 部分满足 | Keystatic 提供编辑 UI，但不是多用户 CMS |
| 版本管理 | 满足 | Git commit / branch / tag 负责版本 |
| 所有章节关联 | 满足 | 通过 `book` + `order` 字段生成目录和上一章 / 下一章 |
| 用户界面简单 | 满足 | Astro 可以做更定制的小说阅读器 |
| 性能快 | 满足 | 静态 HTML + CDN；比 Hugo 稍重，但仍属于静态站 |
| 未来局部交互 | 更适合 | Astro 组件和 island 架构更方便逐步增强 |

## 五、推荐技术栈

```text
框架:       Astro
内容管理:   Astro Content Collections
编辑 UI:    Keystatic
正文格式:   Markdown（首选）/ MDX（需要组件化时）
搜索:       Pagefind
版本:       Git + GitHub
部署:       Cloudflare Pages
静态资源:   public/ 或 Cloudflare R2（大文件才需要）
未来动态:   Cloudflare Pages Functions + D1 / KV（第二阶段）
```

不要在第一版里同时引入太多东西。首版只需要 Astro、Keystatic、Pagefind 和 Cloudflare Pages。D1、KV、R2、Functions 都放到未来阶段。

## 六、内容模型设计

这套系统建议把“书”和“章节”拆成两个 collection。书籍只放元数据，章节放正文。

### 6.1 目录结构

```text
mixtxt-astro/
├── astro.config.mjs
├── package.json
├── src/
│   ├── content.config.ts
│   ├── content/
│   │   ├── books/
│   │   │   └── sanguo-scifi.json
│   │   ├── chapters/
│   │   │   └── sanguo-scifi/
│   │   │       ├── 001-prologue.md
│   │   │       ├── 002-huangjin.md
│   │   │       └── 003-luoyang.md
│   │   └── releases/
│   │       └── sanguo-scifi.json
│   ├── layouts/
│   │   ├── BaseLayout.astro
│   │   └── ReaderLayout.astro
│   ├── pages/
│   │   ├── index.astro
│   │   ├── books/
│   │   │   ├── [book].astro
│   │   │   └── [book]/
│   │   │       └── [chapter].astro
│   │   └── search.astro
│   ├── components/
│   │   ├── BookCard.astro
│   │   ├── ChapterNav.astro
│   │   ├── ReaderToolbar.astro
│   │   └── SearchBox.astro
│   └── styles/
│       └── reader.css
├── public/
│   ├── covers/
│   └── fonts/
├── keystatic.config.ts
└── README.md
```

### 6.2 书籍元数据

`src/content/books/sanguo-scifi.json`：

```json
{
  "title": "三国演义：星火纪元",
  "slug": "sanguo-scifi",
  "original": "三国演义",
  "status": "serializing",
  "summary": "把东汉末年的群雄割据改写成星际文明崩塌后的权力重组。",
  "cover": "/covers/sanguo-scifi.jpg",
  "tags": ["三国", "科幻", "AI改编"],
  "createdAt": "2026-06-03",
  "updatedAt": "2026-06-03"
}
```

### 6.3 章节正文

`src/content/chapters/sanguo-scifi/002-huangjin.md`：

```markdown
---
book: "sanguo-scifi"
title: "002 黄巾初起"
slug: "002-huangjin"
order: 2
draft: false
summary: "巨鹿星区的张角点燃第一枚信标，旧帝国的边境开始瓦解。"
createdAt: "2026-06-03"
updatedAt: "2026-06-03"
---

## 一、边境信标

巨鹿星区的夜空没有月亮，只有一圈报废轨道炮留下的蓝白色残光。
```

这样设计有几个好处：

- `book` 决定章节归属。
- `order` 决定目录和上一章 / 下一章。
- `draft` 控制是否发布。
- `summary` 用于书页、搜索结果和 SEO。
- 文件路径保留书籍分组，Git diff 也容易看。

### 6.4 版本说明

`src/content/releases/sanguo-scifi.json`：

```json
{
  "book": "sanguo-scifi",
  "releases": [
    {
      "version": "v0.1.0",
      "title": "前三章试读版",
      "date": "2026-06-03",
      "notes": "完成世界观、楔子和黄巾初起两章。",
      "gitTag": "v0.1.0"
    }
  ]
}
```

版本说明不等于逐章 diff。它只记录给读者看的发布节点，真正的逐字历史仍然由 Git 保存。

### 6.5 Content Collections schema

`src/content.config.ts` 可以用 schema 把内容结构固定下来。下面是示意配置：

```ts
import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const books = defineCollection({
  loader: glob({ pattern: "*.json", base: "./src/content/books" }),
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    original: z.string().optional(),
    status: z.enum(["planning", "serializing", "completed", "paused"]),
    summary: z.string(),
    cover: z.string().optional(),
    tags: z.array(z.string()).default([]),
    createdAt: z.string(),
    updatedAt: z.string(),
  }),
});

const chapters = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/chapters" }),
  schema: z.object({
    book: z.string(),
    title: z.string(),
    slug: z.string(),
    order: z.number().int().positive(),
    draft: z.boolean().default(false),
    summary: z.string(),
    createdAt: z.string(),
    updatedAt: z.string(),
  }),
});

const releases = defineCollection({
  loader: glob({ pattern: "*.json", base: "./src/content/releases" }),
  schema: z.object({
    book: z.string(),
    releases: z.array(
      z.object({
        version: z.string(),
        title: z.string(),
        date: z.string(),
        notes: z.string(),
        gitTag: z.string().optional(),
      })
    ),
  }),
});

export const collections = {
  books,
  chapters,
  releases,
};
```

落地时可以先不做 `releases` collection。首版只要 `books` 和 `chapters` 两个 collection 就够。

## 七、页面与阅读体验

### 7.1 首页

首页只做三件事：

- 展示所有书籍。
- 展示最近更新章节。
- 提供搜索入口。

不要把首页做成营销落地页。这个项目的第一屏应该让读者直接看到“有哪些书”和“最近更新到哪里”。

### 7.2 书籍页

书籍页路径建议：

```text
/books/sanguo-scifi/
```

页面内容：

- 封面、书名、简介、标签、状态。
- 章节目录，按 `order` 排序。
- 最近更新时间。
- 版本说明入口。

章节列表不要依赖文件名排序，必须按 `order` 排序。Astro 文档也提醒过，collection 查询结果如果需要固定顺序，要自己排序。

### 7.3 章节页

章节页路径建议：

```text
/books/sanguo-scifi/002-huangjin/
```

章节页需要四块：

- 正文阅读区域。
- 上一章 / 下一章。
- 当前书目录抽屉或侧栏。
- 阅读设置：字号、行距、主题色。

阅读设置不需要服务端。首版可以用 `localStorage` 保存到浏览器本地。

### 7.4 章节导航算法

章节导航不要跨书。每个章节页先取同一本书的所有已发布章节，再按 `order` 排序：

```ts
const chapters = (await getCollection("chapters"))
  .filter((chapter) => chapter.data.book === book && !chapter.data.draft)
  .sort((a, b) => a.data.order - b.data.order);

const currentIndex = chapters.findIndex((chapter) => chapter.data.slug === slug);
const prevChapter = chapters[currentIndex - 1] ?? null;
const nextChapter = chapters[currentIndex + 1] ?? null;
```

这个逻辑比依赖文件名更稳，也比把上一章 / 下一章写进 front matter 更好维护。

## 八、Keystatic 编辑方案

Keystatic 的定位是：给文件型内容加一个编辑 UI。它不改变“内容正本是 Git 仓库里的文件”这个原则。

### 8.1 两种使用模式

| 模式 | 适合场景 | 说明 |
|------|----------|------|
| Local mode | 本地写作、调试、首版搭建 | 内容保存到本地文件系统 |
| GitHub mode | 想在网页里编辑并保存到仓库 | 内容通过 GitHub 写回仓库 |

首版建议先用 Local mode 跑通。等页面、schema 和目录结构稳定后，再接 GitHub mode。

### 8.2 Keystatic 配置思路

`keystatic.config.ts` 负责把书籍和章节暴露成可编辑 collection。下面是示意配置：

```ts
import { config, collection, fields } from "@keystatic/core";

export default config({
  storage: {
    kind: "local",
  },
  collections: {
    books: collection({
      label: "书籍",
      slugField: "slug",
      path: "src/content/books/*",
      format: { data: "json" },
      schema: {
        title: fields.text({ label: "书名" }),
        slug: fields.slug({ name: { label: "Slug" } }),
        original: fields.text({ label: "原作", validation: { isRequired: false } }),
        status: fields.select({
          label: "状态",
          options: [
            { label: "计划中", value: "planning" },
            { label: "连载中", value: "serializing" },
            { label: "已完结", value: "completed" },
            { label: "暂停", value: "paused" },
          ],
          defaultValue: "planning",
        }),
        summary: fields.text({ label: "简介", multiline: true }),
        cover: fields.text({ label: "封面路径", validation: { isRequired: false } }),
        tags: fields.array(fields.text({ label: "标签" }), { label: "标签" }),
        createdAt: fields.date({ label: "创建日期" }),
        updatedAt: fields.date({ label: "更新日期" }),
      },
    }),
    chapters: collection({
      label: "章节",
      slugField: "slug",
      path: "src/content/chapters/*/*",
      format: { contentField: "content" },
      schema: {
        book: fields.text({ label: "所属书籍 slug" }),
        title: fields.text({ label: "章节标题" }),
        slug: fields.slug({ name: { label: "Slug" } }),
        order: fields.integer({ label: "章节序号" }),
        draft: fields.checkbox({ label: "草稿" }),
        summary: fields.text({ label: "摘要", multiline: true }),
        createdAt: fields.date({ label: "创建日期" }),
        updatedAt: fields.date({ label: "更新日期" }),
        content: fields.mdx({
          label: "正文",
          extension: "md",
        }),
      },
    }),
  },
});
```

这个配置的重点不是一次写到完美，而是确保 Keystatic 的字段和 Astro 的 schema 对齐。Keystatic 的 `fields.slug` 会同时管理显示文本和文件 slug，落地时要检查它实际写出的文件名、front matter 字段和 Astro schema 是否一致；如果不一致，就把 slug 改成普通 text 字段，再用 Astro schema 做校验。

### 8.3 后台访问控制

Keystatic 不应该被当作公开后台。建议：

- 只给作者自己的 GitHub 账号写权限。
- 管理入口不要放在主导航。
- 如果部署到公网管理界面，额外用 Cloudflare Access 保护 `/keystatic`。
- 不要把 Keystatic 当成多作者协作系统；多作者需要更正式的权限设计。

## 九、搜索方案

Pagefind 适合这个项目，因为它不需要搜索服务端。构建完 Astro 后，再让 Pagefind 扫描 `dist` 目录生成索引：

```bash
astro build
npx pagefind --site dist
```

`package.json` 可以这样写：

```json
{
  "scripts": {
    "dev": "astro dev",
    "build": "astro build && pagefind --site dist",
    "preview": "astro preview"
  }
}
```

搜索页只加载 Pagefind 的静态资源，不需要 API。Pagefind 的官方说明是：它在静态站点生成器之后运行，读取静态 HTML 并生成搜索 bundle。

搜索索引要注意两个边界：

- 如果章节不希望被搜索，模板里不要给正文区域加索引标记，或者用 Pagefind 的排除规则。
- 如果未来有私有草稿，不要把私有内容构建进公开站点。静态搜索没有权限校验。

## 十、版本管理

版本管理仍然交给 Git。Astro 不需要自己实现版本系统。

建议分三层：

| 层级 | 实现 | 首版是否需要 |
|------|------|--------------|
| 作者内部版本 | 每次编辑后 Git commit | 需要 |
| 发布大版本 | 用 Git tag 标记 `v0.1.0`、`v1.0.0` | 建议 |
| 读者可见历史版本 | 按 tag 构建多份站点或生成版本说明页 | 第二阶段 |

首版只需要做到：

```bash
git add src/content/chapters/sanguo-scifi/002-huangjin.md
git commit -m "feat: update sanguo chapter 002"
git tag v0.1.0
git push origin main --tags
```

如果要给读者看版本变化，不建议一开始做逐字 diff 页面。更轻的做法是在书页加“版本说明”，只记录重要发布节点。

## 十一、部署到 Cloudflare Pages

Cloudflare Pages 官方提供 Astro 部署指南。对这个项目来说，配置可以保持很简单：

```text
Build command: npm run build
Build output directory: dist
Root directory: /
```

如果使用 pnpm：

```text
Build command: pnpm build
Build output directory: dist
```

Cloudflare Pages 免费层当前需要注意：

- 每月 500 次构建。
- 免费层同一时间 1 个构建任务。
- 单个 Pages site 最多 20,000 个文件。
- 单个静态资源最大 25 MiB。

你已有一个项目每月大约 300 次 build，那么这个 Astro 小说站首版要控制构建频率。建议不要每改一个字就 push；本地预览确认后，每天集中 push 1-3 次。这样每月新增构建大约 30-90 次，和现有项目合计仍然在免费层范围内。

## 十二、和 Hugo 方案的取舍

| 对比项 | Hugo | Astro + Keystatic |
|--------|------|-------------------|
| 构建速度 | 更快 | 较快，但通常慢于 Hugo |
| 依赖复杂度 | 更低 | 更高，需要 Node 生态 |
| Markdown 正本 | 支持 | 支持 |
| 内容 schema 校验 | 弱，需要自写校验 | 强，Content Collections 原生适合 |
| 网页编辑 UI | 需要接额外 CMS | Keystatic 集成更自然 |
| 阅读器交互 | 可做，但模板体系不如 Astro 顺 | 更自然 |
| 未来接动态能力 | 可以，但不顺 | 更顺 |
| 首版上线速度 | Hugo 更快 | Astro 稍慢 |

如果你的第一目标是“最少折腾、最快上线”，Hugo 仍然更适合。  
如果你的第一目标是“内容结构稳、作者编辑体验好、未来阅读器可扩展”，Astro + Keystatic 更好。

我的判断是：**如果你还没真正开始实现，Astro + Keystatic 值得作为首选试一次；如果你已经用 Hugo 跑通了站点，没必要为了技术洁癖迁移。**

## 十三、风险与边界

### 13.1 工具链更重

Astro、Keystatic、Pagefind 都在 Node 生态里。依赖升级、包管理器、构建缓存、Cloudflare build image 都会比 Hugo 多一点维护成本。

建议固定：

```text
Node.js: 使用 Cloudflare Pages 支持的 LTS 版本
包管理器: pnpm 或 npm 二选一
锁文件: 必须提交 pnpm-lock.yaml 或 package-lock.json
```

### 13.2 Keystatic 不是完整 CMS

Keystatic 很适合单作者或少量编辑维护文件型内容，但它不是订单后台、权限系统、审核系统。不要把它扩展成复杂运营后台。

### 13.3 静态站没有读者权限

只要章节被构建进 `dist`，读者就可能访问。草稿必须在构建阶段过滤掉，不能只靠前端隐藏。

### 13.4 搜索索引会暴露正文

Pagefind 会索引构建后的 HTML。如果正文不想被搜索，就不要把它放入索引范围。私有内容不能进入公开构建产物。

### 13.5 改编作品仍有版权风险

AI 改编不自动获得公开发布权。首批建议只处理公版作品，或者只把非公版作品作为私人草稿保存。这个风险和技术栈无关，但会影响网站能否长期公开运营。

## 十四、实施计划

### Phase 1：验证 Astro 内容结构

目标：确认 Astro 能正确生成书页和章节页。

1. 初始化 Astro 项目。
2. 建 `books` 和 `chapters` 两个 collection。
3. 写 1 本书和 3 个章节样例。
4. 实现首页、书页、章节页。
5. 实现章节排序、上一章 / 下一章。

验收标准：

- `npm run build` 成功。
- 书页章节顺序正确。
- 草稿章节不会出现在生产构建里。

### Phase 2：接入 Keystatic

目标：让作者能用网页 UI 编辑书籍和章节。

1. 安装 Keystatic。
2. 配置 `books` 和 `chapters` collection。
3. 本地打开 `/keystatic` 编辑样例内容。
4. 确认保存后的文件仍符合 Astro schema。
5. 再决定是否切到 GitHub mode。

验收标准：

- 能通过 Keystatic 新增章节。
- 新增章节能被 Astro 构建并显示。
- front matter 字段和 schema 不冲突。

### Phase 3：补阅读体验和搜索

目标：让读者使用体验接近真实小说站。

1. 加 ReaderLayout。
2. 加字号、行距、暗色模式。
3. 加目录抽屉或侧栏。
4. 接 Pagefind 搜索。
5. 添加 RSS、sitemap、robots.txt。

验收标准：

- 移动端阅读舒适。
- 搜索能搜到已发布章节。
- Pagefind 索引不包含草稿。

### Phase 4：部署和版本管理

目标：把站点部署到 Cloudflare Pages，并跑通版本流程。

1. GitHub 仓库连接 Cloudflare Pages。
2. 配置 build command 和 output directory。
3. 本地预览后再 push，避免浪费构建次数。
4. 用 Git tag 标记第一个版本。
5. 在书页补版本说明。

验收标准：

- Cloudflare Pages 构建成功。
- 每月构建次数可控。
- 版本说明能追溯到 Git tag。

## 十五、推荐起步命令

```bash
# 创建 Astro 项目
npm create astro@latest mixtxt-astro
cd mixtxt-astro

# 安装 Keystatic
npm install @keystatic/core @keystatic/astro

# 安装 Pagefind
npm install -D pagefind

# 本地开发
npm run dev

# 构建并生成搜索索引
npm run build
```

如果后续使用 pnpm，则从一开始就统一使用 pnpm，不要混用 npm 和 pnpm。

## 十六、最终建议

这套方案适合你在以下条件下采用：

- 希望内容仍然是 Markdown 文件。
- 不想引入数据库。
- 希望有一个作者可用的网页编辑界面。
- 希望书籍、章节、版本说明有 schema 校验。
- 希望以后把阅读器做得更细，而不是只套一个主题。

如果你只想最快上线，Hugo 更干净。  
如果你想把 AI 改编小说网做成一个长期可维护、可扩展的内容应用，**Astro + Keystatic + Pagefind + Cloudflare Pages 是目前更有成长性的静态方案**。

## 附录 A：参考来源

- [Astro Content Collections](https://docs.astro.build/en/guides/content-collections/)：确认 collection、schema、build-time content、`getCollection()` 等机制。
- [Keystatic Introduction](https://keystatic.com/docs/introduction)：确认 Keystatic 可保存到本地文件系统或 GitHub，并可接入 Astro。
- [Keystatic MDX Field](https://keystatic.com/docs/fields/mdx)：确认可用 `.md` 扩展保存正文内容。
- [Keystatic Slug Field](https://keystatic.com/docs/fields/slug)：确认 slug 字段会生成 URL 友好的 entry slug。
- [Pagefind Running Pagefind](https://pagefind.app/docs/running-pagefind/)：确认 Pagefind 在静态站生成后扫描 HTML 并生成搜索索引。
- [Cloudflare Pages Astro Guide](https://developers.cloudflare.com/pages/framework-guides/deploy-an-astro-site/)：确认 Astro 可部署到 Cloudflare Pages。
- [Cloudflare Pages Limits](https://developers.cloudflare.com/pages/platform/limits/)：确认免费层构建次数、文件数量和单文件大小限制。
