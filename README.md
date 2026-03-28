# A股董秘说 (GitHub Actions 纯静态版)

这是一个利用 **GitHub Actions** 定时爬虫 + **GitHub Pages** 静态托管实现的完全零成本、免运维的 A股董秘说实时追踪方案。

## 架构说明
- **数据爬取**：`scrape.py` 脚本负责从深交所互动易和上交所e互动获取最新问答。
- **自动更新**：通过 `.github/workflows/scrape.yml`，每15分钟触发一次爬虫脚本，抓取新数据并自动 `git commit`。
- **静态前端**：`index.html` 和 `stock.html` 完全使用纯前沿技术 (Fetch, LocalStorage, CSS variables) 读取 JSON，并无需任何后端服务器即可完成热点排行、按关键词过滤、全文搜索。

## 文件结构
- `.github/workflows/scrape.yml`：GitHub Actions 配置文件。
- `scrape.py`：单文件独立爬虫。
- `data/all_qa.json`：全量问答数据（历史数据已导入）。
- `data/hot.json`, `data/stats.json`：热度排行与统计缓存。
- `index.html`, `stock.html`：网站前端。

## 如何部署
1. 在 GitHub 创建一个新的 public 仓库（例如 `dongmishuo`）。
2. 将此文件夹内容完整 push 到该仓库：
   ```bash
   git remote add origin https://github.com/你的用户名/dongmishuo.git
   git branch -M main
   git push -u origin main
   ```
3. 前往 GitHub 仓库的 **Settings -> Pages**：
   - Source 选择 `Deploy from a branch`
   - Branch 选择 `main` 和 `/(root)`
   - 点击 Save
4. 前往 GitHub 仓库的 **Settings -> Actions -> General**：
   - 找到 `Workflow permissions`
   - 勾选 `Read and write permissions` 并保存（重要！这是让爬虫能自动提交更新的前提）。

部署完成后，即可通过 `https://你的用户名.github.io/dongmishuo` 随时随地访问，且数据会自动每15分钟更新！
