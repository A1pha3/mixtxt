# 小说网站开发框架 — Next.js App Router + Supabase

> 文档类型：技术架构设计
>
> 推荐方案：Next.js App Router + Supabase
>
> 目标读者：具备基础编程经验的个人开发者
>
> 项目规模：多本书籍（初期几本，未来可达上百本），AI 写作自动化
>
> 前置文档：[开发框架方案对比与推荐.md](./开发框架方案对比与推荐.md)

---

## 一、为什么从 Astro 切换到 Next.js

### 1.1 Astro 方案的核心问题

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| SSG + 付费墙矛盾 | 🔴 致命 | 付费章节内容在构建时写入 HTML，源码可绕过付费墙 |
| 全站重建 | 🔴 严重 | 每次内容更新需全站 SSG 重建，上百本书时构建极慢 |
| 动态交互弱 | 🟡 中等 | 大量岛屿架构削弱 SSG 性能优势，管理后台体验差 |
| Content Collections 未利用 | 🟡 中等 | 从数据库读内容而非本地 Markdown，浪费 Astro 核心功能 |

### 1.2 Next.js App Router 的优势

| 对比项 | Astro SSG | Next.js App Router |
|--------|-----------|-------------------|
| 付费内容保护 | ❌ SSG 泄露 | ✅ Server Components 服务端渲染 |
| 内容更新 | ❌ 全站重建 | ✅ ISR 按需再生 |
| 动态交互 | ⚠️ 需大量岛屿 | ✅ RSC + Client Components 自然混合 |
| 认证中间件 | ⚠️ 手动处理 | ✅ middleware.ts 统一拦截 |
| 支付 Webhook | ⚠️ Edge Functions | ✅ Route Handlers 原生支持 |
| 管理后台 | ❌ SSG 不适合 | ✅ 同一项目中 Client Components |
| 免费部署 | ✅ Vercel 免费层 | ✅ Vercel 免费层 |
| 学习曲线 | 低 | 中（RSC 心智模型需适应） |

---

## 二、技术栈选型

| 层级 | 技术选型 | 选型理由 |
|------|----------|----------|
| 前端框架 | **Next.js 15 (App Router)** | RSC + ISR + Server Actions，一站式全栈 |
| 后端服务 | **Supabase** | PostgreSQL + Auth + Storage，一站式 BaaS |
| 数据库 | **Supabase PostgreSQL** | 500MB 免费额度，RLS 权限控制 |
| 用户认证 | **Supabase Auth** | Supabase 管理用户和会话，@supabase/ssr 处理 SSR cookie |
| 文件存储 | **Supabase Storage** | 封面、图片存储 |
| 搜索 | **Meilisearch** | 中文搜索友好，开源可自托管（注：非 Supabase 官方一方集成，需独立部署或使用 Meilisearch Cloud） |
| 支付接入 | **Payjs（初期）/ 微信支付宝直连（后期）** | 国内支付，个人可用 |
| 部署平台 | **Vercel** | Next.js 原生支持，免费层 |
| 样式方案 | **Tailwind CSS + shadcn/ui** | 开发效率高，组件库完善 |

---

## 三、架构设计

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         本地开发环境                                  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    content/ 目录                               │  │
│  │  - 本地 Markdown 文件（正本，source of truth）                 │  │
│  │  - meta.json 元数据                                           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │ Git push                             │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                     GitHub 仓库                                │  │
│  │  - 代码和内容一起版本控制                                      │  │
│  │  - GitHub Actions 自动化                                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
             ┌─────────────────┴──────────────────┐
             ▼                                    ▼
┌──────────────────────────┐    ┌────────────────────────────────────┐
│    Supabase 云服务        │    │           Vercel                   │
│  ┌────────────────────┐  │    │  ┌──────────────────────────────┐  │
│  │   PostgreSQL        │  │    │  │   Next.js App Router          │  │
│  │   - 用户/订单数据    │  │    │  │   - SSG: 首页/列表/免费章节  │  │
│  │   - 章节元数据索引   │  │    │  │   - SSR: 付费章节（权限校验） │  │
│  │   - 评论/进度       │  │    │  │   - ISR: 书籍详情（按需更新） │  │
│  ├────────────────────┤  │    │  │   - API: 支付/评论/管理       │  │
│  │   Auth             │  │    │  └──────────────────────────────┘  │
│  ├────────────────────┤  │    └────────────────────────────────────┘
│  │   Storage          │  │
│  ├────────────────────┤  │    ┌────────────────────────────────────┐
│  │   Meilisearch      │  │    │         Payjs / 微信支付宝         │
│  │   (搜索集成)        │  │    │   - 扫码支付                      │
│  └────────────────────┘  │    │   - Webhook 回调                  │
└──────────────────────────┘    └────────────────────────────────────┘
```

### 3.2 渲染策略

| 页面类型 | 渲染模式 | 说明 |
|----------|----------|------|
| 首页、书籍列表 | SSG | 内容稳定，构建时生成，CDN 缓存 |
| 书籍详情页 | ISR | `revalidate: 3600`，每小时更新 |
| 免费章节 | ISR | `revalidate: 600`，每10分钟更新 |
| 付费章节 | SSR | 服务端实时校验权限，内容不缓存 |
| 用户中心 | SSR | 需要认证，动态内容 |
| 管理后台 | CSR | 纯客户端渲染，大量交互 |
| API 路由 | Server | Route Handlers 处理支付回调等 |

---

## 四、数据库设计

### 4.1 与 Astro 方案的关键差异

1. **chapters 表不存 content 字段**：内容从本地 Markdown 通过构建时读取，数据库只存元数据和索引
2. **修复了 balances 表 RLS 漏洞**：禁止用户直接 UPDATE 余额
3. **修复了 deduct_balance 竞态条件**：使用原子操作
4. **移除了 PostgreSQL 中文全文搜索**（zhparser 配置门槛高、Supabase 托管环境不易维护）：改用 Meilisearch
5. **purchases 表统一记录所有付费行为**：`purchase_type` 区分 chapter / book / vip / recharge；`recharges` 与 `vip_subscriptions` 作为衍生流水/订阅状态表，主交易记录都在 purchases。支付回调只需查一张表

### 4.2 数据表设计

#### 用户相关

```sql
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username TEXT UNIQUE,
  avatar_url TEXT,
  bio TEXT,
  role TEXT DEFAULT 'user' CHECK (role IN ('user', 'editor', 'admin')),
  vip_expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE balances (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  balance DECIMAL(10, 2) DEFAULT 0.00 CHECK (balance >= 0),
  total_recharged DECIMAL(10, 2) DEFAULT 0.00,
  total_spent DECIMAL(10, 2) DEFAULT 0.00,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE balances ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own balance"
  ON balances FOR SELECT
  USING (auth.uid() = user_id);

-- 注意：不设 INSERT/UPDATE/DELETE 策略，余额变更只允许通过 SECURITY DEFINER 函数（add_balance/deduct_balance）操作
-- 初始余额行由 handle_new_user 触发器创建
```

#### 书籍相关

```sql
CREATE TABLE books (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  author_id UUID REFERENCES auth.users(id),
  author_name TEXT NOT NULL,
  cover_url TEXT,
  description TEXT,
  status TEXT DEFAULT 'serializing' CHECK (status IN ('serializing', 'completed', 'paused')),

  is_paid BOOLEAN DEFAULT FALSE,
  price DECIMAL(8, 2) DEFAULT 0.00,
  chapter_price DECIMAL(8, 2) DEFAULT 0.00,

  view_count INTEGER DEFAULT 0,
  like_count INTEGER DEFAULT 0,
  chapter_count INTEGER DEFAULT 0,

  meta_title TEXT,
  meta_description TEXT,

  is_published BOOLEAN DEFAULT FALSE,
  is_deleted BOOLEAN DEFAULT FALSE,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE chapters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  title TEXT NOT NULL,
  local_file_path TEXT NOT NULL,
  word_count INTEGER DEFAULT 0,

  chapter_order INTEGER NOT NULL,
  is_published BOOLEAN DEFAULT FALSE,
  is_vip BOOLEAN DEFAULT FALSE,

  view_count INTEGER DEFAULT 0,
  like_count INTEGER DEFAULT 0,

  is_ai_generated BOOLEAN DEFAULT FALSE,
  ai_model TEXT,

  is_deleted BOOLEAN DEFAULT FALSE,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(book_id, slug),
  UNIQUE(book_id, chapter_order)
);

CREATE INDEX idx_chapters_book ON chapters(book_id, chapter_order);
CREATE INDEX idx_chapters_published ON chapters(book_id, is_published, chapter_order);
CREATE INDEX idx_chapters_local_path ON chapters(local_file_path);

CREATE TABLE categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  sort_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE book_categories (
  book_id UUID REFERENCES books(id) ON DELETE CASCADE,
  category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
  PRIMARY KEY (book_id, category_id)
);

CREATE TABLE book_tags (
  book_id UUID REFERENCES books(id) ON DELETE CASCADE,
  tag_id UUID REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (book_id, tag_id)
);
```

#### 交易相关

```sql
CREATE TABLE purchases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),

  purchase_type TEXT NOT NULL CHECK (purchase_type IN ('book', 'chapter', 'vip', 'recharge')),

  book_id UUID REFERENCES books(id),
  chapter_id UUID REFERENCES chapters(id),

  amount DECIMAL(10, 2) NOT NULL,

  payment_no TEXT UNIQUE,
  payment_method TEXT CHECK (payment_method IN ('wechat', 'alipay', 'balance')),

  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),

  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX idx_purchases_user ON purchases(user_id, created_at DESC);

