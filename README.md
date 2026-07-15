# H3C BR1008L-EI：AC + 软路由场景下 Wi‑Fi 客户端拿不到全局 IPv6

本仓库提供两种修复方式：

| 目录 | 方案 | 是否持久 |
|------|------|----------|
| [`firmware/`](firmware/) | 刷入已打好补丁的固件 | 是（重启仍有效） |
| [`runtime-fix/`](runtime-fix/) | Telnet/debugshell 临时写入 | 否（重启后需重做） |

**适用拓扑：**

```
软路由 (OpenWrt / PPPoE+IPv6)
        │
        ▼
H3C BR1008L-EI  (AC 模式, LAN 口接上游)
        │
        ▼
H3C AP (如 SWBA1B1)
        │
        ▼
Wi‑Fi 客户端  ← 期望拿到全局 IPv6 (如 240e:…)
```

**不适用 / 不必改：** 设备工作在 **路由器 + PPPoE** 时，官方路径本来就会写前缀；本补丁仅在 **AC 模式**（`productmodeflag==1`）启用，避免影响 PPPoE。

---

## 问题原因

有两层独立问题；只修一层往往不够。

### 1. AC 学不到上游 RA（`accept_ra`）

`set_radvds` 会打开 `lan1` 的 IPv6 forwarding。Linux 默认在 `forwarding=1` 且 `accept_ra=1` 时 **不接受** Router Advertisement，于是：

- `/var/rainfo` 可能一直停在无效状态  
- `lan1` 拿不到全局地址（如 `240e:…/64`）

需要：`echo 2 > /proc/sys/net/ipv6/conf/lan1/accept_ra`（允许转发接口收 RA）。

### 2. AC 的 `radvd` 不广播 Prefix（mode=1 缺 PD 文件）

官方 `set_radvds` 按配置分两条路：

| 模式 | 典型场景 | 前缀来源 | 结果 |
|------|----------|----------|------|
| **mode=2** | 路由器 + PPPoE / PD | MW 配置项 `ipv6raprefix` | 写入 `radvd.conf` 的 `prefix …/64` |
| **mode=1** | AC + 上游 RA | `get_dhcp6_pd()` 读 **`/var/dhcp6pd.conf`**，再 `radvd_reconfig` | 文件空/缺失 → 无有效 Prefix（或全 0） |

AC 侧 `ipv6rahandle` 收到 RA 后 mainly 更新 `/var/rainfo`、`/var/ramtu`，**不会**像 PPPoE 那样把学到的前缀写入 `ipv6raprefix`，也 **不会**自动生成 `/var/dhcp6pd.conf`。

因此即使 `lan1` 已有 `240e:`，下游 Wi‑Fi 仍可能只有链路本地地址。

**正确做法（官方路径）：** 写入 `/var/dhcp6pd.conf`，再触发 `cm dhcp6c_get`（内部走 `set_radvds(mode=1)` → `get_dhcp6_pd` → `radvd_reconfig`）。  
**不要**手工往 `/var/radvd.conf` 里塞 `prefix` 行（易与官方重写冲突，且路由/PPPoE 路径本就不该这么改）。

`dhcp6pd.conf` 一行格式（与官方 dhcp6c 写入一致；空格分隔亦可）：

```text
<32位十六进制的 /64 网络前缀> <plen> <preferred> <valid>
```

示例：

```text
240e0390108d2a300000000000000000 64 604800 2592000
```

---

## 方案 A：刷固件（推荐，持久）

### 文件

- [`firmware/HM1A0V100R012.bin`](firmware/HM1A0V100R012.bin)

基于官方 `HM1A0V100R011` 改包，版本头为 `HM1A0V100R012`，并已按设备校验方式重签 payload checksum。AC 模式下 `etc/rc` 增加晚启动钩子：

1. 周期性 `accept_ra=2`  
2. 从 `lan1` 全局 `/64` 生成 `/var/dhcp6pd.conf`  
3. 调用 `cm dhcp6c_get` 刷新 `radvd`

路由器模式不执行该钩子。

### 使用步骤

1. 浏览器打开 AC 管理页 → **本地升级 / 固件升级**  
2. 选择 `firmware/HM1A0V100R012.bin`，等待升级完成并重启  
3. 开机后约 **1–2 分钟**（钩子有延迟重试）  
4. 验证：
   - AC：`lan1` 有全局 IPv6；`/var/radvd.conf` 中 `prefix` 为真实前缀（非全 0）  
   - Wi‑Fi 客户端：能拿到同前缀的全局 IPv6，并能访问 IPv6 网站  

### 风险与注意

- 自定义固件有变砖风险；请确保可恢复官方包  
- 仅在你明确需要 AC+软路由 IPv6 时使用  
- 升级过程中不要断电  

---

## 方案 B：Runtime 临时修复（不刷机）

适合验证、或暂时不能刷机。**重启后失效。**

### 文件

| 文件 | 说明 |
|------|------|
| [`runtime-fix/apply.py`](runtime-fix/apply.py) | 通过 Telnet 自动执行（推荐） |
| [`runtime-fix/manual-commands.sh`](runtime-fix/manual-commands.sh) | 可粘贴到 `debugshell` 的命令说明 |

**不需要**替换 `/bin/ipv6rahandle`。固件里的 `ipv6rahandle` 补丁只解决「AC 收 RA 的网口选 lan1 还是 WAN1」；若 `accept_ra=2` 后 `lan1` 已有全局地址，runtime 只需补 pdconf + 触发 `cm dhcp6c_get` 即可。

### 使用步骤（脚本）

```bash
cd runtime-fix
python apply.py --host 192.168.124.1 --password '你的密码'
```

脚本会：

1. 设置 `lan1/accept_ra=2`  
2. 从 `lan1` 全局地址推导 `/64` 并写入 `/var/dhcp6pd.conf`  
3. 执行 `cm dhcp6c_get`  
4. 检查 `/var/radvd.conf` 是否出现非零 Prefix  

### 使用步骤（手工）

1. Telnet 登录 AC → 进入 `debugshell`  
2. 按 `manual-commands.sh` 中的顺序执行  
3. 用你的真实前缀替换示例中的 hex（或先看 `ip -6 addr show lan1`）  

### 验证

```sh
cat /proc/sys/net/ipv6/conf/lan1/accept_ra    # 应为 2
cat /var/dhcp6pd.conf
grep prefix /var/radvd.conf                   # 应含真实前缀，不是全 0
```

客户端断开重连 Wi‑Fi 或等待 RA 周期后再查 IPv6。

---

## 两种方案怎么选

- **要长期稳定、重启仍可用** → 方案 A 刷固件  
- **先确认环境、临时救急** → 方案 B runtime  
- **已经刷过方案 A** → 一般无需再跑方案 B  

---

## 免责声明

非官方补丁，仅供学习与自用。刷机与修改系统配置造成的设备损坏、网络中断等风险自负。请遵守当地法规与运营商要求。
