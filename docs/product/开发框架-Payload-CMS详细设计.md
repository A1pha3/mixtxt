# 小说网站开发框架 — Payload CMS 3 + PostgreSQL

> 文档类型：技术架构设计
>
> 推荐方案：Payload CMS 3 + PostgreSQL
>
> 内容正本：**Payload CMS / PostgreSQL**
>
> 目标读者：具备基础编程经验的个人开发者
>
> 项目规模：多本书籍（初期几本，未来可达上百本），AI 写作自动化，支持章节付费 / 整本购买 / VIP
>
> 前置文档：
> - [开发框架Next-js.md](./开发框架Next-js.md)
> - [开发框架方案对比与推荐.md](./开发框架方案对比与推荐.md)

---

## 一、为什么改用 Payload CMS 3

相比“Next.js + Supabase + 自研后台”的路线，Payload CMS 3 更适合这个项目的根本原因不是它更潮，而是它更符合“**内容平台**”的本质。

这个项目真正复杂的部分不在首页、书籍页和章节页，而在：

- 书籍/章节内容建模
- 发布状态与后台管理
- 章节排序、分类、标签、封面、推荐位
- 用户权限与内容访问控制
- 订单、充值、VIP、评论、阅读进度
- AI 生成内容后的人工修订与发布流

如果继续沿用 Next.js + Supabase，你需要自己补：

- Admin 后台
- 内容模型管理
- 字段校验
- 运营编辑体验
- 审核/草稿/发布工作流
- 很多通用管理页面

而 Payload CMS 本身就是为这些能力设计的。

### 1.1 与 Next.js + Supabase 的核心差异

| 对比项 | Next.js + Supabase | Payload CMS 3 |
|--------|-------------------|---------------|
| 后台管理 | 需要自己开发 | ✅ 内建 Admin |
| 内容模型 | 需自己定义 API + UI | ✅ Collection / Globals 开箱即用 |
| 字段管理 | 手写表单与校验 | ✅ 内建字段类型、校验、关联 |
| 草稿/发布 | 需自研 | ✅ 原生支持 draft/version |
| 富文本/媒体管理 | 需自己接 | ✅ 原生支持 |
| 权限控制 | 中间件 + API + RLS 多层拼装 | ✅ Access Control 集中管理 |
| 生命周期 Hook | 需自己拼 | ✅ beforeChange / afterChange / jobs |
| 自定义前台 | ✅ 很强 | ✅ 同样可做 |
| 上手复杂度 | 中 | 中偏低（更少造轮子） |

### 1.2 为什么“Payload 为正本”比“Markdown 为正本”更适合

如果项目目标是长期做内容平台，而不是纯 Git 管理的静态内容仓库，那么 Payload 作为内容正本更合理：

- 编辑、运营、AI 工作流都直接围绕 CMS 运作
- 发布状态只有一处真相，不需要 Markdown / DB 双写同步
- 章节修改后可立即生效，无需导入/同步/解析链路
- 更容易实现草稿、审核、定时发布、推荐位等能力

Markdown 保留为“导出能力”即可，而不应继续作为唯一正本。

---

## 二、技术栈选型

| 层级 | 技术选型 | 选型理由 |
|------|----------|----------|
| Web 框架 | **Payload CMS 3（基于 Next.js 15）** | 同时拥有 CMS 能力与现代 SSR/SEO 能力 |
| CMS / Admin | **Payload Admin** | 内建内容管理后台，减少大量重复开发 |
| 数据库 | **PostgreSQL** | 事务能力强，适合订单、VIP、评论、进度等核心数据 |
| 认证 | **Payload Auth / 用户 Collection** | 可统一后台与前台用户模型 |
| 文件存储 | **S3 / Cloudflare R2** | 封面、插图、富媒体资源 |
| 支付 | **Payjs（初期）** | 国内个人开发者可落地 |
| 搜索 | **Meilisearch（后期接入）** | 中文搜索友好，先不做首发依赖 |
| 部署 | **Railway / Fly.io / Render / VPS Docker** | 比 Vercel + 多服务拼装更像一体化应用 |
| 样式 | **Tailwind CSS + shadcn/ui（可选）** | 补充前台展示层 |
| 定时任务 | **Payload Jobs / 外部 Cron** | AI 生成、定时发布、同步任务 |

### 2.1 部署建议

首发不建议拆太多服务，推荐两种模式：

#### 模式 A：简单稳妥

```text
Payload App（含前台 + Admin + API）
PostgreSQL
R2 / S3
Payjs
```

#### 模式 B：后期扩展