CREATE TABLE recharges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  amount DECIMAL(10, 2) NOT NULL,
  payment_no TEXT UNIQUE,
  payment_method TEXT CHECK (payment_method IN ('wechat', 'alipay')),
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE vip_subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  plan TEXT NOT NULL CHECK (plan IN ('monthly', 'yearly', 'lifetime')),
  amount DECIMAL(10, 2) NOT NULL,
  starts_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  payment_no TEXT,
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 互动相关

```sql
CREATE TABLE comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
  book_id UUID REFERENCES books(id) ON DELETE CASCADE,
  parent_id UUID REFERENCES comments(id),
  content TEXT NOT NULL,

  like_count INTEGER DEFAULT 0,
  is_deleted BOOLEAN DEFAULT FALSE,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_comments_chapter ON comments(chapter_id, created_at DESC);
CREATE INDEX idx_comments_book ON comments(book_id, created_at DESC);

CREATE TABLE reading_progress (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  progress INTEGER DEFAULT 0,
  last_position INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(user_id, chapter_id)
);

CREATE TABLE book_likes (
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  book_id UUID REFERENCES books(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, book_id)
);

CREATE TABLE chapter_likes (
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, chapter_id)
);
```

### 4.3 RLS 策略

```sql
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE books ENABLE ROW LEVEL SECURITY;
ALTER TABLE chapters ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchases ENABLE ROW LEVEL SECURITY;
ALTER TABLE recharges ENABLE ROW LEVEL SECURITY;
ALTER TABLE vip_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE reading_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE book_likes ENABLE ROW LEVEL SECURITY;
ALTER TABLE chapter_likes ENABLE ROW LEVEL SECURITY;

-- user_profiles：公开字段所有人可读，自己可改
CREATE POLICY "Profiles are viewable by everyone"
  ON user_profiles FOR SELECT
  USING (true);

CREATE POLICY "Users can update own profile"
  ON user_profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- 注意：不允许客户端修改 role / vip_expires_at，需通过 SECURITY DEFINER 函数或 admin 客户端
-- VIP 不是 role，而是订阅状态。role 只用于后台权限（user / editor / admin）
-- VIP 状态通过 vip_subscriptions 表推导，不存储在 role 字段中

CREATE POLICY "Public books are viewable by everyone"
  ON books FOR SELECT
  USING (is_published = true AND is_deleted = false);

CREATE POLICY "Admins and editors can manage books"
  ON books FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles
      WHERE id = auth.uid() AND role IN ('admin', 'editor')
    )
  );

CREATE POLICY "Published chapters viewable with access check"
  ON chapters FOR SELECT
  USING (
    is_published = true
    AND is_deleted = false
    AND (
      is_vip = false
      OR EXISTS (
        SELECT 1 FROM purchases
        WHERE purchases.user_id = auth.uid()
        AND purchases.chapter_id = chapters.id
        AND purchases.status = 'completed'
      )
      OR EXISTS (
        SELECT 1 FROM purchases
        WHERE purchases.user_id = auth.uid()
        AND purchases.book_id = chapters.book_id
        AND purchases.purchase_type = 'book'
        AND purchases.status = 'completed'
      )
      OR EXISTS (
        SELECT 1 FROM vip_subscriptions
        WHERE vip_subscriptions.user_id = auth.uid()
        AND vip_subscriptions.status = 'active'
        AND vip_subscriptions.expires_at > NOW()
      )
    )
  );

CREATE POLICY "Admins and editors can manage chapters"
  ON chapters FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles
      WHERE id = auth.uid() AND role IN ('admin', 'editor')
    )
  );

-- purchases：用户可查询自己的订单，但不允许直接 INSERT/UPDATE（必须走服务端 Route Handler，由 admin client 写入）
CREATE POLICY "Users can view own purchases"
  ON purchases FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Admins and editors can manage purchases"
  ON purchases FOR ALL
  USING (
    EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role IN ('admin', 'editor'))
  );

-- recharges：同上
CREATE POLICY "Users can view own recharges"
  ON recharges FOR SELECT
  USING (auth.uid() = user_id);

-- vip_subscriptions：用户可查询自己的订阅
CREATE POLICY "Users can view own vip subscriptions"
  ON vip_subscriptions FOR SELECT
  USING (auth.uid() = user_id);

-- reading_progress：用户读写自己的进度
CREATE POLICY "Users can view own reading progress"
  ON reading_progress FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can upsert own reading progress"
  ON reading_progress FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own reading progress"
  ON reading_progress FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- 点赞：用户可读所有人的点赞，只能管理自己的
CREATE POLICY "Likes are viewable by everyone"
  ON book_likes FOR SELECT USING (true);
CREATE POLICY "Users can manage own book likes"
  ON book_likes FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Chapter likes are viewable by everyone"
  ON chapter_likes FOR SELECT USING (true);
CREATE POLICY "Users can manage own chapter likes"
  ON chapter_likes FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view comments"
  ON comments FOR SELECT
  USING (is_deleted = false);

CREATE POLICY "Users can insert own comments"
  ON comments FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own comments"
  ON comments FOR DELETE
  USING (auth.uid() = user_id);

CREATE POLICY "Admins and editors can manage comments"
  ON comments FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles
      WHERE id = auth.uid() AND role IN ('admin', 'editor')
    )
  );
```

