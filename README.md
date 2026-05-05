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
