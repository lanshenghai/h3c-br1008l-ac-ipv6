# 已修复固件

| 文件 | 说明 |
|------|------|
| `HM1A0V100R012.bin` | AC+软路由 IPv6 修复包（Web 本地升级） |

基线：官方 `HM1A0V100R011`。镜像内版本字符串为 `HM1A0V100R012`。

AC 模式晚启动钩子（`etc/rc` 标记 `ipv6_ac_mode1_pd`）：

- `accept_ra=2`
- 写 `/var/dhcp6pd.conf`
- `cm dhcp6c_get`

路由器 / PPPoE 模式不启用该钩子。

升级与验证见仓库根目录 [README.md](../README.md)。
