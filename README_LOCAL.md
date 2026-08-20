# Paper Monitor LOCAL V6 — ID First

Build: `LOCAL-2026.08.20-V6-ID-FIRST`

V6 把“是不是新论文”的判断从日期改成稳定 source ID：

- Elsevier: `PII`
- IEEE: `Document ID`
- Springer: Meta API identifier/DOI

## Elsevier

每本期刊只打开一个搜索页：

`https://www.sciencedirect.com/search?docId={ISSN}&sortBy=date&show=50`

搜索结果按网页顺序读取。PII 没见过就保存；连续若干个 PII 已存在就停止当前期刊。**不再打开 article page。**

日期只是显示信息：结果卡片有 `Available online` 就保留日级日期；否则保留页面显示的出版年月（例如 `January 2027`）。出版年月不会被当成 online 日期用于排序。

## IEEE

使用 `journal_list.xlsx` 中 15 个简洁 Xplore TOC/Early Access 链接，例如：

`https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=6352949&sortType=newest`

只从列表页提取 Document ID、题名、作者和文章链接。Document ID 没见过就保存。**不查日期，也不打开 article page。**

## Springer

继续使用 Springer Nature Meta API，只使用 `onlineDate`。

## 获取日期

数据库新增 `fetched_date`：论文第一次被本地程序发现并入库的日期。以后再次遇到同一个 source ID，`fetched_date` 永不改变。

网页默认排序：

1. fetched_date DESC
2. journal ASC
3. true online sort date DESC
4. source_rank ASC

因此同一天获取的论文先按期刊聚合；IEEE 没有日期时自然保持 Xplore 列表页顺序。

## 快速开始

看根目录 `START_HERE.txt` 或直接按编号运行 BAT。