```text
Payload App
PostgreSQL
R2 / S3
Meilisearch
独立 Worker（AI 任务 / 队列任务）
Payjs
```

结论：**Meilisearch 不应成为首发必需依赖**，先把内容、支付、权限闭环跑通。

---

## 三、整体架构设计

### 3.1 架构图

```text
┌──────────────────────────────────────────────────────────────┐
│                        用户访问层                             │
│  Web 前台（书籍页 / 章节页 / 搜索 / 用户中心 / 书架）          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                     Payload CMS 3 应用层                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Admin 后台                                             │  │
│  │ - 书籍管理 / 章节管理 / 用户管理 / 订单管理              │  │
│  │ - 草稿 / 发布 / 推荐位 / 评论审核                        │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 前台页面 / API / Hooks / Jobs                          │  │
│  │ - SSR / ISR 页面                                       │  │
│  │ - 支付接口 / Webhook                                   │  │
│  │ - AI 内容入库 / 发布后同步 / 缓存刷新                   │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬───────────────────────────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ PostgreSQL        │  │ R2 / S3          │  │ Payjs            │
│ - 内容/订单/用户   │  │ - 封面/图片       │  │ - 支付下单/回调   │
│ - 评论/进度/VIP    │  │ - 富媒体资源      │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │ Meilisearch      │
                      │ - 后期接入搜索    │
                      └──────────────────┘
```

### 3.2 关键设计原则

1. **Payload 为唯一内容正本**
2. **前台、后台、API、Hooks 尽量在一个应用内完成**
3. **订单是权限凭证的一部分**，不要把“是否可看”分散到太多地方
4. **支付成功只认服务端回调，不认前端成功提示**
5. **首发以最小闭环为目标：内容发布 + 章节阅读 + 支付 + 权限**
6. **搜索、推荐、运营活动、复杂 AI 工作流放第二阶段**

---

## 四、渲染与页面策略

Payload 3 本质上跑在 Next.js 体系内，因此前台仍然可以使用现代渲染策略。

### 4.1 页面类型与策略

| 页面类型 | 渲染模式 | 说明 |
|----------|----------|------|
| 首页 | SSG / ISR | 内容稳定，适合缓存 |
| 书籍列表页 | ISR | 分类、标签页可定时更新 |
| 书籍详情页 | ISR | 章节列表和简介可缓存 |
| 免费章节 | ISR | 可缓存，兼顾 SEO |
| 付费章节 | SSR / Dynamic | 需逐请求校验访问权限 |
| 用户中心 | SSR | 个性化数据 |
| 书架 / 购买记录 | SSR | 登录后私有数据 |
| Admin 后台 | Payload Admin | 不需要自己单独开发完整后台 |
| API / Webhook | Server | 支付、评论、进度、购买接口 |

### 4.2 为什么付费章节必须动态校验

小说正文一旦被预渲染到静态页面，就存在被绕过付费墙的风险。因此：

- **免费章节**：可以 ISR
- **付费章节**：必须服务端按请求判断权限，再决定返回正文还是付费墙

这也是为什么“内容平台”与“纯静态内容站”在架构上根本不同。

---

## 五、数据模型设计

Payload 推荐以 Collection 为核心建模。下面给出适合本项目的主模型。

### 5.1 Collection 列表

| Collection | 用途 |
|------------|------|
| users | 用户、作者、管理员、VIP 状态 |
| books | 书籍信息 |
| chapters | 章节正文与元数据 |
| categories | 分类 |
| tags | 标签 |
| purchases | 所有付费行为主记录 |
| recharges | 充值流水 |
| vipSubscriptions | VIP 订阅记录 |
| comments | 评论 |
| readingProgress | 阅读进度 |
| bookLikes | 书籍点赞 |
| chapterLikes | 章节点赞 |
| banners / featuredBooks | 首页推荐位（可选） |

### 5.2 users

建议字段：

- `email`
- `username`
- `avatar`
- `bio`
- `role`：`user | editor | admin`
- `isVIP`
- `vipExpiresAt`
- `balance`
- `status`：`active | banned`
- `lastLoginAt`

说明：

- **不建议把 VIP 单独只靠 role 表达**，VIP 是一种付费状态，不是后台权限。
- 后台权限应使用 `role`。
- VIP 应通过 `isVIP + vipExpiresAt` 或 `vipSubscriptions` 推导。

### 5.3 books

建议字段：

