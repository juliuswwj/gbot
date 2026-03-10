# gbot: 高性能智能家庭网关机器人

`gbot` 是一个专为 Linux 网关（如 Raspberry Pi 5）设计的智能管家。它结合了 **eBPF 深度包检测**、**Google 生态集成**与 **Gemini 大模型**，能够自动识别内网家庭成员的网络行为并执行智能调度。

---

## 🚀 核心特性

- **eBPF 高性能嗅探**: 在内核态实现全端口流量分析，即使是非标准端口也能精准提取 SNI 和 DNS。
- **Tags 驱动的设备管理**: 
  - **单一事实来源**: 所有设备（MAC/IP/名称/标签）均存储在 `dnsmasq.conf` 中。
- **智能行为识别与学习**: 区分“游戏”、“网课”与“视频”，并支持主动 Web 搜索学习未知流量。
- **Google 生态联动**: 
  - **同步日历**: 自动执行“休息/网课”安排。
  - **提前预警**: 断网前 5 分钟发出 Chat 警告。
  - **精细控制**: 网课期间仅封禁游戏，保留 YouTube/Zoom 等。
- **存储优化**: 针对 SD 卡优化的 SQLite (WAL 模式)，支持 30 天自动老化。

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

## 🛠 安装说明

### 1. 准备环境与用户
在树莓派上安装依赖并创建专用用户：
```bash
sudo apt update
sudo apt install python3-pip clang llvm libelf-dev bpfcc-tools iptables dnsmasq
sudo useradd -m -r -s /usr/sbin/nologin gbot
pip3 install mcp pyyaml google-api-python-client aiohttp
```

### 2. 目录权限配置
创建必要的系统目录并分配权限：
```bash
sudo mkdir -p /etc/gbot /var/lib/gbot /run/gbot
sudo chown -R gbot:gbot /etc/gbot /var/lib/gbot
# gmon.sock 所在目录权限由 gmon.service 自动管理
```

### 3. 配置 gbot
创建并配置 `/etc/gbot/config.yml`：
```yaml
# ... (配置内容同前) ...
```

### 4. 配置 Google API 与 Gemini-CLI
- **Google API**: 将您的 OAuth2 凭证 JSON 放入 `/etc/gbot/google_secret.json`。
- **Gemini-CLI**: 为 `gbot` 用户配置 `/home/gbot/.gemini/settings.json`：
  ```json
  {
    "api_key": "YOUR_GOOGLE_API_KEY",
    "model": "gemini-2.0-flash",
    "tools": ["google_web_search"]
  }
  ```
  确保该文件属主为 `gbot:gbot` 且权限为 `600`。

### 4. 编译与测试
运行测试脚本验证环境与代码逻辑：
```bash
./test.sh
```

### 5. 部署服务
```bash
sudo cp scripts/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gmon gbot
```

---

## 📂 项目结构
- `src/gmon/`: 特权数据面（eBPF, 流量聚合, 历史数据库）。
- `src/gbot/`: 智能控制面（Gemini 提示词, 调度器, Google 接口）。

---

## ⚖️ 许可证
GPL v3
