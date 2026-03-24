#!/bin/bash

# ============================================
# DNS Toggler
# Double-click to cycle: AdGuard → Multi-DNS → Automatic → AdGuard
# For Wi-Fi network interface
# ============================================
#
# HOW TO MAKE THIS SCRIPT RUNNABLE:
# 1. Open Terminal
# 2. Run: chmod +x /path/to/Toggle-DNS.command
#    Example: chmod +x ~/Desktop/Toggle-DNS.command
# 3. Double-click the file to run it
#
# NOTE: The .command extension allows double-click execution on macOS
# ============================================

INTERFACE="Wi-Fi"
ADGUARD_DNS_1="94.140.14.14"
ADGUARD_DNS_2="94.140.15.15"
GOOGLE_DNS="8.8.8.8"
CLOUDFLARE_DNS="1.1.1.1"
OPENDNS="208.67.222.222"

# Get current DNS
CURRENT_DNS=$(networksetup -getdnsservers "$INTERFACE" 2>/dev/null)

if [[ "$CURRENT_DNS" == *"$ADGUARD_DNS_1"* ]]; then
    # AdGuard → Multi-DNS (Google, Cloudflare, OpenDNS)
    networksetup -setdnsservers "$INTERFACE" "$GOOGLE_DNS" "$CLOUDFLARE_DNS" "$OPENDNS"
    osascript -e 'display notification "DNS set to Multi-DNS" with title "DNS Toggler"'
    echo "✓ DNS set to Multi-DNS ($GOOGLE_DNS, $CLOUDFLARE_DNS, $OPENDNS)"
elif [[ "$CURRENT_DNS" == *"$GOOGLE_DNS"* ]]; then
    # Multi-DNS → Automatic
    networksetup -setdnsservers "$INTERFACE" "Empty"
    osascript -e 'display notification "DNS set to Automatic" with title "DNS Toggler"'
    echo "✓ DNS set to Automatic"
else
    # Automatic/other → AdGuard
    networksetup -setdnsservers "$INTERFACE" "$ADGUARD_DNS_1" "$ADGUARD_DNS_2"
    osascript -e 'display notification "DNS set to AdGuard" with title "DNS Toggler"'
    echo "✓ DNS set to AdGuard ($ADGUARD_DNS_1, $ADGUARD_DNS_2)"
fi

# Flush DNS cache
dscacheutil -flushcache
killall -HUP mDNSResponder 2>/dev/null

echo ""
echo "DNS cache flushed."
sleep 2
