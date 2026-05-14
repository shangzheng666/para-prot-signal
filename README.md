# para.prot.signal

本地科研日报页面，用 PubMed / NCBI E-utilities 抓取弓形虫、疟原虫和 malaria parasite 相关文献。

公开分享地址：

```text
https://shangzheng666.github.io/para-prot-signal/
```

## 打开页面

直接打开：

```powershell
D:\ToxoVault\ai-feed-page\index.html
```

## 更新文献数据

默认使用 `research-config.json` 里的 `days` 和关键词。

```powershell
python .\ai-feed-page\scripts\fetch_research.py
```

临时扩大抓取范围，例如最近 30 天：

```powershell
python .\ai-feed-page\scripts\fetch_research.py --days 30
```

脚本会生成：

```text
ai-feed-page/research-data.js
```

页面读取这个文件，所以用 `file://` 打开也能工作。

## Daily Workflow

1. 运行现有数据更新脚本，生成最新 `research-data.js`。
2. 直接打开 `index.html`，或访问 GitHub Pages 公开页面。
3. 用主题 chips、搜索框和排序按钮初筛当天文献。
4. 点击星标收藏值得继续看的文献。
5. 在文献卡片下方的讨论区写下判断、疑问或后续追踪意见。
6. 可打开“只看收藏”，继续叠加主题和搜索条件核对结果。
7. 点击“导出收藏 N 篇”，下载 Obsidian 友好的 Markdown 日报。
8. 将下载的 `.md` 文件放入 Obsidian 文献或日报文件夹，继续补 `Why it matters` 和 `Notes`。

导出的 Markdown 包含 YAML front matter、数据更新时间、收藏数量，并按主题分组列出 PMID、DOI、期刊、日期、作者、链接、摘要摘录、人工笔记占位和本地讨论内容。

## Data Contract

页面保持纯静态，不需要后端、构建工具或包管理器。它只依赖：

```js
window.researchLastUpdated = "2026-05-05 11:27:20 +0800";
window.researchItems = [
  {
    id: "pubmed-42080628",
    title: "...",
    url: "https://pubmed.ncbi.nlm.nih.gov/42080628/",
    source: "PubMed",
    tag: "Toxoplasma",
    topics: ["Toxoplasma"],
    type: "PubMed",
    ageHours: 27.5,
    score: 100,
    journal: "...",
    pubDate: "2026-05-04",
    authors: ["Author A", "Author B"],
    pmid: "42080628",
    doi: "10.xxxx/xxxxx",
    why: "Abstract excerpt..."
  }
];
```

收藏状态保存在浏览器 `localStorage` 的 `parasiteSignalSaved` 中。收藏 ID 使用稳定文献标识符生成，优先级为 `PMID > DOI > URL > title + date`，不会依赖数组顺序。

文献讨论内容保存在浏览器 `localStorage` 的 `parasiteSignalDiscussions` 中。当前实现是纯静态本地讨论，不会同步到其他设备或其他用户。

## 部署地址

当前建议先用 GitHub Pages 免费地址：

```text
https://shangzheng666.github.io/para-prot-signal/
```

后续如果购买正式域名，可以再添加 `CNAME` 文件，并在 DNS 里把域名指向 GitHub Pages。

## 增加主题

编辑 `research-config.json`，追加一个主题：

```json
{
  "tag": "Vaccine",
  "query": "(Toxoplasma gondii[Title/Abstract] AND vaccine[Title/Abstract])"
}
```

常用方向可以写成：

- `ROP18`
- `GRA15`
- `SAG1`
- `bradyzoite`
- `drug resistance`
- `host immunity`
- `vaccine`
- `Plasmodium falciparum`
- `Plasmodium vivax`