### 4.4 数据库函数

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.user_profiles (id) VALUES (NEW.id);
  INSERT INTO public.balances (user_id) VALUES (NEW.id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

CREATE OR REPLACE FUNCTION update_book_chapter_count()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE books
  SET chapter_count = (
    SELECT COUNT(*) FROM chapters
    WHERE book_id = COALESCE(NEW.book_id, OLD.book_id)
      AND is_published = true AND is_deleted = false
  ),
  updated_at = NOW()
  WHERE id = COALESCE(NEW.book_id, OLD.book_id);
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE TRIGGER on_chapter_change
  AFTER INSERT OR UPDATE OR DELETE ON chapters
  FOR EACH ROW EXECUTE FUNCTION update_book_chapter_count();

-- 充值：使用 UPSERT 避免触发器尚未跑完时余额行不存在
CREATE OR REPLACE FUNCTION add_balance(p_user_id UUID, p_amount DECIMAL)
RETURNS VOID AS $$
BEGIN
  IF p_amount <= 0 THEN
    RAISE EXCEPTION 'Amount must be positive';
  END IF;

  INSERT INTO balances (user_id, balance, total_recharged)
  VALUES (p_user_id, p_amount, p_amount)
  ON CONFLICT (user_id) DO UPDATE
  SET balance = balances.balance + EXCLUDED.balance,
      total_recharged = balances.total_recharged + EXCLUDED.total_recharged,
      updated_at = NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- 扣款：原子 UPDATE + 余额检查；失败返回 FALSE
CREATE OR REPLACE FUNCTION deduct_balance(p_user_id UUID, p_amount DECIMAL)
RETURNS BOOLEAN AS $$
DECLARE
  affected INTEGER;
BEGIN
  IF p_amount <= 0 THEN
    RAISE EXCEPTION 'Amount must be positive';
  END IF;

  UPDATE balances
  SET balance = balance - p_amount,
      total_spent = total_spent + p_amount,
      updated_at = NOW()
  WHERE user_id = p_user_id AND balance >= p_amount;

  GET DIAGNOSTICS affected = ROW_COUNT;
  RETURN affected = 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- 原子余额购买：在单个事务中完成扣款 + 创建订单，避免中间状态
CREATE OR REPLACE FUNCTION purchase_with_balance(
  p_user_id UUID,
  p_purchase_type TEXT,
  p_book_id UUID,
  p_chapter_id UUID,
  p_amount DECIMAL
)
RETURNS TABLE (success BOOLEAN, purchase_id UUID) AS $$
DECLARE
  v_deducted BOOLEAN;
  v_purchase_id UUID;
BEGIN
  IF p_amount <= 0 THEN
    RAISE EXCEPTION 'Amount must be positive';
  END IF;

  -- 先扣款
  v_deducted := deduct_balance(p_user_id, p_amount);
  IF NOT v_deducted THEN
    RETURN QUERY SELECT false, NULL::UUID;
    RETURN;
  END IF;

  -- 再创建订单
  INSERT INTO purchases (user_id, purchase_type, book_id, chapter_id, amount, payment_method, status, completed_at)
  VALUES (p_user_id, p_purchase_type, p_book_id, p_chapter_id, p_amount, 'balance', 'completed', NOW())
  RETURNING id INTO v_purchase_id;

  RETURN QUERY SELECT true, v_purchase_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;
```

---

## 五、项目结构

```
novel-site/
├── content/                              # 本地 Markdown 内容（正本）
│   ├── my-first-book/
│   │   ├── meta.json
│   │   └── chapters/
│   │       ├── chapter-1.md
│   │       └── chapter-2.md
│   └── another-book/
│       ├── meta.json
│       └── chapters/
├── src/
│   ├── app/                              # App Router 页面
│   │   ├── layout.tsx                    # 根布局
│   │   ├── page.tsx                      # 首页
│   │   ├── globals.css
│   │   ├── books/
│   │   │   ├── page.tsx                  # 书籍列表 (SSG)
│   │   │   └── [slug]/
│   │   │       ├── page.tsx              # 书籍详情 (ISR)
│   │   │       └── [chapter]/
│   │   │           └── page.tsx          # 章节阅读 (SSR/ISR)
│   │   ├── categories/
│   │   │   └── [slug]/page.tsx
│   │   ├── tags/
│   │   │   └── [slug]/page.tsx
│   │   ├── search/page.tsx
│   │   ├── user/
│   │   │   ├── login/page.tsx
│   │   │   ├── register/page.tsx
│   │   │   ├── profile/page.tsx          # SSR
│   │   │   ├── library/page.tsx          # SSR
│   │   │   ├── purchases/page.tsx        # SSR
│   │   │   ├── recharge/page.tsx         # SSR
│   │   │   └── settings/page.tsx         # SSR
│   │   ├── admin/                        # 管理后台 (CSR)
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── books/page.tsx
│   │   │   ├── chapters/page.tsx
│   │   │   ├── users/page.tsx
│   │   │   └── orders/page.tsx
│   │   └── api/
│   │       ├── payment/
│   │       │   ├── create/route.ts       # 创建支付订单
│   │       │   └── notify/route.ts       # 支付回调
│   │       ├── comments/route.ts
│   │       └── revalidate/route.ts       # ISR 按需刷新
│   ├── components/
│   │   ├── ui/                           # shadcn/ui 组件
│   │   ├── BookCard.tsx
│   │   ├── ChapterList.tsx
│   │   ├── CommentSection.tsx
│   │   ├── Paywall.tsx
│   │   ├── ReadingProgress.tsx
│   │   └── layout/
│   │       ├── Header.tsx
│   │       ├── Footer.tsx
│   │       └── Sidebar.tsx
│   ├── lib/
│   │   ├── supabase/
│   │   │   ├── client.ts                # 浏览器端 Supabase 客户端
│   │   │   ├── server.ts                # 服务端 Supabase 客户端
│   │   │   └── admin.ts                 # Admin 客户端（Service Role）
│   │   ├── auth.ts                       # Supabase Auth 工具函数
│   │   ├── content.ts                    # 本地 Markdown 读取工具
│   │   ├── payment.ts                    # Payjs 支付工具
│   │   ├── meilisearch.ts               # 搜索客户端
│   │   └── utils.ts
│   ├── types/
│   │   ├── database.ts                   # Supabase 生成的类型
│   │   └── content.ts                    # 内容相关类型
│   └── content/                          # Next.js Content Layer（可选）
├── scripts/
│   ├── ai-generate.ts                    # AI 生成脚本
│   ├── sync-to-supabase.ts              # 同步元数据到数据库
│   └── sync-to-meilisearch.ts           # 同步搜索索引
├── public/
│   └── covers/                           # 书籍封面
├── middleware.ts                          # 认证中间件
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

---

## 六、核心功能实现

### 6.1 Supabase 客户端配置

```typescript
// src/lib/supabase/client.ts
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
```

```typescript
// src/lib/supabase/server.ts
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch {
            // middleware 中调用时会忽略
          }
        },
      },
    }
  )
}
```

```typescript
// src/lib/supabase/admin.ts
import { createClient } from '@supabase/supabase-js'

export const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!,
  { auth: { persistSession: false } }
)
```

### 6.2 认证中间件

```typescript
// middleware.ts
import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          supabaseResponse = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  const { data: { user } } = await supabase.auth.getUser()

  const protectedPaths = ['/user/profile', '/user/library', '/user/purchases', '/user/recharge', '/user/settings']
  const adminPaths = ['/admin']

  if (protectedPaths.some(p => request.nextUrl.pathname.startsWith(p)) && !user) {
    return NextResponse.redirect(new URL('/user/login', request.url))
  }

  if (adminPaths.some(p => request.nextUrl.pathname.startsWith(p))) {
    if (!user) {
      return NextResponse.redirect(new URL('/user/login', request.url))
    }
    const { data: profile } = await supabase
      .from('user_profiles')
      .select('role')
      .eq('id', user.id)
      .single()

    if (!profile || !['admin', 'editor'].includes(profile.role)) {
      return NextResponse.redirect(new URL('/', request.url))
    }
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
```

### 6.3 本地内容读取

```typescript
// src/lib/content.ts
import * as fs from 'fs'
import * as path from 'path'
import matter from 'gray-matter'

interface ChapterFrontmatter {
  title: string
  slug: string
  order: number
  is_vip: boolean
  is_published: boolean
  created_at: string
  ai_model?: string
}

interface BookMeta {
  slug: string
  title: string
  author_name: string
  description: string
  cover_url?: string
  status: 'serializing' | 'completed' | 'paused'
  is_paid: boolean
  price: number
  chapter_price: number
  categories: string[]
  tags: string[]
}

const CONTENT_DIR = path.join(process.cwd(), 'content')

export function getAllBooks(): BookMeta[] {
  if (!fs.existsSync(CONTENT_DIR)) return []

  return fs.readdirSync(CONTENT_DIR)
    .filter(dir => {
      const metaPath = path.join(CONTENT_DIR, dir, 'meta.json')
      return fs.existsSync(metaPath)
    })
    .map(dir => {
      const metaPath = path.join(CONTENT_DIR, dir, 'meta.json')
      return JSON.parse(fs.readFileSync(metaPath, 'utf-8')) as BookMeta
    })
}

export function getBookMeta(slug: string): BookMeta | null {
  const metaPath = path.join(CONTENT_DIR, slug, 'meta.json')
  if (!fs.existsSync(metaPath)) return null
  return JSON.parse(fs.readFileSync(metaPath, 'utf-8')) as BookMeta
}

export function getBookChapters(bookSlug: string): Array<ChapterFrontmatter & { content: string }> {
  const chaptersDir = path.join(CONTENT_DIR, bookSlug, 'chapters')
  if (!fs.existsSync(chaptersDir)) return []

  return fs.readdirSync(chaptersDir)
    .filter(f => f.endsWith('.md'))
    .sort()
    .map(file => {
      const filePath = path.join(chaptersDir, file)
      const raw = fs.readFileSync(filePath, 'utf-8')
      const { data, content } = matter(raw)
      return { ...(data as ChapterFrontmatter), content }
    })
    .filter(c => c.is_published)
    .sort((a, b) => a.order - b.order)
}

export function getChapterContent(
  bookSlug: string,
  chapterSlug: string
): (ChapterFrontmatter & { content: string }) | null {
  const chaptersDir = path.join(CONTENT_DIR, bookSlug, 'chapters')
  if (!fs.existsSync(chaptersDir)) return null

  // 优化：先尝试文件名直接匹配（约定文件名 = slug.md）
  const directPath = path.join(chaptersDir, `${chapterSlug}.md`)
  if (fs.existsSync(directPath)) {
    const raw = fs.readFileSync(directPath, 'utf-8')
    const { data, content } = matter(raw)
    return { ...(data as ChapterFrontmatter), content }
  }

  // 回退：遍历查找匹配的 slug（兼容非标准命名）
  const targetFile = fs.readdirSync(chaptersDir)
    .find(f => {
      if (!f.endsWith('.md')) return false
      const raw = fs.readFileSync(path.join(chaptersDir, f), 'utf-8')
      const { data } = matter(raw)
      return (data as ChapterFrontmatter).slug === chapterSlug
    })

  if (!targetFile) return null

  const raw = fs.readFileSync(path.join(chaptersDir, targetFile), 'utf-8')
  const { data, content } = matter(raw)
  return { ...(data as ChapterFrontmatter), content }
}
```

### 6.4 页面实现

#### 首页（SSG）

```typescript
// src/app/page.tsx
import { getAllBooks } from '@/lib/content'
import { BookCard } from '@/components/BookCard'

export default function HomePage() {
  const books = getAllBooks()

  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">全部书籍</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {books.map(book => (
          <BookCard key={book.slug} book={book} />
        ))}
      </div>
    </main>
  )
}
```

#### 书籍详情（ISR）

```typescript
// src/app/books/[slug]/page.tsx
import { getAllBooks, getBookMeta, getBookChapters } from '@/lib/content'
import { createClient } from '@/lib/supabase/server'
import { notFound } from 'next/navigation'
import { ChapterList } from '@/components/ChapterList'

export const revalidate = 3600

export async function generateStaticParams() {
  const books = getAllBooks()
  return books.map(book => ({ slug: book.slug }))
}

export default async function BookDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const meta = getBookMeta(slug)
  if (!meta) notFound()

  const chapters = getBookChapters(slug)

  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  // 通过 slug 拿到 books.id（BookMeta 不含 id，必须查库）
  const { data: bookRow } = await supabase
    .from('books')
    .select('id')
    .eq('slug', slug)
    .single()
  const bookId = bookRow?.id

  // VIP 状态从 vip_subscriptions 推导，不从 role 字段判断
  let purchasedChapterIds: Set<string> = new Set()
  let isVip = false
  let hasBookPurchase = false

  if (user) {
    const { data: purchases } = await supabase
      .from('purchases')
      .select('chapter_id, book_id, purchase_type')
      .eq('user_id', user.id)
      .eq('status', 'completed')

    purchasedChapterIds = new Set(
      purchases?.filter(p => p.purchase_type === 'chapter' && p.chapter_id)
        .map(p => p.chapter_id as string) ?? []
    )

    hasBookPurchase = !!purchases?.some(
      p => p.purchase_type === 'book' && p.book_id === bookId
    )

    // 从 vip_subscriptions 表判断 VIP 状态，不使用 role 字段
    const { data: vipSub } = await supabase
      .from('vip_subscriptions')
      .select('id')
      .eq('user_id', user.id)
      .eq('status', 'active')
      .gt('expires_at', new Date().toISOString())
      .maybeSingle()

    isVip = !!vipSub
  }

  // 免费书籍视为已"购买"，付费书籍则需要购买记录或 VIP
  const isBookPurchased = !meta.is_paid || hasBookPurchase || isVip

  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-2">{meta.title}</h1>
      <p className="text-gray-500 mb-4">{meta.author_name}</p>
      <p className="text-gray-700 mb-8">{meta.description}</p>
      <ChapterList
        chapters={chapters}
        bookSlug={slug}
        isBookPurchased={isBookPurchased}
        isVip={isVip}
        purchasedChapterIds={purchasedChapterIds}
      />
    </main>
  )
}
```

#### 章节阅读（SSR for VIP / ISR for free）

```typescript
// src/app/books/[slug]/[chapter]/page.tsx
import { getBookMeta, getChapterContent } from '@/lib/content'
import { createClient } from '@/lib/supabase/server'
import { notFound, redirect } from 'next/navigation'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { Paywall } from '@/components/Paywall'

interface Props {
  params: Promise<{ slug: string; chapter: string }>
}

// 免费章节走 ISR；付费章节内的权限校验是 dynamic 的，但页面壳本身可缓存
export const revalidate = 600

export default async function ChapterPage({ params }: Props) {
  const { slug, chapter: chapterSlug } = await params

  const meta = getBookMeta(slug)
  if (!meta) notFound()

  const chapter = getChapterContent(slug, chapterSlug)
  if (!chapter) notFound()

  // 免费章节直接渲染
  if (!chapter.is_vip) {
    return (
      <main className="container mx-auto px-4 py-8 max-w-3xl">
        <h1 className="text-2xl font-bold mb-6">{chapter.title}</h1>
        <MarkdownRenderer content={chapter.content} />
      </main>
    )
  }

  // 付费章节：force-dynamic，逐请求校验
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect(`/user/login?redirect=/books/${slug}/${chapterSlug}`)
  }

  // 通过 slug 拿到 books.id 和 chapters.id
  const { data: bookRow } = await supabase
    .from('books').select('id').eq('slug', slug).single()
  if (!bookRow) notFound()

  const { data: chapterRow } = await supabase
    .from('chapters')
    .select('id')
    .eq('slug', chapterSlug)
    .eq('book_id', bookRow.id)
    .single()
  if (!chapterRow) notFound()

  // 三种权限来源：单章购买、整本购买、VIP
  const [chapterPurchase, bookPurchase, vipSub] = await Promise.all([
    supabase.from('purchases').select('id')
      .eq('user_id', user.id).eq('chapter_id', chapterRow.id)
      .eq('purchase_type', 'chapter').eq('status', 'completed').maybeSingle(),
    supabase.from('purchases').select('id')
      .eq('user_id', user.id).eq('book_id', bookRow.id)
      .eq('purchase_type', 'book').eq('status', 'completed').maybeSingle(),
    supabase.from('vip_subscriptions').select('id')
      .eq('user_id', user.id).eq('status', 'active')
      .gt('expires_at', new Date().toISOString()).maybeSingle(),
  ])

  const hasAccess = !!chapterPurchase.data || !!bookPurchase.data || !!vipSub.data

  if (!hasAccess) {
    return (
      <main className="container mx-auto px-4 py-8 max-w-3xl">
        <h1 className="text-2xl font-bold mb-6">{chapter.title}</h1>
        <Paywall
          bookSlug={slug}
          chapterSlug={chapterSlug}
          chapterTitle={chapter.title}
          price={meta.chapter_price}
        />
      </main>
    )
  }

  return (
    <main className="container mx-auto px-4 py-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-6">{chapter.title}</h1>
      <MarkdownRenderer content={chapter.content} />
    </main>
  )
}
```

> **关于 SSR/ISR 混合**：付费章节虽走运行时校验，但页面文件本身仍可被 ISR 缓存——Next.js 在权限校验阶段读取 cookie 后会自动转为 dynamic，这是 RSC 的正确用法。如需强制 dynamic 可加 `export const dynamic = 'force-dynamic'`。

### 6.5 支付模块（Payjs）

```typescript
// src/lib/payment.ts
import crypto from 'crypto'

interface PayjsConfig {
  mchid: string
  key: string
}

const config: PayjsConfig = {
  mchid: process.env.PAYJS_MCHID!,
  key: process.env.PAYJS_KEY!,
}

interface CreatePaymentParams {
  total_fee: number
  out_trade_no: string
  body: string
  notify_url: string
  type?: 'wechat' | 'alipay'
}

export function createPayjsUrl(params: CreatePaymentParams): string {
  const data: Record<string, string> = {
    mchid: config.mchid,
    total_fee: String(params.total_fee),
    out_trade_no: params.out_trade_no,
    body: params.body,
    notify_url: params.notify_url,
    type: params.type || 'wechat',
  }

  const sign = signParams(data)
  data.sign = sign

  const query = new URLSearchParams(data).toString()
  return `https://payjs.cn/api/cashier?${query}`
}