- `slug`
- `title`
- `subtitle`
- `authorName`
- `cover`
- `description`
- `status`：`serializing | completed | paused`
- `isPaid`
- `price`
- `chapterPrice`
- `categories`
- `tags`
- `wordCount`
- `chapterCount`
- `isPublished`
- `publishedAt`
- `seoTitle`
- `seoDescription`
- `featured`
- `sortOrder`

### 5.4 chapters

建议字段：

- `book`（relation -> books）
- `slug`
- `title`
- `chapterOrder`
- `content`（richText / lexical 或 markdown）
- `excerpt`
- `isVIP`
- `priceOverride`（可选，默认走 books.chapterPrice）
- `status`：`draft | scheduled | published | archived`
- `publishedAt`
- `scheduledAt`
- `wordCount`
- `isAIGenerated`
- `aiModel`
- `aiPromptVersion`
- `viewCount`
- `likeCount`

说明：

- 如果以阅读体验为优先，正文建议存储为 Payload 支持的结构化 richText 或 markdown 文本。
- 如果 AI 流水线会直接生成 markdown，可用 `textarea + markdown renderer` 的简单模式，后期再升级为富文本。

### 5.5 purchases

这是最关键的交易主表。

建议字段：

- `user`
- `purchaseType`：`chapter | book | vip | recharge`
- `book`（可空）
- `chapter`（可空）
- `amount`
- `paymentMethod`：`wechat | alipay | balance`
- `paymentNo`
- `status`：`pending | completed | failed | refunded`
- `completedAt`
- `meta`（JSON，可放套餐信息、活动信息）

设计原则：

- 所有付费行为统一进 `purchases`
- `recharges` / `vipSubscriptions` 作为衍生数据表，不作为唯一来源
- 权限判断时优先看 `purchases + vipSubscriptions`

### 5.6 vipSubscriptions

字段建议：

- `user`
- `plan`：`monthly | yearly | lifetime`
- `amount`
- `startsAt`
- `expiresAt`
- `status`：`active | expired | cancelled`
- `paymentNo`

### 5.7 comments

字段建议：

- `user`
- `book`
- `chapter`
- `parent`
- `content`
- `status`：`visible | hidden | deleted | pendingReview`
- `likeCount`

### 5.8 readingProgress

字段建议：

- `user`
- `book`
- `chapter`
- `progressPercent`
- `lastPosition`
- `updatedAt`

---

## 六、权限设计

Payload 的优势之一是把权限集中在 Collection Access 中处理，而不是散落在前端、中间件和数据库三层。

### 6.1 后台权限

| 角色 | 权限 |
|------|------|
| user | 无后台权限，仅前台用户 |
| editor | 可创建/编辑书籍、章节、评论审核，但不能处理用户资金 |
| admin | 全权限 |

### 6.2 前台内容访问权限

章节访问判断建议统一封装为一个服务函数：

```ts
canUserAccessChapter(user, chapter, book)
```

判断顺序：

1. 章节不是 VIP -> 直接可看
2. 用户未登录 -> 不可看
3. 用户购买过该章节 -> 可看
4. 用户购买过整本书 -> 可看
5. 用户存在有效 VIP -> 可看
6. 否则不可看

### 6.3 为什么不要把“正文权限”只交给前端

前端隐藏按钮、隐藏跳转都不是安全控制。

真正的权限控制必须在：

- 服务端页面渲染前
- API 返回正文前
- 下载/导出正文前

统一做判断。

---

## 七、支付系统设计

### 7.1 支付目标

首发阶段只做必要闭环：

- 充值
- 单章购买
- 整本购买
- VIP 开通

### 7.2 推荐最小化策略

实际上首发建议只做两种：

- **单章购买**
- **VIP 开通**

不要一开始同时把：

- 余额充值
- 单章购买
- 整本购买
- VIP

四套全部做满，否则状态机会明显变复杂。

### 7.3 支付流程

```text
用户点击购买
   ↓
服务端创建 purchases(pending)
   ↓
返回 Payjs 支付链接/二维码
   ↓
用户完成支付
   ↓
Payjs webhook 回调
   ↓
服务端验签
   ↓
CAS 更新 pending -> completed
   ↓
根据 purchaseType 执行后续动作
   ↓
写入 VIP / 充值流水 / 权限状态
```

### 7.4 幂等性要求

支付回调必须满足：

- 重复回调不会重复加余额
- 重复回调不会重复开 VIP
- 重复回调不会多次创建流水

建议规则：

- `paymentNo` 唯一
- 只允许更新 `status = pending` 的记录
- 所有衍生动作都在“订单成功转 completed 后”执行一次

### 7.5 为什么订单表必须是主凭证

