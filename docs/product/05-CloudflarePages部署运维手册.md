# Cloudflare Pages 部署与运维手册（场景 A · Zola 站点）

> 文档类型：部署与运维操作手册（本目录唯一部署权威文档）
>
> 适用范围：`mixtxt-zola/`（Zola 0.23.3 + Pagefind 1.5.2 + Cloudflare Pages）
>
> 关联文档：[04-Zola方案详细设计.md](./04-Zola方案详细设计.md) §2.11（基础配置）、[03-轻量静态站架构设计.md](./03-轻量静态站架构设计.md)（共享模型）
>
> 文档目标：把「连 Git → 配构建 → 自定义域名 → 排障」一次讲清楚，避免部署出错。本文所有结论均来自真实排障复盘（见 §4.5 与 §6）。

---

## 0. 三条铁律（先读）

1. **本地构建必须通过，再连 Cloudflare。** Cloudflare 的构建环境和你本地完全一致（同版本 Zola、同 Node），本地跑不通的，线上 100% 跑不通。先 `./scripts/build.sh` 绿了再说。
2. **自定义域名不能只配 DNS。** 必须在 Cloudflare Pages 项目里「挂号」（`Settings → Custom domains` 添加），否则只有裸 CNAME 会得到 **HTTP 522**，永远打不开（§4 详述根因）。
3. **构建失败 = 旧版继续在线。** Pages 是一次构建产物整体替换；构建中断时上一次成功产物仍在线，不会「部署一半」。所以大胆修、大胆推。

---

## 1. 仓库结构与前提

```text
mixtxt/                         ← Git 仓库根（连 Cloudflare 时用整个仓库）
├── mixtxt-zola/                ← Zola 项目（Cloudflare 的 Root directory 指向这里）
│   ├── config.toml             ← Zola 配置（base_url、search 等）
│   ├── content/                ← 书 _index.md / 章节 .md（真理源）
│   ├── templates/              ← base / home / books / book / chapter / page / search ...
│   ├── sass/                   ← main.scss
│   ├── static/                 ← _headers（缓存+CSP）、favicon、covers
│   ├── scripts/                ← validate_content.py / generate_chapters.py / build.sh
│   └── public/                 ← 构建产物（被 .gitignore 忽略，不入库）
└── docs/
```

**工具链（本地复现用）：**
- Zola `0.23.3`（与线上 `ZOLA_VERSION` 必须一致，见 §3.4）
- Node / npx（Pagefind 走 `npx`，CF 构建环境自带 Node）
- Python 3（`validate_content.py` 用）

---

## 2. 本地构建验证（部署前必做）

### 2.1 完整命令

```bash
cd mixtxt-zola
./scripts/build.sh                      # validate → zola check → zola build → pagefind
# 预览：
zola serve                             # 生产视图（不含草稿）
zola serve --drafts                    # 含草稿预览（看草稿必须显式 --drafts）
```

`build.sh` 是**唯一构建入口**，内部顺序固定：

1. `python3 scripts/validate_content.py` —— 校验每本书版权/weight/封面，失败即中断（内容门禁）。
2. `zola check --skip-external-links` —— 查**内部**死链（不发 HTTP，构建环境稳定）。
3. `zola build "$@"` —— 透传参数（如 `--base-url "$CF_PAGES_URL"`）。
4. `npx -y pagefind@1.5.2 --site public` —— 生成搜索索引（中文需 `pagefind_extended`，`npx` 自动启用）。

任一环节失败 → 构建中断 → 旧版保持在线。**不要**在 Cloudflare 把构建命令写成裸 `zola build`（那样会跳过校验门禁）。

### 2.2 部署前必须修复的坑（来自真实排障）