export function verifyNotify(params: Record<string, string>): boolean {
  const sign = params.sign
  delete params.sign
  const expectedSign = signParams(params)
  return sign === expectedSign
}

function signParams(params: Record<string, string>): string {
  const sorted = Object.keys(params)
    .filter(k => params[k] !== '')
    .sort()
    .map(k => `${k}=${params[k]}`)
    .join('&')
  return crypto.createHash('md5')
    .update(sorted + `&key=${config.key}`)
    .digest('hex')
    .toUpperCase()
}
```

```typescript
// src/app/api/payment/create/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { createPayjsUrl } from '@/lib/payment'

export async function POST(request: NextRequest) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json()
  const { type, bookId, chapterId, amount, paymentMethod } = body

  // 余额购买：使用原子函数在单个事务中完成扣款 + 创建订单
  if (paymentMethod === 'balance') {
    const { data, error } = await supabase.rpc('purchase_with_balance', {
      p_user_id: user.id,
      p_purchase_type: type,
      p_book_id: bookId || null,
      p_chapter_id: chapterId || null,
      p_amount: amount,
    })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    if (!data?.success) {
      return NextResponse.json({ error: '余额不足' }, { status: 400 })
    }

    return NextResponse.json({ success: true })
  }

  // 外部支付（微信/支付宝）
  const outTradeNo = `ORD_${Date.now()}_${user.id.slice(0, 8)}`

  // 检查是否有重复的 pending 订单，避免堆积
  // 注意：PostgREST 中 NULL 比较必须用 .is()，不能用 .eq()
  let existingQuery = supabase
    .from('purchases')
    .select('payment_no')
    .eq('user_id', user.id)
    .eq('purchase_type', type)
    .eq('status', 'pending')

  existingQuery = chapterId
    ? existingQuery.eq('chapter_id', chapterId)
    : existingQuery.is('chapter_id', null)
  existingQuery = bookId
    ? existingQuery.eq('book_id', bookId)
    : existingQuery.is('book_id', null)

  const { data: existing } = await existingQuery.limit(1)

  let finalTradeNo = outTradeNo
  if (existing && existing.length > 0 && existing[0].payment_no) {
    // 复用已有的 pending 订单
    finalTradeNo = existing[0].payment_no
  } else {
    const { error } = await supabase.from('purchases').insert({
      user_id: user.id,
      purchase_type: type,
      book_id: bookId || null,
      chapter_id: chapterId || null,
      amount,
      payment_no: finalTradeNo,
      payment_method: paymentMethod || 'wechat',
      status: 'pending',
    })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }
  }

  const payUrl = createPayjsUrl({
    total_fee: Math.round(amount * 100),
    out_trade_no: finalTradeNo,
    body: type === 'chapter' ? '章节购买' : type === 'book' ? '书籍购买' : type === 'vip' ? 'VIP订阅' : '余额充值',
    notify_url: `${process.env.NEXT_PUBLIC_SITE_URL}/api/payment/notify`,
  })

  return NextResponse.json({ payUrl, outTradeNo: finalTradeNo })
}
```

```typescript
// src/app/api/payment/notify/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase/admin'
import { verifyNotify } from '@/lib/payment'

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const params: Record<string, string> = {}
  formData.forEach((value, key) => {
    params[key] = value.toString()
  })

  if (!verifyNotify(params)) {
    return new NextResponse('sign error', { status: 400 })
  }

  if (params.return_code !== '1') {
    return new NextResponse('success')
  }

  const outTradeNo = params.out_trade_no

  // 幂等性：使用 CAS 模式，只有 status='pending' 的记录才会被更新
  // 即使并发 webhook 重试，PostgreSQL 的行锁保证只有一个能成功
  const { data: purchase, error: selectError } = await supabaseAdmin
    .from('purchases')
    .select('*')
    .eq('payment_no', outTradeNo)
    .eq('status', 'pending')
    .single()

  // 已处理过（completed/failed）或不存在，直接返回成功（幂等）
  if (!purchase) {
    return new NextResponse('success')
  }

  const paidAmount = parseInt(params.total_fee) / 100

  // 根据购买类型执行不同逻辑
  if (purchase.purchase_type === 'recharge') {
    // 充值：增加余额 + 记录充值流水
    await supabaseAdmin.rpc('add_balance', {
      p_user_id: purchase.user_id,
      p_amount: paidAmount,
    })

    await supabaseAdmin
      .from('recharges')
      .insert({
        user_id: purchase.user_id,
        amount: paidAmount,
        payment_no: outTradeNo,
        payment_method: purchase.payment_method,
        status: 'completed',
        completed_at: new Date().toISOString(),
      })
  } else if (purchase.purchase_type === 'vip') {
    // VIP：写入订阅记录 + 同步 user_profiles
    // 套餐通过 amount 或额外的 metadata 列识别（生产环境建议给 purchases 加 plan 字段）
    const plan: 'monthly' | 'yearly' | 'lifetime' =
      paidAmount >= 999 ? 'lifetime' : paidAmount >= 168 ? 'yearly' : 'monthly'

    const now = new Date()
    const expires =
      plan === 'lifetime'
        ? new Date('2099-12-31')
        : new Date(now.getTime() + (plan === 'yearly' ? 365 : 30) * 86400_000)

    await supabaseAdmin.from('vip_subscriptions').insert({
      user_id: purchase.user_id,
      plan,
      amount: paidAmount,
      starts_at: now.toISOString(),
      expires_at: expires.toISOString(),
      payment_no: outTradeNo,
      status: 'active',
    })

    // 只更新 vip_expires_at，不修改 role 字段
    // VIP 状态由 vip_subscriptions 表推导，role 专用于后台权限（user / editor / admin）
    await supabaseAdmin
      .from('user_profiles')
      .update({ vip_expires_at: expires.toISOString() })
      .eq('id', purchase.user_id)
  }
  // book / chapter 直接外部支付：purchases 表本身就是访问凭证，无需额外动作
  // 余额购买已在 create 时扣除并写入 completed，不会进入此回调

  // 标记订单完成
  const { error: updateError } = await supabaseAdmin
    .from('purchases')
    .update({
      status: 'completed',
      completed_at: new Date().toISOString(),
    })
    .eq('id', purchase.id)
    .eq('status', 'pending')  // 二次确认，防止并发

  if (updateError) {
    console.error('Failed to complete purchase:', updateError)
  }

  return new NextResponse('success')
}
```

### 6.6 ISR 按需刷新

```typescript
// src/app/api/revalidate/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { revalidatePath } from 'next/cache'

