# gbot: 高性能智能家庭网关机器人

`gbot` 是一个专为 Linux 网关（如 Raspberry Pi 5）设计的智能管家。它结合了 **eBPF 深度包检测**、**Google 生态集成**与 **Gemini 大模型**，能够自动识别内网家庭成员的网络行为。

---

## 🚀 核心特性

- **eBPF 高性能嗅探**: 在内核态实现全端口流量分析，精准提取 DNS 查询与 TLS SNI，支持非标准端口识别。
- **Tags 驱动的设备管理**: 
  - **单一事实来源**: 所有设备（MAC/IP/名称/标签）均存储在 `dnsmasq.conf` 中。
  - **解耦设计**: 配置文件仅定义 `用户 <-> 标签` 关系。
- **智能行为识别与学习**: 
  - 自动区分“玩游戏”、“上网课”与“看视频”。
  - 遇到未知域名会自动进行 `web_search` 并持久化学习结论。
- **Google 生态联动**: 
  - 同步 Google Calendar 安排（休息/网课）。
  - **提前预警**: 断网前 5 分钟通过 Google Chat 警告。
- **存储优化**: 针对 SD 卡优化的 SQLite (WAL 模式)，支持 30 天自动数据老化与空间压缩。

---

## 🛠 配置指南

### 1. gbot 核心配置 (`/etc/gbot/config.yml`)
该文件定义了系统行为和用户关系：
```yaml
system:
  interface: "eth0"
  dnsmasq_conf: "/etc/dnsmasq.conf"

google_api:
  chat_webhook_url: "https://chat.googleapis.com/v1/spaces/..." # Google Chat Webhook 地址
  # Gmail 和 Calendar 凭证通常由环境变量或默认路径加载

users:
  - name: "Xiao Ming"
    role: "child"
    tag: "xiaoming"
    calendar_id: "family_rest@group.calendar.google.com" # 该小孩关联的日历 ID
  - name: "Dad"
    role: "parent"
    contact: "dad@gmail.com" # 家长的 Gmail 地址，仅接收此地址发来的指令
```

### 2. Google 通道集成
- **Google Chat**: 在您的 Google Chat Space 中创建一个 Webhook，并将 URL 填入上述 `chat_webhook_url`。
- **Gmail & Calendar**: 
  - `gbot` 使用 Google Python SDK 进行操作。
  - 建议将 OAuth2 凭证 JSON 文件放在 `/etc/gbot/google_secret.json`。
  - 运行时需确保环境变量 `GOOGLE_APPLICATION_CREDENTIALS` 指向该文件。

### 3. Gemini-CLI 配置
`gbot` 内部调用 `gemini-cli` 作为大脑。您可以直接使用 `gemini-cli` 原生的配置方式：
- **配置文件**: `~/.gemini/settings.json` (针对运行 gbot 的普通用户)。
- **配置内容**: 在此文件中设置您的 `api_key`、默认模型以及启用 `google_web_search` 工具。
- **环境变量**: 也可以通过 `GOOGLE_API_KEY` 环境变量直接传递。

---

## 🏗 架构设计

```text
(Root) [ gmon MCP Server ] <--- Unix Socket ---> (User) [ gbot MCP Host ]
      | (eBPF, Network Ops)                           | (Scheduler, Channels)
      |                                               |
      +--> [ dnsmasq.conf ]                           +--> [ Gemini-CLI ]
           (Single Source of Truth)                        (~/.gemini/settings.json)
```

---

## 📂 项目结构
- `src/gmon/`: 特权数据面（eBPF, 流量聚合, 历史数据库, dnsmasq 标签管理）。
- `src/gbot/`: 智能控制面（Gemini 提示词, 调度器, Google 接口）。

---

## ⚖️ 许可证
GPL v3
