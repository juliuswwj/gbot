# gbot: 高性能智能家庭网关机器人

`gbot` 是一个专为 Linux 网关（如 Raspberry Pi 5）设计的智能管家。它结合了 **eBPF 深度包检测**、**Zoho 生态集成**与 **Gemini 大模型**，能够自动识别内网家庭成员的网络行为并执行智能调度。

---

## 🚀 核心特性

- **eBPF 高性能嗅探**: 在内核态实现全端口流量分析，精准提取 SNI 和 DNS。
- **Tags 驱动的设备管理**: 所有设备（MAC/IP/名称/标签）均存储在 `dnsmasq.conf` 中。
- **智能分析与学习**: 区分“游戏”、“网课”与“视频”，支持主动 Web 搜索学习。
- **Zoho 生态联动**: 
  - **同步 Zoho 日历**: 执行“休息/网课”日程安排，并提前 5 分钟发出通知。
  - **Zoho Cliq 通知**: 实时发送状态报告与报警到指定的 Cliq 频道。
  - **Zoho Email 控制**: 支持通过 Zoho 邮件 Webhook 接收远程指令并由 Gemini 处理。
- **加固与优化**: 
  - **安全隔离**: `gmon (Root)` 与 `gbot (User)` 通过 Unix Socket (`0660`, Group: `gbot`) 进行通信。
  - **权限分级**: 源码属主为 `root`，防止降权后的 `gbot` 用户篡改代码。

---

## 🏗 架构设计

```text
(Root) [ gmon MCP Server ] <--- Unix Socket (0660) ---> (User: gbot) [ gbot MCP Host ]
      | (eBPF, Network Ops)                                | (Scheduler, Channels)
      |                                                    |
      +--> [ dnsmasq.conf ]                                +--> [ Gemini-CLI ]
           (Single Source of Truth)                             +--> [ Zoho Cliq/Calendar ]
```

---

## 🛠 安装说明

### 1. 准备环境与用户
```bash
sudo apt update
sudo apt install python3-pip python3-venv clang llvm libelf-dev bpfcc-tools iptables dnsmasq
sudo useradd -m -r -d /etc/gbot -s /usr/sbin/nologin gbot
```

### 2. 源码部署与权限
```bash
sudo mkdir -p /opt/gbot /var/lib/gbot /etc/gbot
sudo chown -R gbot:gbot /var/lib/gbot /etc/gbot
# 将源码放入 /opt/gbot/src ...
```

### 3. 配置文件示例 (`/etc/gbot/config.yml`)
```yaml
system:
  interface: "eth0"
  webhook_port: 8080
  dnsmasq_conf: "/etc/dnsmasq.conf"
  block_list_db: "/var/lib/gbot/blocks.json"

zoho:
  client_id: "1000.XXXXXX"
  client_secret: "XXXXXX"
  refresh_token: "1000.XXXXXX.XXXXXX"
  region: "com"
  webhook_token: "your_secure_token"  # Used for /bot/mail and /bot/chat auth
  cron_chat_id: "16087..."            # Default chat for daily reports/warnings
  cron_chat_language: "en_us"         # Language for daily reports (default: en_us)

gemini:
  api_key: "AIzaSy..."  # Optional: Google AI Studio API Key (Priority)
  model: "gemini-3.1-flash-lite-preview"  # Default if not specified

users:
  - name: "Child1"
    role: "child"
    calendar_id: "hex_calendar_id_here"
    devices: ["AA:BB:CC:DD:EE:FF"]
  - name: "Dad"
    role: "parent"
    contact: "dad@example.com"
    language: "zh_cn"                 # Language for brain responses (default: zh_cn)
```

### 4. Zoho API 配置说明 (Cliq & Calendar)

#### 1. 注册 Zoho 应用程序
1. 访问 [Zoho API Console](https://api-console.zoho.com/)。
2. 注册一个 **Server-based Application**。
3. 获取 `Client ID` 和 `Client Secret`。

#### 2. 获取授权令牌 (Scope)
引导 OAuth2 流程以获取 `refresh_token`。**必须** 包含以下 Scope 以同时支持日历同步和聊天功能：
*   `ZohoCalendar.calendar.READ` (日历读取)
*   `ZohoCliq.chats.CREATE` (发送消息到聊天)
*   `ZohoCliq.messages.CREATE` (消息处理)

#### 3. 配置 Webhook (Zoho Cliq Webhook)
1. 在 Zoho Cliq 中设置 **Bot** 或 **Outgoing Webhook**。
2. **端点地址**：
   - 指向 `http://<your-gateway-ip>:8080/bot/chat` (Cliq 聊天消息)
   - 指向 `http://<your-gateway-ip>:8080/bot/mail` (邮件/系统通知)
3. **安全认证**：设置 `webhook_token` 并在 Webhook 头部包含 `Authorization: Bearer <webhook_token>`。
4. **数据格式**：
   - `/bot/chat`：由 Zoho Cliq 自动生成。支持 `message`, `mention`, `function` 处理器。
   - `/bot/mail`：自定义 JSON (包含 `from`, `subject`, `content`, `id`, `chat_id`)。


### 5. 编译与测试
```bash
./test.sh
```
由于切换到了 Zoho Webhook 模式，集成测试现在可以通过 `curl` 模拟 Zoho 的 Webhook 请求。
