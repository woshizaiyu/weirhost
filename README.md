# Weirdhost 家宽游戏机自动续期

> `hub.weirdhost.xyz` 基于 Pterodactyl 面板的家宽小主机自动续期，基于 `oyz8/weirdhost-login` 精简重构，去 `xdotool/opencv/scrot` 重依赖，保留 UC 过盾与 API 校验核心链路。

- **多账号多服**：`WEIRDHOST_COOKIE_1..5`，每账号自动发现全部 `free/notfree` 服务器
- **Cloudflare Turnstile**：登录页 + 续期弹窗双阶段处理（`seleniumbase UC` + JS 点击兜底，无 `xdotool`）
- **健壮校验**：续期前后双重校验 `expire`，区分 `success / cooldown / skipped`
- **通知与回写**：TG Bot 通知 + 截图产物 + 可选 `REPO_TOKEN` 自动回写 `remember_web` Cookie
- **本地+CI**：支持 `python scripts/weirdhost_renew.py` 本地直跑与 GitHub Actions 定时

## 快速开始

### 1. 获取 Cookie

登录 `https://hub.weirdhost.xyz` 后 `F12 -> Application -> Cookies -> hub.weirdhost.xyz` 复制 `remember_web_59ba36addc2b2f...` 的 `名称=值`。

### 2. GitHub Secrets 配置

`Settings -> Secrets and variables -> Actions -> New repository secret`

| Secret | 示例 | 说明 |
|---|---|---|
| `WEIRDHOST_COOKIE_1` | `备注-----remember_web_59ba36addc2b2f940CCCC=xxx` | 账号1，`备注-----` 前缀可选（用于 TG 显示） |
| `WEIRDHOST_COOKIE_2..5` | 同上 | 账号2..5 |
| `TG_BOT_TOKEN` | `123456:ABC...` | 可选，TG 通知 |
| `TG_CHAT_ID` | `123456789` | 可选 |
| `REPO_TOKEN` | `ghp_xxx` | 可选，自动回写 Cookie |
| `RENEW_THRESHOLD_DAYS` | `2` | 已在 workflow 固定为 2，无需额外设置 |

> 兼容旧版：也支持 `WEIRDHOST_ACCOUNTS` / `ACCOUNTS` JSON 数组。

### 3. 运行

- 手动：`Actions -> Weirdhost 自动续期 -> Run workflow`
- 定时：每天北京时间 `00:15` 自动跑
- 本地：`pip install -r requirements.txt && python scripts/weirdhost_renew.py`（支持根目录 `.env`）

### 4. 查看结果

- Actions 日志 + `debug-screenshots` 产物
- TG 收到 `账号：xxx / 服务器：xxx / 状态：🟢 续期成功 / 剩余：X天`

## 目录结构

```
weirhost/
├── .github/workflows/renew.yml   # 定时任务
├── scripts/weirdhost_renew.py    # 主脚本（精简版，~700 行）
├── requirements.txt              # 仅 seleniumbase/aiohttp/pynacl
├── .env.example                  # 本地配置模板
└── README.md
```

## 与原版差异

| 项 | 原版 oyz8 | 本版 |
|---|---|---|
| 系统依赖 | xvfb + x11-utils + xdotool + scrot + 韩文字体 + opencv | 仅 xvfb |
| Python 依赖 | seleniumbase + aiohttp + pynacl + opencv + numpy + pillow | seleniumbase + aiohttp + pynacl |
| Turnstile 点击 | xdotool 坐标点击（依赖窗口坐标） | 纯 JS iframe 内 click + dispatchEvent + UC 兜底 |
| 代码行数 | 1348 行单文件 | ~700 行，结构同源但去重依赖 |
| Secrets | WEIRDHOST_COOKIE_1..5 / ACCOUNTS 混用 | 统一 WEIRDHOST_COOKIE_1..5，兼容旧 JSON |

## 常见问题

- **Cookie 失效**：TG 提示 `Cookie 已失效`，重新抓取 `remember_web` 更新 Secret 即可；若配了 `REPO_TOKEN` 会自动回写。
- **冷却期**：免费服 24h 冷却，`冷却期内` 属正常，次日会自动再试。
- **无截图**：`upload-artifact` 仅在有 `*.png` 时上传，`if-no-files-found: ignore`。

## 致谢

核心链路与 API 逆向来自 `oyz8/weirdhost-login`（58★, 75 fork），本项目仅做精简与可维护性重构。
