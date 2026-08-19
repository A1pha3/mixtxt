# Zola 方案详细设计 — 变更历史归档

> 本文档归档 [04-Zola方案详细设计.md](./04-Zola方案详细设计.md) 1.8 及之前的变更记录。
> 1.9 及之后的变更见主文档文头。

## 1.8（对抗性审查收尾，判断 4）

**小准确性问题 + 更强项**——① book.html 的 `{% if not page.draft %}` 加注为"双保险"（Zola 构建期已把草稿从 `section.pages` 移出，此判断通常恒真，保留防子目录漏排）；② §2.8 补"**重排 vs 改名**"：重排只改 `weight` 不改文件名/URL，改名（换 slug）会变 URL，须在 frontmatter 加 `aliases` 防死链。（搜索摘要改 DOMParser、批量发布改 weight 区间这两项已在 1.6 完成，此处不重复。）

## 1.7（对抗性审查回顾，判断 3 落地）

**实现代码移回 repo 作为单一真实源**——`validate_content.py`（§2.12）、`generate_chapters.py`（§2.18）、`build.sh`（§2.12）、`templates/search.html`（§2.9）全文迁到仓库根 [`mixtxt-zola/`](../../mixtxt-zola/) 对应路径，文档正文改为"规则清单 + 关键实现要点 + 链接引用"，瘦身约 300 行、消除"文档与脚本双写漂移"；§2.12 旧"覆盖清单"并入新增的"校验规则"清单（去重）。阶段说明：站点仓库尚未初始化，此目录先在 `docs` 仓库内承载上述脚本的单一真源，Phase 0 `zola init` 时按 §2.4 结构展开。

## 1.6（第一性对抗性审查回顾）

**收敛"单一真源"——删除文件名数字前缀**。原先 "weight==文件名数字前缀" 实为需手工同步的双副本，恰是 §2.8 重排两个 bug 的根因。现：章节文件改为**不承载章号的 `<slug>.md`**（书内唯一、仅作 URL slug），章号/排序/显示全由 `weight` 派生；validate 不再校验"文件名↔weight"，改为校验"weight 非负整数且书内唯一、slug 书内唯一"；§2.8 插章/删章/重排从"`sed -i`+`git mv`+`sort -r`"塌缩为"只改 weight 字段"，文件名/链接/URL 永不因重排改变，天然无 `git mv` 冲突与死链；harness 生成 `ch<weight>.md`（opaque slug）、起始章号改为读 frontmatter 的 weight（不再从文件名拆）；§2.13 批量发布改为按 weight 区间的 tiny python（消除 `005*.md` 误命中 4 位章号的 glob 隐患）；§2.5/§2.13 外链策略表述收敛到 §2.12 单点（防再次两处不自洽）；§2.9 结果摘要改 DOMParser 取纯文本。

## 1.5（对抗性审查第 7/8 轮）

**修复 §2.8 插章重排命令两个 bug**——`${p%%-*}` 对无 slug 文件名（`003.md`）不裁剪导致 `$((10#003.md))` 算术错误、`${p#"$w"}` 因 w 变整数错删前缀；且必须按章号**从大到小**处理（`sort -r`），否则先改名会占用后移目标名、`git mv` 冲突（正序 003→004 时 004 尚未移走）；现兼容 `003.md` 与 `003-huangjin.md`。**恢复 home.html 的 visibility 模板过滤**（经查 Zola 只保证 draft section 的子孙不处理、未保证其从父 section 的 `subsections` 移除，保留双保险防 hidden 书死链）。修正 §2.12 覆盖清单错误表述（`zola check` 只查链接、查不了 `ai.prompt` 引用与 semver，不能作为它们的兜底）。§2.17 中文搜索行补 PyPI 跑法。

## 1.4（对抗性审查第 6 轮）

**单一真源收敛——删 `extra.chapterNo` 与 `extra.book`**（与已删的 `wordCount`/`seo` 同一逻辑：章号由 `weight` 用 `"%03d"|format` 派生、书归属由目录唯一决定，存了只会造成第三份漂移源）；validate 一致性收敛为"文件名前缀==weight"两处；**build.sh 纳入 `zola check --skip-external-links`**（不发 HTTP，唯一入口补齐内部死链门禁；Actions 删独立那行）；补"连载中插章/删章/重排"指引与"批量发布受控命令"；home.html 删 visibility 模板过滤（hidden 书已由 section `draft=true` 构建期过滤，第 7/8 轮又恢复为双保险，见 1.5）；精简 Elasticlunr 重复表述（集中 §2.9）；harness 单章 LLM 失败不再拖垮整批（汇总失败清单继续其余）。

## 1.3（对抗性审查第 5 轮）

**构建入口收敛为 `scripts/build.sh`（校验+构建+索引唯一入口），修复 Cloudflare Pages 构建命令漏跑校验脚本的门禁缺口**；Actions 改调 build.sh 且 `zola check --skip-external-links`（修复与 §2.13 的自相矛盾）；删 `extra.wordCount`（Zola 原生 `page.word_count` 已按字符计，免手工维护）；og:image 对无封面书防御；CSS 加 `cachebust`；补"继续阅读"进度记忆与"本地 serve 无搜索索引"说明；validate 加 createdAt≤updatedAt。

## 1.2（对抗性审查第 4 轮）

chapter 导航加 `data-pagefind-ignore`（防搜索索引污染）；删误导性 `in_search_index`；base.html 补 canonical/OG（对齐 doc 03 §2.11 SEO 要求）；Pagefind 固定 `@1.5.2` 并补充 Python/PyPI 免 Node 跑法与"中文必须 extended 版"；validate 校验 `extra.book` 与目录一致；harness 加 API Key 缺失报错、429/5xx 重试、缺省读真实书名、desc 去 Markdown 标记；补 taxonomy 简版模板；§2.1/§2.15 过时表述修正。

## 1.1（对抗性审查第 3 轮）

中文搜索改 Pagefind（内置 Elasticlunr 对中文不可用）；`hidden` 书=书 section `draft=true`；prompts 移出 `content/`；删 `[extra.seo]` 死数据；validate 增加 文件名/weight/chapterNo 一致性、日期格式、hidden 联动门禁；harness 生成前版权 fail-fast、date 改无引号 TOML datetime；`ZOLA_VERSION` 0.23.2→0.23.3；注明 `zola check` 默认检查外部链接。