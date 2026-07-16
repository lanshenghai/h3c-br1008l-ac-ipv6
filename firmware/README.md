# 已修复固件

| 文件 | 说明 |
|------|------|
| `HM1A0V100R014.bin` | **推荐**刷入（镜像版本字符串 R014） |
| `HM1A0V100R013.bin` / `HM1A0V100R012.bin` | 与 R014 **同一镜像**（仅文件名不同） |

基线：官方 `HM1A0V100R011`。版本演进详见仓库首页 [README · 固件版本差异](../README.md#固件版本差异)。

## 版本差异（摘要）

| 版本 | 相对上一版 | 要点 |
|------|------------|------|
| **R011** | 官方原厂 | 无补丁 |
| **R012** | ← R011 | Option A + `etc/rc` 晚启动钩子 |
| **R013** | ← R012 | 事件钩子 + `expr`；GUI 开关可恢复 |
| **R014** | ← R013 | 前缀更换：按路由 `src` 选 `/64` + 后台监视；换号时旧前缀 Preferred=0 作废 RA |

## 补丁内容（仅 AC 模式，R014）

| 项 | 说明 |
|----|------|
| Option A | `ipv6rahandle`：AC → 在 `lan1` 收 RA；路由器/PPPoE 不变 |
| 事件钩子 | 包装 `/bin/ipv6rahandle`：Web/开机启用 IPv6 时触发 |
| `accept_ra=2` | 转发口可学上游 RA |
| `/var/dhcp6pd.conf` + `cm dhcp6c_get` | 官方 mode=1 → `radvd` 广播真实 Prefix |
| 前缀监视 | 默认路由 `src` 变化时刷新 pdconf/`radvd`；先发旧前缀 Preferred=0 |
| ash 兼容 | arm 用 `expr`，不用 `$((arith))` |

`productmodeflag≠1`（路由器/PPPoE）时 arm 直接退出。

升级与验证见仓库根目录 [README.md](../README.md)。