export async function POST(request: NextRequest) {
  const body = await request.json()
  const { secret, path } = body

  if (secret !== process.env.REVALIDATION_SECRET) {
    return NextResponse.json({ error: 'Invalid secret' }, { status: 401 })
  }

  if (path) {
    revalidatePath(path)
    return NextResponse.json({ revalidated: true, path })
  }

  return NextResponse.json({ revalidated: false }, { status: 400 })
}
```

AI 上传内容后，只需调用一次 revalidate API 即可刷新对应页面，无需全站重建。

### 6.7 搜索模块（Meilisearch）

```typescript
// src/lib/meilisearch.ts
import { MeiliSearch } from 'meilisearch'

export const meili = new MeiliSearch({
  host: process.env.NEXT_PUBLIC_MEILISEARCH_HOST!,
  apiKey: process.env.MEILISEARCH_SEARCH_KEY!,
})

export const meiliAdmin = new MeiliSearch({
  host: process.env.NEXT_PUBLIC_MEILISEARCH_HOST!,
  apiKey: process.env.MEILISEARCH_ADMIN_KEY!,
})
```

```typescript
// src/app/search/page.tsx
import { meili } from '@/lib/meilisearch'

interface Props {
  searchParams: Promise<{ q?: string }>
}

export default async function SearchPage({ searchParams }: Props) {
  const { q } = await searchParams
  let results: Array<Record<string, unknown>> = []

  if (q) {
    const searchResults = await meili.index('books').search(q, {
      limit: 20,
    })
    results = searchResults.hits
  }

  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">搜索</h1>
      <form action="/search" method="get" className="mb-8">
        <input
          type="text"
          name="q"
          defaultValue={q}
          placeholder="搜索书籍..."
          className="w-full max-w-md px-4 py-2 border rounded-lg"
        />
      </form>
      {results.length > 0 && (
        <div className="space-y-4">
          {results.map((hit) => (
            <div key={hit.id as string} className="p-4 border rounded-lg">
              <h2 className="text-lg font-semibold">{hit.title as string}</h2>
              <p className="text-gray-600">{hit.description as string}</p>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}
```

---

## 七、AI 自动化工作流

### 7.1 同步脚本（仅元数据，不传内容）

```typescript
// scripts/sync-to-supabase.ts
import * as fs from 'fs'
import * as path from 'path'
import matter from 'gray-matter'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!,
  { auth: { persistSession: false } }
)

const CONTENT_DIR = path.join(process.cwd(), 'content')

async function syncBook(bookSlug: string) {
  const metaPath = path.join(CONTENT_DIR, bookSlug, 'meta.json')
  const meta = JSON.parse(fs.readFileSync(metaPath, 'utf-8'))

  const { data: book, error: bookError } = await supabase
    .from('books')
    .upsert({
      slug: bookSlug,
      title: meta.title,
      author_name: meta.author_name,
      description: meta.description,
      cover_url: meta.cover_url,
      status: meta.status,
      is_paid: meta.is_paid,
      price: meta.price,
      chapter_price: meta.chapter_price,
      is_published: true,
    }, { onConflict: 'slug' })
    .select()
    .single()

  if (bookError) throw bookError

  const chaptersDir = path.join(CONTENT_DIR, bookSlug, 'chapters')
  if (!fs.existsSync(chaptersDir)) return

  const files = fs.readdirSync(chaptersDir).filter(f => f.endsWith('.md')).sort()

  for (const file of files) {
    const raw = fs.readFileSync(path.join(chaptersDir, file), 'utf-8')
    const { data: frontmatter } = matter(raw)
    const localFilePath = `${bookSlug}/chapters/${file}`

    await supabase.from('chapters').upsert({
      book_id: book.id,
      slug: frontmatter.slug,
      title: frontmatter.title,
      local_file_path: localFilePath,
      word_count: raw.length,
      chapter_order: frontmatter.order,
      is_published: frontmatter.is_published ?? true,
      is_vip: frontmatter.is_vip ?? false,
      is_ai_generated: !!frontmatter.ai_model,
      ai_model: frontmatter.ai_model || null,
    }, { onConflict: 'book_id,slug' })
  }

  console.log(`Synced: ${meta.title} (${files.length} chapters)`)
}

async function syncAll() {
  const dirs = fs.readdirSync(CONTENT_DIR).filter(d =>
    fs.existsSync(path.join(CONTENT_DIR, d, 'meta.json'))
  )
  for (const slug of dirs) {
    await syncBook(slug)
  }
}

const args = process.argv.slice(2)
if (args[0] === 'book') {
  syncBook(args[1])
} else {
  syncAll()
}
```

### 7.2 GitHub Actions 工作流

```yaml
# .github/workflows/ai-generate-and-sync.yml
name: AI Generate and Sync

on:
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:
    inputs:
      book_slug:
        description: 'Book Slug'
        required: true
        type: string
      start_chapter:
        description: 'Start Chapter'
        required: true
        type: number
      end_chapter:
        description: 'End Chapter'
        required: true
        type: number

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm install

      - name: Generate chapters
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          npx ts-node scripts/ai-generate.ts generate \
            ${{ inputs.book_slug || 'default-book' }} \
            "默认书名" \
            ${{ inputs.start_chapter || 1 }} \
            ${{ inputs.end_chapter || 10 }}

      - name: Sync metadata to Supabase
        env:
          NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          npx ts-node scripts/sync-to-supabase.ts book \
            ${{ inputs.book_slug || 'default-book' }}

      - name: Sync to Meilisearch
        env:
          MEILISEARCH_HOST: ${{ secrets.MEILISEARCH_HOST }}
          MEILISEARCH_ADMIN_KEY: ${{ secrets.MEILISEARCH_ADMIN_KEY }}
        run: |
          npx ts-node scripts/sync-to-meilisearch.ts

      - name: Trigger ISR revalidation
        env:
          REVALIDATION_SECRET: ${{ secrets.REVALIDATION_SECRET }}
          SITE_URL: ${{ secrets.SITE_URL }}
        run: |
          curl -X POST "${SITE_URL}/api/revalidate" \
            -H "Content-Type: application/json" \
            -d "{\"secret\":\"${REVALIDATION_SECRET}\",\"path\":\"/books/${{ inputs.book_slug || 'default-book' }}\"}"

      - name: Commit and push
        run: |
          git config --local user.email "github-actions@github.com"
          git config --local user.name "GitHub Actions"
          git add content/
          git diff --staged --quiet || git commit -m "AI generated chapters"
          git push
```

---

## 八、部署方案

### 8.1 Vercel 部署

```bash
# 安装 Vercel CLI
npm i -g vercel

# 部署
vercel

# 或连接 GitHub 仓库，自动部署
```

### 8.2 环境变量清单

| 变量名 | 说明 | 位置 |
|--------|------|------|
| NEXT_PUBLIC_SUPABASE_URL | Supabase 项目地址 | 前端 + 服务端 |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | Supabase 匿名密钥 | 前端 + 服务端 |
| SUPABASE_SERVICE_ROLE_KEY | Supabase 服务密钥 | 服务端 |
| PAYJS_MCHID | Payjs 商户号 | 服务端 |
| PAYJS_KEY | Payjs 密钥 | 服务端 |
| NEXT_PUBLIC_MEILISEARCH_HOST | Meilisearch 地址 | 前端 + 服务端 |
| MEILISEARCH_SEARCH_KEY | Meilisearch 搜索密钥 | 前端 |
| MEILISEARCH_ADMIN_KEY | Meilisearch 管理密钥 | 服务端 |
| OPENAI_API_KEY | OpenAI API 密钥 | AI 脚本 |
| REVALIDATION_SECRET | ISR 刷新密钥 | 服务端 |
| NEXT_PUBLIC_SITE_URL | 站点地址 | 前端 + 服务端 |

---

## 九、成本估算

### 9.1 月度成本（初期）

| 服务 | 免费额度 | 超出费用 | 初期预估 |
|------|----------|----------|----------|
| Supabase | 500MB DB, 1GB Storage, 50K 月活 | $25/月 | **$0** |
| Vercel | 100GB 带宽, Serverless 函数 | $20/月 | **$0** |
| Meilisearch Cloud | 10K 文档免费 | $30/月 | **$0** |
| Payjs | 费率 0.6%-1% | - | 按交易量 |
| 域名 | .xyz ~$5/年 | - | **~$0.5/月** |
| **总计** | | | **$0-1/月** |

### 9.2 扩展阶段成本（月活 > 10 万）

| 服务 | 方案 | 月费 |
|------|------|------|
| Supabase Pro | 8GB DB, 100GB Storage | $25 |
| Vercel Pro | 更多带宽和函数 | $20 |
| Meilisearch | 按需 | $30 |
| **总计** | | **$75/月** |

---

## 十、开发路线图

### Phase 1：基础框架（1-2 周）

- [ ] 创建 Next.js 项目，配置 Tailwind + shadcn/ui
- [ ] 创建 Supabase 项目，配置数据库和 RLS
- [ ] 实现本地 Markdown 内容读取
- [ ] 实现首页和书籍列表页（SSG）
- [ ] 实现书籍详情页（ISR）
- [ ] 实现章节阅读页（SSR/ISR 混合）

### Phase 2：用户系统（1-2 周）

- [ ] Supabase Auth + 中间件集成
- [ ] 用户注册/登录页面
- [ ] 用户个人中心
- [ ] 阅读进度同步
- [ ] 书架功能

### Phase 3：AI 自动化（1 周）

- [ ] AI 生成脚本开发
- [ ] 同步元数据到 Supabase 脚本
- [ ] GitHub Actions 定时任务
- [ ] ISR 按需刷新

### Phase 4：付费系统（2-3 周）

- [ ] Payjs 账户配置
- [ ] 充值功能
- [ ] 章节/书籍购买
- [ ] VIP 订阅
- [ ] 付费墙组件

### Phase 5：搜索与互动（1-2 周）

- [ ] Meilisearch 集成
- [ ] 搜索页面
- [ ] 评论系统
- [ ] 点赞功能

### Phase 6：管理后台（1-2 周）

- [ ] 管理后台布局（CSR）
- [ ] 书籍管理
- [ ] 章节管理
- [ ] 用户管理
- [ ] 订单管理

---

## 十一、与 Astro 方案对比总结

| 维度 | Astro + Supabase（改进后） | Next.js + Supabase |
|------|---------------------------|-------------------|
| 付费内容保护 | ⚠️ hybrid 模式可解决，但需额外配置 | ✅ RSC 天然支持 |
| 构建效率 | ⚠️ hybrid 模式下部分页面需运行时 | ✅ ISR 按需刷新，无需全站重建 |
| 开发体验 | ⚠️ 岛屿架构增加心智负担 | ✅ RSC + Client Components 统一模型 |
| 管理后台 | ❌ 需独立项目或大量岛屿 | ✅ 同一项目内 Client Components |
| 支付集成 | ⚠️ 需 Edge Functions | ✅ Route Handlers 原生支持 |
| 中间件 | ⚠️ Astro 中间件功能有限 | ✅ Next.js 中间件功能完善 |
| 学习曲线 | ✅ 更低 | ⚠️ 中等 |
| 社区生态 | ⚠️ 较小 | ✅ 庞大 |
| 适合场景 | 纯内容展示站 | 内容 + 动态交互 + 付费 |

**结论**：对于需要付费系统、用户交互、管理后台的小说网站，Next.js App Router 是更合适的选择。Astro 更适合纯内容展示、无需复杂动态交互的场景。

---

## 十二、安全与运维清单

### 12.1 必须做的事

- [ ] **付费内容只在 Server Components 中读取**：永远不要把章节正文 props 进 Client Component，否则会出现在 RSC payload 中
- [ ] **所有写操作走服务端 Route Handler**：`balances` / `purchases` / `vip_subscriptions` 表对客户端只开 SELECT；写操作必须使用 `supabaseAdmin`（service role）
- [ ] **支付 Webhook 验签 + 幂等**：`verifyNotify` 必查；`UPDATE ... WHERE status='pending'` 提供幂等保证
- [ ] **支付 Webhook IP 白名单**（可选）：在 middleware 里限制 `/api/payment/notify` 仅接受 Payjs IP
- [ ] **ISR 刷新密钥强随机**：`REVALIDATION_SECRET` ≥ 32 字节随机串，不要硬编码
- [ ] **service role key 永不出现在 NEXT_PUBLIC_ 变量中**
- [ ] **每个 SECURITY DEFINER 函数显式 SET search_path**：防止 search_path 注入

### 12.2 已知限制

| 限制 | 影响 | 缓解 |
|------|------|------|
| Vercel 单函数 10 秒超时（Hobby） | 长事务、批量同步会被截断 | 同步脚本在 GitHub Actions 跑，不放 Vercel |
| Supabase 免费层 500MB | 上百本书评论 + 进度可能超限 | 早做 archive 策略；reading_progress 设 TTL |
| Meilisearch 免费层 10K 文档 | 章节级索引很快超 | 只索引 books（书级），不索引 chapters |
| Vercel ISR 缓存按 region | 多地区可能短暂不一致 | 关键写后调 revalidatePath |
| Edge Middleware 不能用 Node API | 无法在 middleware 里 import gray-matter 等 | 内容读取放 Server Component / Route Handler |

### 12.3 监控建议

- Supabase Logs：关注 `purchases` 表的 RLS 拒绝次数
- Vercel Analytics：关注 `/books/[slug]/[chapter]` 的 P95 响应时间（付费章节走 dynamic）
- 自建：定期对账 `purchases.status='completed'` 与 Payjs 后台流水

---

> 文档版本：1.2
>
> 创建日期：2026-04-28
>
> 最后更新：2026-04-28（superpowers 二次审查：补全 RLS、修复 BookDetailPage/ChapterPage Bug、修正支付 NULL 查询、补充 VIP 订阅生效逻辑、SECURITY DEFINER 加 search_path、补充安全运维清单）
