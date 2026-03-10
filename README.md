# gbot: 高性能智能家庭网关机器人

`gbot` 是一个专为 Linux 网关（如 Raspberry Pi 5）设计的智能管家。它结合了 **eBPF 深度包检测**、**Google 生态集成**与 **Gemini 大模型**，能够自动识别内网家庭成员的网络行为并执行智能调度。

---

## 🚀 核心特性

- **eBPF 高性能嗅探**: 在内核态实现全端口流量分析，精准提取 SNI 和 DNS。
- **Tags 驱动的设备管理**: 所有设备（MAC/IP/名称/标签）均存储在 `dnsmasq.conf` 中。
- **智能分析与学习**: 区分“游戏”、“网课”与“视频”，支持主动 Web 搜索学习。
- **Google 生态联动**: 
  - **同步日历**: 执行“休息/网课”日程安排，并提前 5 分钟发出 Chat 警告。
  - **精细控制**: 网课期间仅封禁游戏，保留学习工具。
- **加固与优化**: 
  - **安全隔离**: `gmon (Root)` 与 `gbot (User)` 通过 Unix Socket (`0660`, Group: `gbot`) 进行通信。
  - **权限分级**: **源码存放在 `/opt/gbot`，属主为 `root`，防止降权后的 `gbot` 用户篡改代码。**
  - **SD 卡优化**: SQLite WAL 模式，支持 30 天自动老化。

---

## 🏗 架构设计

```text
(Root) [ gmon MCP Server ] <--- Unix Socket (0660) ---> (User: gbot) [ gbot MCP Host ]
      | (eBPF, Network Ops)                                | (Scheduler, Channels)
      |                                                    |
      +--> [ dnsmasq.conf ]                                +--> [ Gemini-CLI ]
           (Single Source of Truth)                             (/etc/gbot/.gemini/settings.json)
```

---

## 🛠 安装说明

### 1. 准备环境与用户
在树莓派上安装基础系统库并创建专用用户：
```bash
sudo apt update
sudo apt install python3-pip python3-venv clang llvm libelf-dev bpfcc-tools iptables dnsmasq
# 创建 gbot 用户，主目录设为 /etc/gbot
sudo useradd -m -r -d /etc/gbot -s /usr/sbin/nologin gbot
```

### 2. 源码部署与权限加固
将代码部署到 `/opt/gbot`，并建立虚拟环境：
```bash
sudo mkdir -p /opt/gbot
# 将项目源码拷贝至 /opt/gbot/src
# 确保源码属主为 root，防止 gbot 用户被攻破后篡改代码
sudo chown -R root:root /opt/gbot

# 创建并安装虚拟环境
sudo python3 -m venv /opt/gbot/venv
sudo /opt/gbot/venv/bin/pip install mcp pyyaml google-api-python-client aiohttp
```

### 3. 数据与配置目录权限
创建持久化数据目录，并分配给 `gbot` 用户：
```bash
sudo mkdir -p /var/lib/gbot
sudo chown -R gbot:gbot /var/lib/gbot /etc/gbot
```

### 4. 安装 gemini-cli (大脑引擎)
`gbot` 依赖 `gemini-cli` 作为决策大脑。请务必切换到 `gbot` 用户进行安装，以确保环境隔离：

```bash
# 1. 切换到 gbot 用户
sudo -u gbot /bin/bash
cd ~

# 2. 安装 nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc

# 3. 安装 Node.js (推荐 v20+)
nvm install 20

# 4. 全局安装 gemini-cli
npm install -g @google/gemini-cli
```

安装完成后，退出 `gbot` 用户返回 root。

### 5. 配置 Google API 与 Gemini-CLI
- **Google API**: 将凭证 JSON 放入 `/etc/gbot/google_secret.json`。
- **Gemini-CLI**: 为 `gbot` 用户配置 `/etc/gbot/.gemini/settings.json`：
  ```json
  {
    "api_key": "YOUR_GOOGLE_API_KEY",
    "model": "gemini-2.0-flash",
    "tools": ["google_web_search"]
  }
  ```
  *注意：gbot 会自动加载该配置。*

### 6. 编译、测试与部署
```bash
./test.sh
sudo cp scripts/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gmon gbot
```

---

## ⚖️ 许可证
GPL v3