因为最终“你是否有权阅读”不是 UI 决定的，而是交易事实决定的。

- 买了章节 -> 有凭证
- 买了整本 -> 有凭证
- 开了 VIP -> 有订阅凭证

这些都必须能从服务端稳定追溯。

---

## 八、内容发布与 AI 工作流

Payload 方案里，AI 自动化会比 Markdown 同步流更自然。

### 8.1 推荐工作流

```text
AI 生成章节草稿
   ↓
写入 chapters(status=draft, isAIGenerated=true)
   ↓
编辑在 Payload Admin 中修改
   ↓
点击发布
   ↓
afterChange hook 触发
   ├── 更新 books.chapterCount / wordCount
   ├── 清理缓存 / revalidatePath
   └── （后期）同步搜索索引
```

### 8.2 为什么不建议继续以 Git + Markdown 为中心

那套模式适合“静态内容仓库”，但不适合有：

- 草稿
- 审核
- 定时发布
- 多人编辑
- 运营修改
- 订单驱动权限

的内容平台。

### 8.3 可选导出能力

如果你仍然希望保留内容资产可迁移性，可以做：

- 书籍导出为 JSON
- 章节导出为 Markdown ZIP
- 每日/每周自动备份数据库

这样既保留内容可迁移性，又不把 Markdown 变成主工作流负担。

---

## 九、搜索设计

### 9.1 首发策略

**首发不要接 Meilisearch**，先用最小能力：

- 按书名搜索
- 按作者搜索
- 按分类/标签筛选

只要能满足用户找书即可。

### 9.2 第二阶段再加全文搜索

当书籍数量和章节数量明显增长后，再把 `books` 或 `chapters` 同步到 Meilisearch。

推荐顺序：

1. 先只索引 `books`
2. 再评估是否需要索引 `chapters`

原因：章节级全文搜索会显著增加索引规模与维护成本。

---

## 十、评论与互动设计

### 10.1 评论策略

首发建议只做：

- 章节评论
- 删除自己的评论
- 管理员隐藏评论

先不要做：

- 多层嵌套回复
- 敏感词系统
- 举报系统
- 点赞排行

### 10.2 点赞策略

书籍点赞和章节点赞都可以做，但建议后置。对早期产品来说，阅读体验和付费闭环比社交互动更重要。

---

## 十一、项目结构建议

```text
novel-site-payload/
├── src/
│   ├── app/
│   │   ├── (frontend)/
│   │   │   ├── page.tsx
│   │   │   ├── books/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [slug]/
│   │   │   │       ├── page.tsx
│   │   │   │       └── [chapter]/page.tsx
│   │   │   ├── user/
│   │   │   │   ├── login/page.tsx
│   │   │   │   ├── library/page.tsx
│   │   │   │   ├── purchases/page.tsx
│   │   │   │   └── settings/page.tsx
│   │   │   ├── search/page.tsx
│   │   │   └── api/
│   │   │       ├── payment/create/route.ts
│   │   │       ├── payment/notify/route.ts
│   │   │       ├── comments/route.ts
│   │   │       └── progress/route.ts
│   │   └── (payload)/admin/...
│   ├── collections/
│   │   ├── Users.ts
│   │   ├── Books.ts
│   │   ├── Chapters.ts
│   │   ├── Purchases.ts
│   │   ├── VIPSubscriptions.ts
│   │   ├── Comments.ts
│   │   └── ReadingProgress.ts
│   ├── globals/
│   │   ├── SiteSettings.ts
│   │   └── HomepageSettings.ts
│   ├── hooks/
│   │   ├── books/
│   │   ├── chapters/
│   │   └── purchases/
│   ├── access/
│   │   ├── isAdmin.ts
│   │   ├── isEditor.ts
│   │   └── canReadChapter.ts
│   ├── lib/
│   │   ├── payment/
│   │   ├── auth/
│   │   ├── search/
│   │   └── services/
│   ├── components/
│   │   ├── frontend/
│   │   └── ui/
│   └── payload.config.ts
├── scripts/
│   ├── ai-generate.ts
│   ├── import-books.ts
│   └── export-markdown.ts
├── public/
├── Dockerfile
├── docker-compose.yml
└── package.json
```

---

## 十二、Hooks 与自动化

### 12.1 推荐 Hook 列表

#### books / chapters

- `beforeChange`：校验 slug、自动补齐字数
- `afterChange`：更新章节数量、刷新缓存、同步搜索索引
- `afterDelete`：修正统计数据

#### purchases

- `afterChange`：当状态从 pending -> completed 时触发后续动作

### 12.2 Jobs 用途

