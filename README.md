# gbot: 高性能智能家庭网关机器人

`gbot` 是一个专为 Linux 网关（如 Raspberry Pi 5）设计的智能管家。它结合了 **eBPF 深度包检测**、**Google 生态集成**与 **Gemini 大模型**，能够自动识别内网家庭成员（特别是小孩）的网络行为，并根据日程安排自动执行网络访问控制。

---

## 🚀 核心特性

- **eBPF 高性能嗅探**: 在内核态实现全端口流量分析，精准提取 DNS 查询与 TLS SNI（服务器名称指示），即使是非标准端口也能识别。
- **Systemd 权限隔离**: 
  - `gmon (Root)`: 负责底层网络操作（eBPF, iptables, dnsmasq）。
  - `gbot (User)`: 负责大脑决策（Gemini）与外部通讯（Google API）。
- **智能行为识别**: Gemini 大脑能通过流量特征和域名自动区分“玩游戏”、“上网课”与“看视频”。
- **Google 日程联动**: 自动同步 Google Calendar 中的“休息”或“网课”安排。
  - **提前预警**: 在断网前 5 分钟通过 Google Chat 发出警告。
  - **精准拦截**: 网课期间仅封禁游戏，保留 YouTube/Zoom 等学习流量；休息时间全网封禁。
- **家长控制中心**: 仅接收来自家长的指令。支持通过对话“增加 30 分钟游戏时间”或“添加新设备”。
- **自主学习**: 遇到未知域名时，Gemini 会主动进行 `web_search` 并在本地 `behavior_map` 中记录学习成果。

---

## 🏗 架构设计

```text
[ 网络流量 ] <--> [ eBPF Kernel Probe ]
                         |
           (Root) [ gmon MCP Server ] <--- Unix Socket ---> (User) [ gbot MCP Host ]
                         |                                           |
                [ iptables / dnsmasq ]                       [ Gemini-CLI Brain ]
                                                                     |
                                                       [ Google Chat / Gmail / Calendar ]
```

---

## 🛠 安装与部署

### 1. 准备环境
确保您的系统（推荐 Raspberry Pi 5 / Linux 6.12+）已安装以下依赖：
- `python3`, `bcc` (BPF Compiler Collection), `iptables`, `dnsmasq`
- `pip install mcp pyyaml google-api-python-client aiohttp`

### 2. 配置文件
创建目录并配置 `/etc/gbot/config.yml`：
```yaml
system:
  interface: "eth0"
  dnsmasq_conf: "/etc/dnsmasq.conf"

users:
  - name: "Parent Name"
    role: "parent"
    contact: "parent@gmail.com"
  - name: "Xiao Ming"
    role: "child"
    calendar_id: "..."
    devices:
      - mac: "AA:BB:CC:DD:EE:FF"
        name: "iPad"
```

### 3. 部署服务
将 `scripts/` 下的服务文件拷贝至系统目录并启动：
```bash
sudo cp scripts/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gmon gbot
```

---

## 📂 项目结构

- `src/gmon/`: 特权数据面。包含 eBPF C 代码、流量聚合引擎和网络控制器。
- `src/gbot/`: 智能控制面。包含 Gemini 提示词、调度器、日程同步和 Google 通道。
- `tests/`: 完整的单元测试与集成测试集。

---

## ⚖️ 许可证
GPL v3
