# gbot: 高性能智能家庭网关机器人

`gbot` 是一个专为 Linux 网关（如 Raspberry Pi 5）设计的智能管家。它结合了 **eBPF 深度包检测**、**Google 生态集成**与 **Gemini 大模型**，能够自动识别内网家庭成员的网络行为。

---

## 🚀 核心特性

- **eBPF 高性能嗅探**: 在内核态实现全端口流量分析，精准提取 DNS 查询与 TLS SNI，支持非标准端口识别。
- **Tags 驱动的设备管理**: 
  - **单一事实来源**: 所有设备（MAC/IP/名称/标签）均存储在 `dnsmasq.conf` 中。
  - **解耦设计**: 配置文件仅定义 `用户 <-> 标签` 关系。增加新设备只需在 `dnsmasq` 中打上对应标签即可自动受控。
- **智能行为识别与学习**: 
  - 自动区分“玩游戏”、“上网课”与“看视频”。
  - 遇到未知域名会自动进行 `web_search` 并持久化学习结论。
- **Google 生态联动**: 
  - 同步 Google Calendar 安排（休息/网课）。
  - **提前预警**: 断网前 5 分钟通过 Google Chat 警告。
  - **精准拦截**: 网课期间仅封禁游戏（Roblox等），保留 YouTube/Zoom 等学习工具。
- **特权隔离 (Systemd)**: `gmon` (Root) 负责网络控制，`gbot` (User) 负责大脑逻辑。

---

## 🏗 架构设计

```text
[ 网络流量 ] <--> [ eBPF Kernel Probe ]
                         |
           (Root) [ gmon MCP Server ] <--- Unix Socket ---> (User) [ gbot MCP Host ]
                         |                                           |
                [ iptables / dnsmasq ]                       [ Gemini-CLI Brain ]
                  (Tag-based DB)                                     |
                                                       [ Google Chat / Gmail / Calendar ]
```

---

## 🛠 安装与部署

### 1. 配置文件 (`/etc/gbot/config.yml`)
```yaml
users:
  - name: "Xiao Ming"
    role: "child"
    tag: "xiaoming"  # 对应 dnsmasq 中的 set:xiaoming
    calendar_id: "..."
```

### 2. dnsmasq 配置示例
在 `/etc/dnsmasq.conf` 中通过标签关联用户：
```text
dhcp-host=AA:BB:CC:DD:EE:FF,set:xiaoming,192.168.1.5,Xiaoming-iPad
```

### 3. 部署服务
```bash
sudo cp scripts/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gmon gbot
```

---

## 📂 项目结构
- `src/gmon/`: 特权数据面（eBPF, 流量聚合, dnsmasq 标签管理）。
- `src/gbot/`: 智能控制面（Gemini 提示词, 调度器, Google 接口）。

---

## ⚖️ 许可证
GPL v3
