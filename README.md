# 改革宗网书籍 → 简体 Markdown

把 [改革宗网（gaigezong.com）](https://gaigezong.com/) 上按“目录页 + 章节页”组织的书籍，一键整理为**单个简体中文 Markdown 文件**，附带可跳转目录。

提供两种用法：

- **书签工具（推荐）**：纯前端，无需安装，在书籍目录页点一下即可下载。
- **Python 脚本**：命令行批量处理。

## 书签工具

1. 打开工具页面：<https://kingxhao.github.io/gaigezong2md/>（或直接双击本地的 `index.html`）。
2. 显示浏览器书签栏（Chrome / Edge：`Ctrl+Shift+B`），把页面上的「书籍转 Markdown」按钮拖到书签栏。
   拖不动时，点「复制书签代码」，新建书签并把代码粘贴到网址栏。
3. 打开某本书的**目录页**，例如 `https://gaigezong.com/jiejing/xiduyifusuo/index.htm`，点击该书签。
4. 右上角显示进度，完成后自动下载 `.md`，并列出“标题不一致”等提示供核对。

> 该站不允许跨域访问，所以工具以书签形式在 gaigezong.com 页面内运行。书签保存的是代码本身，工具页面更新后需重新拖一次按钮。

## Python 脚本

```bash
pip install requests beautifulsoup4 opencc-python-reimplemented
python scripts/gaigezong_to_md.py <目录页URL> [-o 输出目录] [--cache 缓存目录] [--no-zhe]
```

示例：

```bash
python scripts/gaigezong_to_md.py https://gaigezong.com/jiejing/xiduyifusuo/index.htm -o out
```

网页会缓存到系统临时目录，重复运行不会重复下载。

## 转换规则

两种用法输出完全一致：

- 仅字形繁转简（OpenCC `t2s`），不替换地区用词（如「雪梨」不改为「悉尼」）。
- 「著」转「着」（藉着、因着、活着），保留读 zhù 的词（著作、著名、著墨、显著等）；可用 `--no-zhe` 或页面勾选框关闭。
- 引号「」『』、原文空格与错别字保持原样。
- 去除网页源码中的折行；粗体、表格转为 Markdown。

## 注意

- 正文识别依赖该站常见的页面版式，换新书时建议先浏览生成结果。
- 书签工具首次运行需联网，从 jsDelivr / unpkg 加载 [opencc-js](https://github.com/nk2028/opencc-js) 词库（固定版本，带完整性校验）。
- **版权**：网站上的书籍多为有版权的出版物。本工具仅供个人学习阅读，请勿公开传播转换后的全文。仓库的 `.gitignore` 已排除生成的书稿。
