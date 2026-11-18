# IG Downloader V5.2 — 新增「全部下载」模式

**新增：** 在「下载模式」选择「全部下载（扫描所有历史帖子，跳过已记录）」，程序会忽略 N，遍历所有可访问的所选类型内容。已经记录到 SQLite 历史数据库的帖子不会重下，即使媒体文件被手动删除。要下载所有普通帖子及 Reels，勾选普通照片/视频、多图帖、Reels。Stories 和 Highlights 如需包含，需单独勾选且登录会话有效。Instagram 可能限流或阻止接口，因此不保证绝对完整。

**注意：** 全部下载 ≠ 强制重新下载已记录的内容。首次升级前已经删除、没有记录的旧内容无法自动识别，可能会重新下载。请保留 `~/Downloads/IG-Downloader/_download_history/`。

---

## 旧版 V5.1 功能说明

通过 Mac 本地网页（`http://127.0.0.1:8788`）下载你有权保存的 Instagram 公开内容。Python + Flask + [Instaloader](https://instaloader.github.io/)。不支持直播，也不绕过账号权限。

## 功能

- 自选：普通单帖照片/视频、多图帖（Carousel）、Reels、Stories、Highlights；可以一次勾选多类。
- 下载模式：**只检查最新 N 帖（推荐、最快）** / 寻找 N 个未下载帖子（可能扫描历史） / 检查历史帖子。自定义 N（0=不限），**N 仅适用于普通帖子、多图帖、Reels**，不限制 Stories/Highlights 的媒体数量。
- 按账号保存在 `~/Downloads/IG-Downloader/<用户名>/`，Stories 与 Highlights 存子文件夹；支持网页预览、Finder 打开和 ZIP 打包。
- 旧版下载目录无需迁移；首次升级会导入旧版 `.downloaded_posts.json`，还会在扫描帖子时根据旧文件日期尝试识别旧帖。日期匹配只是一种推断，**可能将不完整的旧帖判为已完成**。如要补漏，需要手动处理历史记录（见下文）。

## 启动

1. 安装 Python 3.10+。
2. 双击 `启动 IG Downloader.command`；它会在项目文件夹中建立 `.venv`、安装 requirements 并运行网页。
3. 若 macOS 阻止运行，在 Finder 里右键文件并选择「打开」，只在确认源代码可信时允许。
4. 浏览器打开 <http://127.0.0.1:8788>，粘贴公开账号链接，选择下载类型、模式和 N，开始下载。
5. 使用期间保持 Terminal 运行。结束按 `Control+C`。

## Stories / Highlights 登录会话

Instaloader 官方要求访问 Stories 和 Highlights 时登录，即使目标账号公开。**不需要在网页输入密码或 cookie**。先在新的 Terminal 中运行：

```bash
cd ~/Downloads/IG-Downloader-V5.1
source .venv/bin/activate
instaloader --login 你自己的IG用户名 --no-posts --no-profile-pic 你自己的IG用户名
```

按终端提示登录后，Instaloader 会把会话保存到 Mac 用户目录。回到 V5 网页，在「已登录的 IG 用户名」填入**自己的账号用户名**（不是要下载的目标账号），再选择 Stories 或 Highlights。不要上传、分享或提交 Session、Cookies、Token、密码。

> Instagram 可能拒绝或限制自动请求；登录不会保证所有内容都能下载，Stories 只包含当前仍可访问的内容。Reels 也可能遇到与普通帖子不同的访问错误。

## 重要说明

- **不要直接覆盖已在使用的旧版程序文件夹。** 推荐以 `IG-Downloader-V5.1` 为新版目录名，并先停止旧版（端口 8788 只能由一个程序使用）。
- ZIP 打包时应等任务停止。媒体文件夹与虚拟环境不属于 GitHub 项目源代码，已在 `.gitignore` 排除。
- 一个帖子可含多个媒体文件；N 是帖子数，不是下载文件数。Stories / Highlights 不按 N 计数。
- 若指定只下载 Reels，普通帖中的某些 Reels 可能受 Instagram 分类/API 差异影响；以实际日志为准。
- 遵守版权、隐私与 Instagram 使用条款，只保存有权使用的媒体。

## 免责声明

第三方非官方项目；未获得 Instagram / Meta 认可。兼容性会随 Instagram 更新而变化。

## 快速检查最新 N 帖

选择「只检查最新 N 帖」并输入例如 `3`，程序会按发布时间检查选中的普通帖子、多图帖与 Reels 中最新 3 帖，历史数据库已记录的帖子会跳过，不再继续翻阅 1399 帖的历史。若最新 3 帖均已保存，则本次新下载 0 帖。注意：启用 Reels 需要读取 Reels 列表的首页，如 Instagram 拒绝访问该列表，可能无法准确覆盖所有 Reels；具体见日志。Stories / Highlights 不受 N 限制，若想只处理最新 3 帖，请不要勾选两项。

## V5 新增：永久下载历史（重要）

- 下载记录**独立于媒体文件**，存放在 `~/Downloads/IG-Downloader/_download_history/<IG用户名>.sqlite3`。
- 每当一个帖子成功完成下载，保存其 shortcode；以后即便你从 Finder 删除已下载的 `.jpg` / `.mp4`，历史记录仍保留，程序**不会自动重新下载该帖子**。Stories / Highlights 也记录已处理的媒体 ID（从 V5 开始有效）。
- 三种模式都会尊重历史记录：快速最新 N 帖只查看最新 N 帖；寻找 N 个未下载帖子可能扫描旧帖子；检查全部历史帖子也不会自动恢复你删掉的文件。
- **首次升级注意：** 老版本不一定保留完整历史。程序会优先导入已有 `.downloaded_posts.json`；对旧媒体则在访问对应帖子时按日期推断导入。因此，**升级前就已删除且没有留存记录的旧帖子无法自动辨认**，将来如果被扫描到仍有可能再下载。
- 旧文件中如同一帖子只有部分文件，日期推断也可能把它当作已完成，不会自动补齐。需要手动补漏时，先备份数据库，再有选择地清除对应 shortcode 的历史记录。不要直接删掉整个数据库，否则以前删除的文件可能又会被下载。
- 建议将整个 `_download_history` 文件夹单独备份。**不要把数据库、个人媒体或登录会话上传到公开 GitHub 仓库。**
- 本地 `~/Downloads/IG-Downloader/` 会同时保存媒体文件和历史数据库；只整理 `用户名/` 媒体文件夹，不要删除 `_download_history/`。

## 第一次测试建议

先保留 V4/V4.1 备份，停止旧服务器，再运行 V5。选择 `只检查最新 N 帖`、N=`3`，只勾选普通帖子、多图帖和 Reels。展开下载日志，确认有 `跳过历史已记录帖子` 和 `帖子阶段结束`。V5 已完成本地语法及数据库测试，但仍需在实际 Mac / Instagram 环境验证。

## V5.1 修复说明：Instagram API 404 / Reels

- 安装 **Instaloader 4.16 或更新的 4.x**：4.16 调整了 Instagram 公开主页信息的读取流程，以减少旧 `web_profile_info` 接口报错的影响。
- 保持原有 V5 的三种模式、下载历史 SQLite 数据库、文件存放路径不变。
- 增加更清楚的 API 失败提示，缩短连接失败时的重复尝试；当 Reels API 读取失败时明确标记本次结果可能不完整。
- **没有承诺修复 Instagram 服务器端的所有 404、429 或权限限制**；不可访问的 Reels 不能假装下载成功。
- 登录会话是可选的（普通帖子和 Reels 也可以使用），只需在网页「已登录的 IG 用户名」中填入你的 Instagram 登录用户名（不是目标账号）。不要将密码或 session 文件上传到 GitHub。

### 从 V5 升级

1. 在原 Terminal 用 Control+C 停止 V5。
2. 解压本项目到 `~/Downloads/IG-Downloader-V5.1/`。
3. 使用 `zsh './启动 IG Downloader.command'` 运行；启动脚本会自动安装新的依赖（包括 Instaloader 4.16+）。
4. 下载媒体和历史数据库仍在 `~/Downloads/IG-Downloader/`，**无需移动或清空**。
5. 先用 N=3 的快速模式测试；若仍出现接口错误，记下具体信息。

### 版本检查

```bash
cd ~/Downloads/IG-Downloader-V5.1
.venv/bin/python -m pip show instaloader
```

查看 `Version` 是否至少为 `4.16`。
