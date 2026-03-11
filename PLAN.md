# gbot 开发计划：高性能智能网关机器人

`gbot` 是一个运行在 Linux 网关上的自动化程序，通过 eBPF 深度包检测和 Gemini 大模型，实现对内网流量的智能监控、行为识别和自动化访问控制。

---

## 1. 核心架构设计

### 1.1 进程与权限模型
*   **gbot (主进程/控制面)**:
    1.  **启动**: 以 `root` 权限启动，读取 `/root/.gbot.yml`。
    2.  **初始化**: 启动 `gmon` 子进程。
    3.  **降权**: 切换 UID/GID 为普通用户（如 `nobody`），确保核心逻辑（Google API 连接、Gemini 决策）运行在非特权环境。
    4.  **角色**: 充当 **MCP Host**，通过标准输入输出（stdio）与 `gmon` 通信。
    5.  **连接器**: 集成 Gmail 和 Google Chat，作为与用户的沟通界面。
*   **gmon (子进程/数据面)**:
    1.  **特权**: 始终保持 `root` 权限。
    2.  **角色**: 充当 **MCP Server**，提供底层网络能力的抽象。
    3.  **核心模块**: eBPF 嗅探器、数据聚合引擎、`dnsmasq` 管理器、防火墙控制器。

---

## 2. gmon 详细设计 (MCP Server)

### 2.1 eBPF 流量嗅探 (全端口识别)
*   **DNS 捕获**: 拦截所有 UDP 53 包，提取域名查询并存入 BPF Map。
*   **SNI 提取**: 拦截所有 TCP 包，在内核态匹配 TLS Client Hello 特征（无论端口号），提取 SNI 域名。
*   **流量统计**: 统计每个连接（五元组+域名）的字节数 (Byte Count) 和包数 (Packet Count)。

### 2.2 数据聚合引擎 (Summary Aggregator)
*   **本地缓存**: 在内存中维护最近 1 小时的活跃流量表。
*   **去重与统计**: 
    *   同一主机对同一服务的多次访问在提供给 Gemini 前进行聚合。
    *   输出格式示例：`{"service": "roblox.com", "endpoint": "128.x.x.x:UDP", "bytes": "450MB", "activity_type": "high_throughput"}`。
*   **老化机制**: 自动清理长期不活跃的条目，防止内存溢出。

### 2.3 网络管理工具 (MCP Tools)
*   **`get_host_info`**: 解析 `/etc/dnsmasq.conf` 和 `leases` 文件，返回内网所有设备的 `IP-MAC-Name` 对应表。
*   **`update_dnsmasq_config`**: 修改静态 IP 绑定，并重载 `dnsmasq`。
*   **`get_blocked_list`**: 返回当前被拦截的 IP 及其原因（Reason）。
*   **`set_ip_forwarding`**: 批量设置多个 IP 的拦截/通过状态，并关联拦截原因。

---

## 3. gbot 详细设计 (MCP Host & Brain)

### 3.1 权限隔离逻辑 (Privilege Dropping)
*   使用 `os.setuid()` 和 `os.setgid()` 实现不可逆的降权。
*   降权前预先打开必要的系统资源（如果需要），降权后仅保留与 `gmon` 的管道通信。

### 3.2 Gemini 集成 (Brain)
*   **MCP 模式**: 使用 `gemini-cli` 作为核心引擎，自动发现并调用 `gmon` 提供的工具。
*   **行为识别 Logic**: 在 System Prompt 中注入域名/行为映射表。
    *   高频域名匹配（如 Roblox -> 游戏，Zoom -> 网课）。
    5.  **连接器**: 集成 Zoho Cliq，作为与用户的沟通界面，并支持通过 Webhook 接收 Zoho 邮件指令。
    ...
    ### 3.3 沟通渠道 (Channels)
    *   **Zoho Cliq**: 实时发送通知到 Zoho Cliq Channel。
    *   **Zoho Email Webhook**: 接收来自 Zoho 邮件的 Webhook 并在本地监听 8080 端口处理指令。

    ---

    ## 4. 开发路线图

    ### 第一阶段：安全与进程框架 (Security & IPC)
    - [x] 编写 `/root/.gbot.yml` 解析器。
    - [x] 实现 `gbot` 启动 `gmon` 并成功降权的 Python 原型。
    - [x] 建立基于 stdio 的 MCP 通信通道。

    ### 第二阶段：eBPF 采集与数据面 (Data Plane)
    - [x] 编写 eBPF C 代码提取 DNS 和 SNI。
    - [x] 实现 BPF Map 到 Python 聚合引擎的数据导出。
    - [x] 编写流量聚合逻辑，支持 IP:Port 和字节数统计。

    ### 第三阶段：网络工具与管理 (Network Ops)
    - [x] 实现 `dnsmasq.conf` 的读写解析逻辑。
    - [x] 实现基于 `iptables/nftables` 的 IP Forwarding 控制工具。
    5.  **连接器**: 集成 Zoho Cliq 和 Zoho Calendar，作为与用户的沟通与计划同步界面。
    ...
    ### 第四阶段：大脑与通讯 (Intelligence & Channels)
    - [x] 配置 Gemini-CLI 的 MCP Host 环境。
    - [x] 集成 Zoho Cliq (Incoming Webhook)。
    - [x] 集成 Zoho Email (Incoming Webhook Server)。
    - [x] 集成 Zoho Calendar API 同步。
    - [x] 编写针对内网分析优化的 System Prompt。

    ---

    ## 5. 配置文件定义 (`/etc/gbot/config.yml`)

    ```yaml
    system:
      interface: "eth0"
      drop_privileges_to: "nobody"
      dnsmasq_conf: "/etc/dnsmasq.conf"
      block_list_db: "/var/lib/gbot/blocks.json"
      webhook_port: 8080

    zoho:
      client_id: "..."
      client_secret: "..."
      refresh_token: "..."
      region: "com"
      webhook_token: "..."

    gemini:
      api_key: "..."
      model: "gemini-3.1-flash-lite-preview"

    mcp:
      gmon_path: "/usr/local/bin/gmon"
    ```


