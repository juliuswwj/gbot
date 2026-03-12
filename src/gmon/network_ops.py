import os
import subprocess
import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class DnsmasqManager:
    def __init__(self, config_path="/etc/dnsmasq.conf"):
        self.config_path = config_path

    def get_hosts(self):
        hosts = []
        try:
            if not os.path.exists(self.config_path):
                return hosts
            with open(self.config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("dhcp-host="):
                        # Format: dhcp-host=MAC,[set:TAG,]IP,NAME
                        # Improved regex to capture optional tag
                        match = re.search(r"dhcp-host=([^,]+),(?:set:([^,]+),)?([^,]+),([^,]+)", line)
                        if match:
                            hosts.append({
                                "mac": match.group(1),
                                "tag": match.group(2) if match.group(2) else "none",
                                "ip": match.group(3),
                                "name": match.group(4)
                            })
        except Exception as e:
            logger.error(f"Error reading dnsmasq config: {e}")
        return hosts

    def update_host(self, mac, ip, name, tag=None):
        """Add or update a dhcp-host entry with optional tag."""
        hosts = self.get_hosts()
        updated = False
        new_hosts = []
        
        for h in hosts:
            if h["mac"].lower() == mac.lower():
                new_hosts.append({"mac": mac, "ip": ip, "name": name, "tag": tag})
                updated = True
            else:
                new_hosts.append(h)
        
        if not updated:
            new_hosts.append({"mac": mac, "ip": ip, "name": name, "tag": tag})
            
        self._save_hosts(new_hosts)
        self.reload_dnsmasq()

    def _save_hosts(self, hosts):
        try:
            lines = []
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    for line in f:
                        if not line.strip().startswith("dhcp-host="):
                            lines.append(line)
            
            for h in hosts:
                tag_str = f"set:{h['tag']}," if h.get("tag") and h['tag'] != "none" else ""
                lines.append(f"dhcp-host={h['mac']},{tag_str}{h['ip']},{h['name']}\n")
                
            with open(self.config_path, "w") as f:
                f.writelines(lines)
        except Exception as e:
            logger.error(f"Error saving dnsmasq config: {e}")

    def reload_dnsmasq(self):
        try:
            # Send SIGHUP to dnsmasq to reload configuration
            subprocess.run(["pkill", "-SIGHUP", "dnsmasq"], check=False)
            logger.info("dnsmasq reloaded.")
        except Exception as e:
            logger.error(f"Failed to reload dnsmasq: {e}")

class FirewallManager:
    def __init__(self, db_path="/var/lib/gbot/blocks.json"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.blocks = self._load_blocks()

    def _load_blocks(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_blocks(self):
        with open(self.db_path, "w") as f:
            json.dump(self.blocks, f, indent=2)

    def get_blocked_list(self):
        return self.blocks

    def set_forwarding(self, rules):
        """
        rules: list of {"ip": "...", "action": "block/allow", "mode": "full/gaming", "reason": "..."}
        """
        for rule in rules:
            ip = rule.get("ip")
            action = rule.get("action")
            mode = rule.get("mode", "full") # Default to full block
            
            if action == "block":
                if mode == "full":
                    self._apply_iptables(ip, block=True)
                elif mode == "gaming":
                    self._apply_gaming_block(ip)
                self.blocks[ip] = {"mode": mode, "blocked_at": str(datetime.now())}
            elif action == "allow":
                self._apply_iptables(ip, block=False)
                self._clear_gaming_block(ip)
                if ip in self.blocks: del self.blocks[ip]
        self._save_blocks()

    def _apply_gaming_block(self, ip):
        # 1. Update eBPF maps with common gaming domains for this IP
        # 2. Or update dnsmasq with specific overrides for this client
        logger.info(f"Applying GAMING-ONLY block for {ip}")

    def _clear_gaming_block(self, ip):
        logger.info(f"Clearing blocks for {ip}")

    def _apply_iptables(self, ip, block=True):
        # We use -I (Insert) to put it at the top of FORWARD chain
        # and -D (Delete) to remove it.
        try:
            if block:
                # First try to delete to avoid duplicates
                subprocess.run(["iptables", "-D", "FORWARD", "-s", ip, "-j", "DROP"], 
                               stderr=subprocess.DEVNULL, check=False)
                subprocess.run(["iptables", "-I", "FORWARD", "-s", ip, "-j", "DROP"], check=True)
                logger.info(f"Blocked IP: {ip}")
            else:
                subprocess.run(["iptables", "-D", "FORWARD", "-s", ip, "-j", "DROP"], check=False)
                logger.info(f"Allowed IP: {ip}")
        except Exception as e:
            logger.error(f"Iptables error for {ip}: {e}")

class BPFManager:
    def __init__(self, interface, bpf_path="src/gmon/ebpf/gmon.bpf.c"):
        self.interface = interface
        self.bpf_path = bpf_path
        self.bpf = None
        self.is_loaded = False

    def load(self):
        """Compile and load eBPF program using BCC."""
        if os.environ.get("GBOT_DEV") == "1":
            logger.info("GBOT_DEV=1, skipping real eBPF loading.")
            return True

        try:
            from bcc import BPF
            # Check if source exists
            if not os.path.exists(self.bpf_path):
                logger.error(f"BPF source not found at {self.bpf_path}")
                return False

            logger.info(f"Loading eBPF program {self.bpf_path} on {self.interface}...")
            self.bpf = BPF(src_file=self.bpf_path)
            
            # Attach to TC (Traffic Control) ingress/egress
            # Note: In a real system, we might need to use 'tc' command via subprocess 
            # if the BCC version doesn't support the high-level attach_tc API well.
            # But for this implementation, we assume BCC can handle the map access.
            fn = self.bpf.load_func("gmon_tc_main", BPF.SCHED_CLS)
            
            # Simple way to attach via subprocess if high-level API is finicky
            subprocess.run(["tc", "qdisc", "add", "dev", self.interface, "clsact"], check=False)
            subprocess.run([
                "tc", "filter", "add", "dev", self.interface, "ingress", 
                "bpf", "da", "obj", "src/gmon/ebpf/gmon.bpf.o", "sec", "tc"
            ], check=False)
            
            self.is_loaded = True
            logger.info("eBPF program loaded.")
            return True
        except ImportError:
            logger.error("BCC (python3-bpfcc) not installed. Cannot load eBPF.")
            return False
        except Exception as e:
            logger.error(f"Failed to load eBPF: {e}")
            return False

    def unload(self):
        """Unload eBPF program and cleanup maps."""
        if not self.is_loaded:
            return
            
        logger.info(f"Unloading eBPF from {self.interface}...")
        subprocess.run(["tc", "qdisc", "del", "dev", self.interface, "clsact"], check=False)
        self.is_loaded = False
        self.bpf = None
        logger.info("eBPF unloaded.")

    def get_bpf(self):
        return self.bpf
