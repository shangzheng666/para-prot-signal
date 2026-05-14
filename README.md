# para.prot.signal

寄生虫科研文献日报，每日自动抓取 PubMed 上 *Toxoplasma*、*Plasmodium*、Malaria parasite 相关最新论文，生成可浏览、可收藏、可导出的静态页面。

**在线地址** &rarr; <https://shzzzayys.github.io/para-prot-signal/>

## 项目结构

```
para-prot-signal/
├── index.html              # 前端页面
├── app.js                  # 前端逻辑（筛选/收藏/导出）
├── styles.css              # 样式
├── research-config.json    # 抓取配置（主题、天数、每主题上限）
├── research-data.js        # 抓取输出 — 前端数据源
├── research-data.md        # 抓取输出 — Markdown 文档
└── scripts/
    └── fetch_research.py   # PubMed 抓取脚本
```

## 快速开始

### 1. 抓取文献

```powershell
# 默认抓取最近 7 天（读取 research-config.json 中的 days）
python scripts/fetch_research.py

# 指定天数
python scripts/fetch_research.py --days 3
```

脚本会同时生成两个文件：

| 文件 | 用途 |
|------|------|
| `research-data.js` | 前端页面数据源 |
| `research-data.md` | Markdown 表格，按日期分组，含 DOI 链接 |

### 2. 浏览页面

直接双击 `index.html`（`file://` 协议即可），或访问 GitHub Pages 在线地址。

## NCBI API Key

匿名模式限速 3 req/s。申请 [NCBI API Key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) 后可提升到 10 req/s（约 3 倍加速）。

```powershell
# 方式一：环境变量
$env:NCBI_API_KEY = "your_key"
python scripts/fetch_research.py

# 方式二：命令行参数
python scripts/fetch_research.py --api-key your_key
```

启动时 stderr 会打印当前模式：

```
Using NCBI API key (10 req/s limit)   # 有 key
Running anonymous, 3 req/s            # 无 key
```

## 抓取脚本特性

| 特性 | 说明 |
|------|------|
| **API Key 加速** | 有 key 时 sleep 0.11s，无 key 时 0.35s |
| **网络重试** | 最多 3 次，指数退避 2s → 4s，仅重试 5xx / 网络错误，4xx 直接抛出 |
| **MeSH 增强查询** | 每个主题 OR 上 MeSH 词，提高召回率 |
| **PMID 去重** | 同一 PMID 跨主题命中时合并 topics |
| **DOI 二次去重** | 不同 PMID 但相同 DOI 的文章（如 ahead-of-print vs 正式版）合并为一条 |

## 配置主题

编辑 `research-config.json`：

```json
{
  "days": 7,
  "retmax_per_topic": 25,
  "topics": [
    {
      "tag": "Toxoplasma",
      "query": "(Toxoplasma gondii[Title/Abstract] OR toxoplasmosis[Title/Abstract] OR \"Toxoplasma\"[MeSH] OR \"Toxoplasmosis\"[MeSH])"
    },
    {
      "tag": "Plasmodium",
      "query": "(Plasmodium[Title/Abstract] OR Plasmodium falciparum[Title/Abstract] OR Plasmodium vivax[Title/Abstract] OR \"Plasmodium\"[MeSH])"
    },
    {
      "tag": "Malaria parasite",
      "query": "(malaria parasite[Title/Abstract] OR malaria parasites[Title/Abstract] OR \"Malaria/parasitology\"[MeSH])"
    }
  ]
}
```

新增主题只需追加一个对象。常用方向示例：

- `ROP18` / `GRA15` / `SAG1` / `bradyzoite`
- `drug resistance` / `host immunity` / `vaccine`
- `Plasmodium falciparum` / `Plasmodium vivax`

查询语法参考 [PubMed 高级搜索](https://pubmed.ncbi.nlm.nih.gov/advanced/)，支持 `[Title/Abstract]`、`[MeSH]`、布尔运算符。

## 页面功能

- **主题筛选** — 顶部 chips 按主题过滤
- **搜索** — 标题 / 期刊 / 作者关键词搜索
- **排序** — 按热度 / 时间排序
- **收藏** — 星标收藏，支持"只看收藏"
- **讨论** — 每篇文献卡片下可写笔记
- **导出** — 导出收藏为 Obsidian 友好的 Markdown 文件

收藏和讨论数据保存在浏览器 `localStorage`，不依赖后端。

## Daily Workflow

1. 运行 `python scripts/fetch_research.py` 更新数据
2. 打开页面，用主题 / 搜索 / 排序初筛
3. 星标收藏值得细看的文献
4. 在卡片讨论区记录判断和疑问
5. 导出收藏 Markdown，放入 Obsidian 继续整理

## Data Contract

页面纯静态，零依赖，只读取 `research-data.js` 中的两个全局变量：

```js
window.researchLastUpdated = "2026-05-14 13:35:07 +0800";
window.researchItems = [ /* ... */ ];
```

每条文献对象包含：`id`, `title`, `url`, `source`, `tag`, `topics`, `type`, `ageHours`, `score`, `journal`, `pubDate`, `authors`, `pmid`, `doi`, `why`。

## 部署

当前使用 GitHub Pages：

```
https://shzzzayys.github.io/para-prot-signal/
```

如需自定义域名，添加 `CNAME` 文件并配置 DNS 指向 GitHub Pages 即可。
