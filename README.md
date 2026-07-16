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

## 固件版本差异

| 版本 | 相对上一版 | 说明 |
|------|------------|------|
| **R011** | —（官方原厂） | 无本仓库补丁。AC 模式下常见：`accept_ra` 不当 → 学不到上游 RA；缺 `/var/dhcp6pd.conf` → `radvd` 无真实 Prefix |
| **R012** | ← R011 | 首次修复包：① Option A（AC 从 `lan1` 收 RA）；② `etc/rc` **晚启动钩子**（周期性/`rc` 延迟：`accept_ra=2`、写 pdconf、`cm dhcp6c_get`）；③ 默认配置倾向 `ipv6enable=1`、关闭无用 igmpsnoop。局限：偏开机路径，**Web 关→开 IPv6 不一定重新武装** |
| **R013** | ← R012 | ① 去掉 `etc/rc` 轮询式钩子；② 改为包装 `/bin/ipv6rahandle` 的**事件钩子**（开机或 Web 启用 IPv6 都会再跑）；③ arm 改为 `expr`，修复设备 ash 不支持 `$((arith))` 导致钩子秒退；④ GUI 关→开 IPv6 后可自动恢复 |
| **R014** | ← R013 | ① 运营商/拨号 **更换 IPv6 前缀** 时：按默认路由 `src` 选当前可达 `/64` 写 pdconf，并后台监视前缀变化；② 换号时先发 **旧前缀 Preferred Lifetime=0** 的 RA（作废），再切到新前缀，避免 Windows 新旧地址都 Preferred、出站仍走旧源地址 |

**推荐刷 [`firmware/HM1A0V100R014.bin`](firmware/HM1A0V100R014.bin)。**  
`HM1A0V100R012.bin` / `R013.bin` / `R014.bin` 是**不同阶段的真实镜像**（功能按上表递增），不要混用文件名与版本能力。

---

## 前提：先在 GUI 打开 IPv6

两条方案都假设 AC 的 **IPv6 功能已启用**。未开启时，`ipv6rahandle` / `radvd` 等路径可能根本不跑，后面的 `accept_ra` / pdconf 也无意义。

1. 登录 AC Web 管理页  
2. 打开 **高级设置 → IPv6**（或同类菜单）  
3. **启用 IPv6**，保存  

说明：

| 方案 | 和 GUI 的关系 |
|------|----------------|
| **刷本仓库固件** | 出厂默认配置里已把 `ipv6enable=1`；若你以前关过 IPv6，或升级保留了旧配置，仍请到 GUI 确认是开的 |
| **Runtime** | 官方原厂固件上 **务必** 先 GUI 启用，再跑脚本 |

可用 debugshell 粗查：`cm get_val` / 配置里 `ipv6enable` 应为 `1`；或看 `ps` 里是否有相关 IPv6/radvd 进程。

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

- [`firmware/HM1A0V100R014.bin`](firmware/HM1A0V100R014.bin)（推荐，当前）  
- [`firmware/HM1A0V100R013.bin`](firmware/HM1A0V100R013.bin) / [`HM1A0V100R012.bin`](firmware/HM1A0V100R012.bin)（历史版本，功能见上表；**内容与 R014 不同**）

基于官方 `HM1A0V100R011` 改包；各 `.bin` 内版本头与文件名一致，并已按设备校验方式重签 payload checksum。

AC 模式补丁要点（当前 R014）：

1. **Option A**：`ipv6rahandle` 在 AC 模式下从 `lan1` 收上游 RA（路由/PPPoE 仍走原路径）  
2. **事件钩子**：包装 `/bin/ipv6rahandle`，每次 **启用 IPv6**（开机或 Web）时自动：  
   - `accept_ra=2`  
   - 按默认路由 `src` 选当前 `/64`，写 `/var/dhcp6pd.conf`  
   - `cm dhcp6c_get` 刷新 `radvd`  
3. arm 用 `expr`（设备 ash **不支持** `$((…))`）  
4. **前缀更换监视**：运营商换 PD 后，先发旧前缀 `Preferred Lifetime=0` 作废 RA，再把 `radvd` 切到新前缀（避免客户端卡在旧 `240e:`）  

**不需要**软路由侧热补丁 / watchdog。

版本演进见上文 [固件版本差异](#固件版本差异)。

### 使用步骤

1. **GUI 启用 IPv6**（见上文「前提」）  
2. 浏览器打开 AC 管理页 → **本地升级 / 固件升级**  
3. 选择 `firmware/HM1A0V100R014.bin`，等待升级完成并重启  
4. 开机后约 **1–2 分钟**（等上游 RA + arm 脚本）  
5. 验证：
   - AC：`lan1` 有全局 IPv6；`/var/radvd.conf` 中 `prefix` 为真实前缀（非全 0）  
   - Wi‑Fi 客户端：能拿到同前缀的全局 IPv6，并能访问 IPv6 网站  
   - （可选）Web 关掉再打开 IPv6，约 1–2 分钟后应能自动恢复  
   - （可选）运营商换前缀后：AC `radvd` / 客户端应在约 1 分钟内跟上新前缀  

同版本号也可再刷（设备允许覆盖同版本时）。

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

### 使用步骤（脚本）

```bash
cd runtime-fix
python apply.py --host 192.168.124.1 --password '你的密码'
```

运行前请确认 **GUI 已启用 IPv6**。脚本会：

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