| # | 坑 | 现象 | 修复 |
|---|----|------|------|
| 1 | **Tera 不支持 `{% macro %}` / `{% import %}`** | `zola build` 直接报 `Unknown tag`，构建必崩 | 删掉 `templates/macros.html`，把书卡循环**内联**进 `home.html` / `books.html`。本版本 Tera 连 `import` 标签本身都不认，只能去宏。 |
| 2 | **CSP 缺 `wasm-unsafe-eval`** | 构建正常，但**线上搜索框失效**（Pagefind 用 WebAssembly，Chrome 在受限 CSP 下拒绝编译 WASM） | `static/_headers` 的 `script-src` 补 `'wasm-unsafe-eval'`：`script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval';` |
| 3 | **`npx pagefind` 缺 `-y`** | CI 非交互环境偶发卡住或提示确认 | 改成 `npx -y pagefind@1.5.2 --site public` |
| 4 | **书 frontmatter 含 Zola section 不支持的顶层字段** | `zola build` 报 `unknown field date` / `unknown field taxonomies` | section（`_index.md`）顶层只允许 `title/description/sort_by/weight/draft/template/extra` 等；`date` 与 `taxonomies` 必须放进 `[extra]` 或用 `extra` 里的 `startedAt/updatedAt`（见 §6） |

> 上面各项在仓库当前版本**均已修复**。新克隆仓库后，先跑 §2.1 确认全绿，再走 §3。

---

## 3. Cloudflare Pages 控制台配置

### 3.1 连接 Git

`Workers & Pages → Create → Pages → Connect to Git`，授权并选中 `mixtxt` 仓库。

### 3.2 关键字段（务必逐项核对）

```text
项目名:          mixtxt                （或任意，记住它决定 *.pages.dev 子域）
生产分支:        main
Root directory:  mixtxt-zola          ★ 关键：站点在子目录，必须指向它
Framework preset: 无（或 Zola）
Build command:   if [ "$CF_PAGES_BRANCH" = "main" ]; then ./scripts/build.sh; else ./scripts/build.sh --base-url "$CF_PAGES_URL"; fi
Build output:    public
```

**`Root directory` 必须设为 `mixtxt-zola`**（不是 `/`）。理由：

- `mixtxt/` 是仓库根，`mixtxt-zola/` 才是 Zola 项目（含 `config.toml`/`content/`/`scripts/`）。
- 设为 `/` 时，构建命令 `./scripts/build.sh` 在仓库根找不到 `scripts/`（实际在 `mixtxt-zola/scripts/`），且 `zola build` 输出 `public/` 落错目录，与 Build output 错配 → 构建失败。
- 设为 `mixtxt-zola` 后，CF 以它为工作目录，`build.sh` 内 `cd "$(dirname "$0")/.."` 也自定位到该目录，二者一致。

### 3.3 构建命令的分支判断

```bash
if [ "$CF_PAGES_BRANCH" = "main" ]; then
  ./scripts/build.sh
else
  ./scripts/build.sh --base-url "$CF_PAGES_URL"
fi
```

- 生产分支（main）用 `config.toml` 的正式 `base_url`。
- 预览分支（PR 预览）用 `$CF_PAGES_URL` 动态覆盖，避免预览页 CSS/JS/搜索资源 404。

### 3.4 环境变量（固定 Zola 版本）

```text
ZOLA_VERSION = 0.23.3
```

CF 默认内置 Zola 较旧（如 0.22.1），必须用 `ZOLA_VERSION` 覆盖为与本地一致的 `0.23.3`，避免引擎版本漂移导致模板行为不一致。

---

## 4. 自定义域名（最易踩坑环节）

### 4.1 核心原理：为什么只配 DNS 不行（522 根因）

Cloudflare Pages **只服务它明确登记过的主机名**。两条铁律：

1. **路由层面**：你手动加的 CNAME 只把流量导到 Cloudflare 边缘，**Pages 后端不认识 `www.example.com` 这个主机** → 连不上源站 → **HTTP 522**。
2. **证书层面**：`*.pages.dev` 的 TLS 证书**不含**你的自定义域名。Pages 必须为您的主机名**单独签发证书**。没登记就没有证书，TLS 层也会失败。

> 一句话：CNAME 是「路牌」，Pages 还需要你在它那里「**挂号 + 办通行证（证书）**」，缺一不可。裸 CNAME 永远打不开。

### 4.2 正确步骤

