# GitHub 上传指南

## 文件放在哪里

| 文件 | 位置 |
| --- | --- |
| `ying-inwork-1.3.1-source.zip` 解压后的内容 | 仓库 Code 根目录 |
| `YingInWork-v1.3.1-windows-x64.zip` | Release 附件，供直接运行 |
| `runtime-windows-x64.zip` | 同一 Release 附件，供源码开发准备组件 |
| `SHA256SUMS.txt` | 同一 Release 附件，供下载校验 |

**不要仅把源码 ZIP 上传到 Code。** 请先解压，进入 `ying-inwork-1.3.1` 文件夹，将里面的 `README.md`、`product`、`tools`、`docs`、`licenses`、`.gitignore` 等内容上传到仓库根目录，GitHub 才会直接显示项目说明。

GitHub 浏览器单文件上传上限为 25 MiB，普通 Git 仓库阻止超过 100 MiB 的文件；大体积二进制文件应使用 Releases。来源：[GitHub 官方大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

## 通过 Git 上传

先在 GitHub 创建空仓库，复制你自己的仓库 HTTPS 地址。在解压后的源码根目录执行：

```powershell
git init -b main
git add .
git status
git commit -m "Initial release: Ying In Work v1.3.1"
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

请将示例地址替换为自己的仓库地址。登录使用 GitHub 的正常认证流程，不要把令牌写进 README 或远程仓库 URL。

如果已经存在 Git 仓库，应在现有仓库中加入这些文件，沿用已有分支和远程配置，而不是重复执行初始化命令。

## 发布可运行版本

1. 进入仓库的 Releases，新建 Release。
2. 标签填写 `v1.3.1`，标题填写 `萤 In Work v1.3.1`。
3. 将 `docs/RELEASE_NOTES_v1.3.1.md` 的内容粘贴为发布说明。
4. 添加上表中的 Windows 运行包、运行组件包和哈希清单。
5. 检查后发布。由于原生追踪尚未完成实机验收，建议先标记为预发布版本。

发布前由团队确认项目许可证及第三方 SDK 的分发条款；本次打包没有替团队添加 MIT、Apache 等整体许可，也没有替你创建或发布远程仓库。
