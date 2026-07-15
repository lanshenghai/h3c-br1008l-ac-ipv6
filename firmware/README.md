# 已修复固件

| 文件 | 说明 |
|------|------|
| `HM1A0V100R013.bin` | **推荐**刷入 |
| `HM1A0V100R012.bin` | 与 R013 同一镜像（仅文件名不同） |

基线：官方 `HM1A0V100R011`。镜像内版本字符串为 `HM1A0V100R013`。

## 补丁内容（仅 AC 模式）

| 项 | 说明 |
|----|------|
| Option A | `ipv6rahandle`：AC → 在 `lan1` 收 RA；路由器/PPPoE 不变 |
| 事件钩子 | 包装 `/bin/ipv6rahandle`：Web/开机启用 IPv6 时触发一次 |
| `accept_ra=2` | 转发口可学上游 RA |
| `/var/dhcp6pd.conf` + `cm dhcp6c_get` | 走官方 mode=1 → `radvd` 广播真实 Prefix |
| ash 兼容 | arm 用 `expr`，不用 `$((arith))` |

`productmodeflag≠1`（路由器/PPPoE）时 arm 直接退出，不改官方 PD 路径。

**不含**软路由 `br1008l_hotpatch` / 定时热补丁。

升级与验证见仓库根目录 [README.md](../README.md)。
