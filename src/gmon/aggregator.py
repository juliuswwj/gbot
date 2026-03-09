import time
import socket
import struct
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class TrafficAggregator:
    def __init__(self):
        # Local cache for Hostnames (IP -> Name)
        self.host_map = {}
        # Local cache for Domains (IP -> Domain)
        self.domain_cache = {}
        # Aggregated stats: {ip: {service_name: {bytes, pkts, last_seen}}}
        self.stats = defaultdict(lambda: defaultdict(lambda: {"bytes": 0, "pkts": 0, "last_seen": 0}))

    def update_host_map(self, dnsmasq_leases_path="/var/lib/misc/dnsmasq.leases"):
        """Update IP to Hostname mapping from dnsmasq leases."""
        try:
            with open(dnsmasq_leases_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        ip, name = parts[2], parts[3]
                        self.host_map[ip] = name
        except FileNotFoundError:
            logger.warning(f"Leases file not found: {dnsmasq_leases_path}")

    def format_ip(self, ip_u32):
        return socket.inet_ntoa(struct.pack("<L", ip_u32))

    def process_ebpf_data(self, bpf_instance):
        """Read data from BPF maps and aggregate."""
        active_flows = bpf_instance.get_table("active_flows")
        
        # In a real BCC app, we iterate over the map
        for key, val in active_flows.items():
            saddr = self.format_ip(key.saddr)
            daddr = self.format_ip(key.daddr)
            dport = key.dport
            proto = "TCP" if key.proto == 6 else "UDP"
            
            # Identify service (Domain or Endpoint)
            service = self.domain_cache.get(daddr, f"{daddr}:{dport}/{proto}")
            
            host_name = self.host_map.get(saddr, saddr)
            
            # Aggregate
            node = self.stats[host_name][service]
            node["bytes"] = val.bytes
            node["pkts"] = val.pkts
            node["last_seen"] = val.last_seen

    def get_summary(self, hostname=None):
        """Return a summary for Gemini."""
        if hostname:
            return self.stats.get(hostname, {})
        return dict(self.stats)

# Helper to parse dnsmasq.conf for static hosts
def parse_dnsmasq_conf(path="/etc/dnsmasq.conf"):
    hosts = {}
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("dhcp-host="):
                    # dhcp-host=MAC,IP,NAME
                    parts = line.split("=")[1].split(",")
                    if len(parts) >= 3:
                        ip, name = parts[1], parts[2]
                        hosts[ip] = name
    except Exception as e:
        logger.error(f"Error parsing dnsmasq.conf: {e}")
    return hosts