- AI 批量生成章节
- 定时发布草稿章节
- 定期清理失效订单
- 导出备份
- 同步 Meilisearch 索引

---

## 十三、安全设计

### 13.1 必须遵守的原则

1. **付费正文只能在服务端拿到后再渲染**
2. **支付结果只认 webhook，不认前端轮询结果**
3. **后台权限与前台用户权限分离**
4. **订单、余额、VIP 都不能让客户端直接写**
5. **每种支付回调都必须幂等**
6. **Admin 后台必须限制为 admin / editor 角色**
7. **数据库每日备份**

### 13.2 常见风险

| 风险 | 说明 | 处理方式 |
|------|------|----------|
| 付费正文泄露 | 章节正文被预渲染或下发到客户端 | 付费章节强制服务端动态校验 |
| 重复回调 | 支付平台重复通知 | 订单状态 CAS 更新 |
| 越权后台访问 | 普通用户进入 admin | Payload access 严格限制 |
| 富文本 XSS | 编辑器内容含恶意脚本 | 服务端渲染时过滤危险标签 |
| 对象存储泄露 | 私有资源被公开 | 封面可公开，正文附件默认私有 |

---

## 十四、部署与成本

### 14.1 初期推荐部署

#### 方案 A：Railway

- 部署简单
- PostgreSQL 配套方便
- 适合快速上线

#### 方案 B：Fly.io

- Docker 化较灵活
- 成本可控
- 对长期运行应用比较友好

#### 方案 C：1 台 VPS + Docker

- 成本最低
- 需要自己处理备份、监控、升级
- 适合有一定运维能力的人

### 14.2 初期成本估算

| 服务 | 方案 | 预估成本 |
|------|------|----------|
| 应用托管 | Railway / Fly.io / VPS | $0 ~ $15/月 |
| PostgreSQL | 托管 / 自建 | $0 ~ $15/月 |
| 对象存储 | R2 / S3 | $0 ~ $5/月 |
| Payjs | 按交易抽成 | 按交易量 |
| 搜索 | 首发不接 | $0 |
| **总计** | | **约 $0 ~ $35/月** |

这通常不会高于 “Next.js + Supabase + Meilisearch + 多服务拼装” 的综合维护成本。

---

## 十五、开发路线图

### Phase 1：最小可上线版本（1-2 周）

- [ ] 初始化 Payload CMS 3 项目
- [ ] 建立 users / books / chapters / purchases Collections
- [ ] 完成首页、书籍页、章节页
- [ ] 实现免费章节 + 付费章节动态校验
- [ ] 接 Payjs 创建订单与回调
- [ ] 完成最小 Admin 内容管理闭环

### Phase 2：用户系统（1 周）

- [ ] 登录 / 注册
- [ ] 用户中心
- [ ] 购买记录
- [ ] 书架
- [ ] 阅读进度

### Phase 3：内容运营（1 周）

- [ ] 分类 / 标签
- [ ] 推荐位
- [ ] 草稿 / 发布 / 定时发布
- [ ] 评论系统

### Phase 4：AI 自动化（1 周）

- [ ] AI 写作脚本接入
- [ ] AI 生成草稿入库
- [ ] 编辑审核发布流
- [ ] Hook 自动刷新缓存

### Phase 5：增强能力（后续）

- [ ] Meilisearch 搜索
- [ ] 整本购买
- [ ] 充值余额
- [ ] 更细运营系统
- [ ] 数据导出 / Markdown 导出

---

## 十六、最终结论

对于“多本小说 + AI 自动化 + 章节付费 + 用户中心 + 后台运营”的项目，**Payload CMS 3 + PostgreSQL** 比纯粹的 Next.js + Supabase 更像一个现成可扩展的底座。

它最核心的价值不是性能，而是：

- **后台和内容模型开箱即用**
- **实现更简单**
- **运营更顺手**
- **长期扩展成本更低**

如果你的目标是：

- 做自己的长期品牌站
- 不想在后台基础设施上花太多时间
- 希望 AI 工作流与内容运营自然整合

那么 Payload CMS 3 是目前更合适的主架构选择。

如果你的目标只是最低成本 MVP，则可以退一步选 PocketBase + Nuxt 3；但如果你已经决定认真做长期站，Payload 会是更稳的中长期答案。

---

> 文档版本：1.0
>
> 创建日期：2026-04-28
>
> 最后更新：2026-04-28
>
> 说明：本方案按“Payload 为内容正本”设计，优先服务内容运营、后台能力和长期扩展，而非保留 Markdown 中心工作流。