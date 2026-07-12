---
name: wechat-article-video-download
description: |
  下载微信公众号文章（mp.weixin.qq.com/s/...）里嵌入的视频。
  支持列出文章里所有视频（按文档顺序）、按序号下载某一个、或一次性下载全部。
  纯 TypeScript 实现，靠 Node.js 22+ 的原生 strip-types 直接运行；
  零依赖 —— 不需要 Playwright、yt-dlp 或任何第三方包。

  当用户给出微信文章链接（mp.weixin.qq.com）并且提到视频、下载、保存、归档，
  或者要求"第 N 个视频"/"所有视频"时，必须触发本 skill。
  触发词包括但不限于：下载视频、下载里面的视频、把视频保存下来、第 5 个视频、扒视频、
  download video、save video、extract video。

  不要在以下情况触发：用户给的是非微信链接；用户只想要文章正文/图片（那是别的 skill 的事）。
---

# 微信公众号文章视频下载器（TypeScript 版）

下载微信公众号文章里嵌入的视频。零依赖（只用 Node.js 内置模块），通过解析文章 HTML 直接拿到 `mpvideo.qpic.cn/*.mp4` 直链下载。

## 适用场景

- 用户给出 `https://mp.weixin.qq.com/s/...` 链接，并希望下载里面的视频。
- 典型表述：下载第 N 个视频 / 下载所有视频 / 把这篇里的视频扒下来 / 列出这篇里有哪些视频。

## 运行环境

需要 Node.js **22+**（依赖 `fetch`、`Readable.fromWeb`、`parseArgs`，以及原生 TS strip-types 才能直接跑 `.ts`）。已在 Node 24 上验证。

## 工作原理（给 Claude 看的速览）

微信文章通过 `<iframe class="video_iframe" data-mpvid="wxv_XXX">` 嵌入视频，但真正的 MP4 直链（`mpvideo.qpic.cn/<file_id>.fXXXXX.mp4?auth_key=...`）就在同一份 HTML 的 JS 数据块里。**带上正常浏览器 User-Agent 的 `fetch` 就足够拿到完整 HTML**，无需 headless 浏览器。

`auth_key` 是短期有效的（一般几个小时）。下载返回 403 就重新跑一次 `list` 刷一遍鉴权即可。文章 HTML 本地缓存 10 分钟，存放在 `~/.cache/wechat-article-video-download/`。

## 画质代码对照

| 代码   | 编码  | 典型分辨率 | 10 分钟视频的典型体积 |
|--------|-------|-----------|----------------------|
| f10002 | H.264 | ~960x544  | ~80 MB               |
| f10102 | HEVC  | ~960x544  | ~50 MB               |
| f10004 | H.264 | ~846x480  | ~30 MB               |
| f10104 | HEVC  | ~480x270  | ~13 MB               |

默认按 f10002 → f10102 → f10004 → f10104 的顺序选可用的最高画质。**注意命名反直觉**：数字最大的 `f10104` 是体积最小的手机版。脚本内部已经处理好优先级，不要拍脑袋。

## 命令行用法

```bash
# 列出文章里所有视频（人类可读）
node ~/.claude/skills/wechat-article-video-download/scripts/wechat_video.ts list <url>

# 列出但输出 JSON（方便程序消费）
node ~/.claude/skills/wechat-article-video-download/scripts/wechat_video.ts list <url> --json

# 下载第 5 个视频到 ./videos/
node ~/.claude/skills/wechat-article-video-download/scripts/wechat_video.ts download <url> 5

# 下载全部到自定义目录
node ~/.claude/skills/wechat-article-video-download/scripts/wechat_video.ts download <url> all --output ./my_videos

# 强制指定画质
node ~/.claude/skills/wechat-article-video-download/scripts/wechat_video.ts download <url> 5 --quality f10102
```

## 推荐执行流程（给 Claude 参考）

当用户说"下载这篇里第 5 个视频"之类的话：

1. 先跑 `list <url>`，把找到的视频总数告诉用户。
2. 如果数量和用户口头说的对不上（比如用户说"6 个"但脚本找到 7 个），明确按文档顺序的"第 N 个"是用户想要的那个，再继续。
3. 跑 `download <url> <N>` 下载用户确认的那个。
4. 报最终的文件路径和大小给用户。

## 已知限制

- **`auth_key` 会过期**：HTML 缓存 10 分钟，但 auth_key 的真实有效期由微信决定（通常几小时）。下载 403 重跑一次 `list` 就行。
- **不支持腾讯视频嵌入**：如果文章里嵌的是 `v.qq.com` 的纯 `vid` 参数，本 skill 不会识别。遇到这种情况，建议回退到 yt-dlp。
- **不下载 `<mpvoice>` 纯音频**：那不是视频，超出范围。
- **被风控时无能为力**：如果当前网络被微信风控（返回"环境异常"页），脚本会直接报错。换个网络再试。

## 文件结构

```
~/.claude/skills/wechat-article-video-download/
├── SKILL.md                       ← 本文件
└── scripts/
    └── wechat_video.ts            ← 主脚本，逐行带详细中文注释，可直接当学习材料读
```
