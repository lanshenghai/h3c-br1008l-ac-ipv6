#!/bin/sh
# BR1008L AC — runtime IPv6 fix (paste into debugshell). NOT persistent across reboot.
#
# Do NOT manually edit /var/radvd.conf prefix lines.
# Official path: /var/dhcp6pd.conf -> get_dhcp6_pd -> set_radvds(mode=1) -> radvd_reconfig

# 1) Allow RA on forwarding interface
echo 2 > /proc/sys/net/ipv6/conf/lan1/accept_ra

# 2) Wait until lan1 has a global address, then check:
#    ip -6 addr show lan1

# 3) Write dhcp6pd.conf
#    Format: <32 hex digits of /64 network> 64 <preferred> <valid>
#    Example for 240e:390:108d:2a30::/64 — REPLACE with YOUR prefix:
echo '240e0390108d2a300000000000000000 64 604800 2592000' > /var/dhcp6pd.conf
cat /var/dhcp6pd.conf

# How to build the 32 hex digits from e.g. 240e:390:108d:2a30:xxxx:xxxx:xxxx:xxxx/64:
#   - take the /64 network (first 64 bits)
#   - write as 32 lowercase hex characters, host part all zero
#   240e:0390:108d:2a30:0000:0000:0000:0000  ->  240e0390108d2a300000000000000000

# 4) Trigger official mode=1 refresh (more reliable than only poking /var/rainfo)
cm dhcp6c_get

# 5) Verify — prefix must NOT be all zeros
grep -i prefix /var/radvd.conf

# Expected something like:
#   prefix 240e:0390:108d:2a30:0000:0000:0000:0000/64