1. Cloudflare 控制台 → `Workers & Pages` → 你的项目 → **Settings → Custom domains**。
2. 点 **Add a domain / Set up a custom domain**，输入完整主机名（如 `www.mixtxt.com`）。
3. 按页面提示完成验证：
   - **域名 DNS 托管在 Cloudflare**（用 CF 的 NS）：自动建好 CNAME（橙云代理），无需手动加。
   - **域名不在 Cloudflare**：页面会给出它需要的具体 DNS 记录，**照它给的填**（目标通常仍是 `项目名.pages.dev`）。把你原来手填的那条删掉或改成指定的。
4. 等状态从 `Pending` → **Active**（证书签发，一般几分钟，首次偶尔半小时到几小时）。
5. 生效后用**无痕窗口**访问 `https://www.example.com` 验证（避开本地 DNS/浏览器缓存）。

### 4.3 两种 DNS 场景对照

| 场景 | 是否在 Cloudflare 托管 DNS | 操作 | 代理状态 |
|------|---------------------------|------|----------|
| A | 是（CF NS） | 在 Custom domains 添加后自动建 CNAME | 自动橙云（Proxied） |
| B | 否（外部注册商 DNS） | 先在 Pages 添加域名 → 按提示在外部 DNS 加 CNAME | 由外部 DNS 决定，CF 自动签发证书 |

> 场景 B 的关键：**先去 Pages 添加域名，再按它给的记录配 DNS**，顺序不能反。

### 4.4 验证是否生效

```bash
# 1) 默认 *.pages.dev 必须能打开（证明站点本身部署成功）
curl -I https://项目名.pages.dev
# 期望：HTTP/2 200

# 2) 自定义域名
curl -I https://www.example.com
# 期望：HTTP/2 200
# 若返回 522 → 没在 Pages 登记（§4.1）；若返回 526 → 证书未就绪，等 Active
```

### 4.5 真实案例复盘：`www.mixtxt.com` 报 522

**现象**（实测）：

```text
https://mixtxt.pages.dev   → HTTP/2 200   ✅ 站点本身正常
https://www.mixtxt.com          → HTTP/2 522   ❌ 自定义域名打不开
```

**根因**：站点部署成功（`*.pages.dev` 能 200），但 `www.mixtxt.com` 只加了裸 CNAME（`www → mixtxt.pages.dev`），**未在 Pages 项目 `mixtxt` 的 Custom domains 里登记**。Pages 后端不认识该主机 → 522。

**修复**：进入 `mixtxt` 项目 → Settings → Custom domains → 添加 `www.mixtxt.com` → 等证书 Active → 无痕窗口验证。

**附带检查项**：
- 若域名在 Cloudflare，确认 CNAME 是橙云（Proxied），不是灰云（DNS only）。
- 想让裸域名 `mixtxt.com`（不带 www）也能访问，同样在 Custom domains 里把 `mixtxt.com` 也加上（CF 自动做 CNAME 扁平化，不受 apex 限制）。
- 域名拼写：`mixtxt`（项目名）vs `mixtxt.com`（域名）不同，确认非笔误。

---

## 5. 故障排查表

| 症状 | 可能原因 | 排查 / 修复 |
|------|----------|-------------|
| `zola build` 报 `Unknown tag` | 模板用了 `{% macro %}`/`{% import %}`（Tera 不支持） | 删 `macros.html`，内联循环（§2.2 坑1） |
| `zola build` 报 `unknown field date/taxonomies` | section 顶层写了 Zola 不支持的字段 | 移入 `[extra]` 或用 `extra.startedAt/updatedAt`（§2.2 坑4 / §6） |
| 构建中断，旧版仍在 | 正常安全网（门禁生效） | 看构建日志修 `validate_content.py` 或死链，重推 |
| 构建报「封面缺失 /covers/xxx.jpg」 | frontmatter 写了 `cover` 但文件不在 | 补 `static/covers/xxx.jpg`，或删 `cover` 字段（模板有 `if` 守卫，删了不崩，仅无图） |
| 预览分支资源 404 | 预览未覆盖 `base_url` | 确认构建命令含 `$CF_PAGES_URL` 分支（§3.3） |
| 线上搜索框无结果 | CSP 缺 `wasm-unsafe-eval`，WASM 被拦 | `static/_headers` 补 `'wasm-unsafe-eval'`（§2.2 坑2） |
| 自定义域名 **522** | 没在 Pages 登记自定义域名 | Settings → Custom domains 添加（§4） |
| 自定义域名 **526** | 证书未就绪 | 等状态变 Active；确认域名已添加且 DNS 正确 |
| 自定义域名一直 Pending | DNS 记录未生效 / 填错 | 核对 CF 给的精确记录；外部 DNS 注意 TTL 与传播 |
| 页面样式错乱 | `base_url` 与访问域名不符 | 生产用正式域名；预览用 `$CF_PAGES_URL`（§3.3） |
| 构建环境 Zola 版本不对 | 未设 `ZOLA_VERSION` | 设 `ZOLA_VERSION = 0.23.3`（§3.4） |
| CI 卡在 pagefind | `npx` 缺 `-y` | 改 `npx -y pagefind@1.5.2`（§2.2 坑3） |

