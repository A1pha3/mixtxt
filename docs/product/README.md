# 小说网站技术文档

## 文档结构

```text
docs/product/
├── README.md                              ← 本文件（导航索引）
├── 开发框架方案对比与推荐.md                ← 总览：7 类方案对比与最终推荐
├── 开发框架Next-js.md                     ← 方案 A：Next.js + Supabase 详细设计
├── 开发框架-Payload-CMS详细设计.md         ← 方案 B：Payload CMS 3 + PostgreSQL 详细设计
├── 开发框架-微信小程序详细设计.md           ← 方案 C：微信小程序详细设计
├── 开发框架-微信小程序项目初始化教程.md     ← 方案 C 配套：从零初始化教程
├── 开发框架-Hugo方案可行性评估.md           ← 评估：Hugo 为什么不适合作为主方案
├── AI改编小说网架构.md                     ← 评估：单作者静态小说站的 Hugo 方案
├── 开发框架-Astro-Keystatic详细方案.md      ← 方案 D：Astro + Keystatic 静态内容应用方案
└── 开发框架-Astro-Pages-CMS详细设计.md      ← 方案 E：Astro + Pages CMS 小说创作网站详细设计
```

## 推荐阅读顺序

1. **[方案对比与推荐](./开发框架方案对比与推荐.md)** — 理解项目核心需求和 7 类方案的优劣取舍
2. 根据选定的方案阅读对应的详细设计：
   - **自建站首选**：[Payload CMS 3 详细设计](./开发框架-Payload-CMS详细设计.md)
   - **当前基准方案**：[Next.js + Supabase 详细设计](./开发框架Next-js.md)
   - **微信生态首选**：[微信小程序详细设计](./开发框架-微信小程序详细设计.md) → [项目初始化教程](./开发框架-微信小程序项目初始化教程.md)
3. **参考**：[Hugo 可行性评估](./开发框架-Hugo方案可行性评估.md) — 了解为什么静态站点生成器不适合付费内容平台
4. **轻量静态站专项**：
   - [AI 改编小说网架构](./AI改编小说网架构.md) — 单作者、Markdown、无数据库场景下的 Hugo 方案
   - [Astro + Keystatic 详细方案](./开发框架-Astro-Keystatic详细方案.md) — 需要网页编辑入口和更强内容结构校验时的静态方案
   - [Astro + Pages CMS 详细设计](./开发框架-Astro-Pages-CMS详细设计.md) — 推荐方案：网页编辑、Markdown 正本、无数据库、可直接落地的小说创作网站

## 关键设计约定

以下约定在所有详细设计文档中统一适用：

### VIP 状态 vs 后台角色

- **VIP 是订阅状态，不是角色**。通过 `vip_subscriptions` 表推导，不存储在 `role` 字段
- `role` 仅用于后台权限控制：`user` / `editor` / `admin`
- 管理员（admin）可以同时拥有 VIP 订阅，两个维度互不干扰

### 内容正本策略

- **Next.js 方案**：本地 Markdown 文件为正本，数据库存元数据索引
- **Payload CMS 方案**：CMS/数据库为正本，Markdown 仅作导出格式
- 两种方案不要混用，选定一种后保持一致

### 支付安全

- 权限开通只认服务端支付回调，不认前端状态
- 所有支付回调必须幂等（CAS 模式：只更新 `status = 'pending'` 的记录）
- 余额操作使用原子数据库函数，不在应用层分步扣款 + 写单

### 数据模型核心表

各方案共享以下核心数据概念（字段名可能不同）：

| 概念 | 说明 |
|------|------|
| users | 用户、VIP 状态、角色 |
| books | 书籍元数据、定价 |
| chapters | 章节元数据与正文 |
| purchases | 所有付费行为主记录 |
| vip_subscriptions | VIP 订阅记录 |
| reading_progress | 阅读进度 |
| comments | 评论（可后置） |