---

## 6. 书 frontmatter 写入规范（避坑）

Zola 的 **section（`_index.md`）** 顶层只接受固定字段白名单：`title / description / sort_by / weight / draft / template / paginate_by / paginate_reversed / paginate_path / insert_anchor_links / render / redirect_to / in_search_index / transparent / page_template / aliases / generate_feeds / hidden / extra`。

- ❌ 顶层 `date = ...` → 报 `unknown field date`。用 `extra.startedAt` / `extra.updatedAt`（本项目约定）。
- ❌ 顶层 `[taxonomies]` 表 → 报 `unknown field taxonomies`。本书目级标签本项目不使用（参考 `sanguo-scifi`）；标签按需放在**章节** frontmatter 的 `taxonomies = { tags = [...] }`。
- ✅ 所有自定义元数据放 `[extra]` 内（`original / author / adaptor / status / visibility / cover / copyrightStatus / startedAt / updatedAt`）。
- ✅ `cover` 字段一旦写，对应 `static/covers/xxx.jpg` 必须存在，否则校验中断构建。暂无封面就先不写 `cover`（模板有 `if` 守卫）。

---

## 7. 回滚与安全网

- **构建失败自动保护**：任一环节（校验/死链/构建/索引）失败 → 本次构建产物不发布 → 上一次成功产物继续在线。无需手动回滚。
- **草稿不公开**：`draft = true` 的章节 `zola build`/`serve` 默认不含（看草稿需 `zola serve --drafts`）。正式发布前改 `draft = false` 再 push。
- **版本历史**：逐字历史在 Git；给读者看的版本说明用 `content/releases/`。按 Git tag 部署历史版本（子路径 `/versions/v0.1.0/`）属第二阶段，未启用。

---

## 8. 上线检查清单（部署前逐项勾）

- [ ] 本地 `./scripts/build.sh` 全绿（validate / check / build / pagefind）
- [ ] `public/_headers` 含 `'wasm-unsafe-eval'`
- [ ] 无 `macros.html` 残留、模板无 `{% macro %}`/`{% import %}`
- [ ] 每本书 `cover` 字段要么不写、要么 `static/covers/` 下有对应文件
- [ ] 书 `_index.md` 顶层无 `date` / `taxonomies` 等非法字段（统一放 `[extra]`）
- [ ] 仓库已 push 到 GitHub（main 分支）
- [ ] Cloudflare：Root directory = `mixtxt-zola`、Build output = `public`、Build command 含分支判断
- [ ] `ZOLA_VERSION = 0.23.3` 已设
- [ ] 首次部署后 `curl -I https://项目名.pages.dev` 返回 200
- [ ] 自定义域名已在 Pages `Custom domains` 登记并 Active
- [ ] 无痕窗口验证 `https://www.example.com` 返回 200
- [ ] （可选）裸域名 `example.com` 也已登记

---

> 维护说明：本文与 [04-Zola方案详细设计.md](./04-Zola方案详细设计.md) §2.11 互补——§2.11 写基础配置字段，本文写完整流程、自定义域名 522 根因、书 frontmatter 规范与排障。若发现新坑，优先补 §2.2 / §5 / §6，并在文头标注日期。
