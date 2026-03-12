import asyncio
import os
import json
import logging
import subprocess
import shutil
from datetime import datetime, date
from gmon.mcp_server import call_tool, bpf_manager, aggregator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - gmon-test - %(levelname)s - %(message)s')
logger = logging.getLogger("test")

# Paths for backup
DNSMASQ_CONF = "/etc/dnsmasq.conf"
BLOCKS_JSON = "/var/lib/gbot/blocks.json"
BEHAVIOR_JSON = "/var/lib/gbot/behavior_map.json"

BACKUP_DIR = "/tmp/gmon_test_backup"

def backup_system():
    logger.info("Backing up system configurations...")
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    # Backup dnsmasq
    if os.path.exists(DNSMASQ_CONF):
        shutil.copy2(DNSMASQ_CONF, os.path.join(BACKUP_DIR, "dnsmasq.conf.bak"))
    
    # Backup firewall state
    if os.path.exists(BLOCKS_JSON):
        shutil.copy2(BLOCKS_JSON, os.path.join(BACKUP_DIR, "blocks.json.bak"))
    
    # Backup behavior map
    if os.path.exists(BEHAVIOR_JSON):
        shutil.copy2(BEHAVIOR_JSON, os.path.join(BACKUP_DIR, "behavior_map.json.bak"))

def restore_system():
    logger.info("Restoring system configurations...")
    
    # Restore dnsmasq
    bak_dnsmasq = os.path.join(BACKUP_DIR, "dnsmasq.conf.bak")
    if os.path.exists(bak_dnsmasq):
        shutil.copy2(bak_dnsmasq, DNSMASQ_CONF)
        # Reload dnsmasq
        subprocess.run(["pkill", "-SIGHUP", "dnsmasq"], check=False)
    
    # Restore firewall state
    bak_blocks = os.path.join(BACKUP_DIR, "blocks.json.bak")
    if os.path.exists(bak_blocks):
        shutil.copy2(bak_blocks, BLOCKS_JSON)
    elif os.path.exists(BLOCKS_JSON):
        os.remove(BLOCKS_JSON)
        
    # Restore behavior map
    bak_behavior = os.path.join(BACKUP_DIR, "behavior_map.json.bak")
    if os.path.exists(bak_behavior):
        shutil.copy2(bak_behavior, BEHAVIOR_JSON)

    # Cleanup iptables (just try to remove our dummy block)
    subprocess.run(["iptables", "-D", "FORWARD", "-s", "192.168.1.254", "-j", "DROP"], 
                   stderr=subprocess.DEVNULL, check=False)
    
    # Unload BPF if it was loaded during test
    bpf_manager.unload()
    
    logger.info("Restore complete.")

async def test_ping():
    logger.info("Testing 'ping'...")
    res = await call_tool("ping", {"message": "hello"})
    assert "pong: hello" in res[0].text
    logger.info("OK.")

async def test_dnsmasq_update():
    logger.info("Testing 'update_dnsmasq_host'...")
    # Add a dummy host
    dummy = {"mac": "00:11:22:33:44:55", "ip": "192.168.1.100", "name": "dummy-host", "tag": "test-tag"}
    res = await call_tool("update_dnsmasq_host", dummy)
    assert "Updated" in res[0].text
    
    # Verify it exists
    res = await call_tool("get_host_info", {})
    hosts = json.loads(res[0].text)
    found = any(h["mac"] == dummy["mac"] and h["tag"] == dummy["tag"] for h in hosts)
    assert found, "Dummy host not found in host info"
    logger.info("OK.")

async def test_firewall():
    logger.info("Testing 'set_ip_forwarding'...")
    dummy_ip = "192.168.1.254"
    
    # Block IP
    res = await call_tool("set_ip_forwarding", {"rules": [{"ip": dummy_ip, "action": "block"}]})
    assert "Applied" in res[0].text
    
    # Check iptables
    output = subprocess.check_output(["iptables", "-L", "FORWARD", "-n"]).decode()
    assert dummy_ip in output, f"IP {dummy_ip} not found in iptables FORWARD chain"
    
    # Unblock IP
    res = await call_tool("set_ip_forwarding", {"rules": [{"ip": dummy_ip, "action": "allow"}]})
    assert "Applied" in res[0].text
    
    # Check iptables again
    output = subprocess.check_output(["iptables", "-L", "FORWARD", "-n"]).decode()
    assert dummy_ip not in output, f"IP {dummy_ip} still found in iptables FORWARD chain after allow"
    logger.info("OK.")

async def test_behavior():
    logger.info("Testing 'save_behavior_category'...")
    res = await call_tool("save_behavior_category", {"domain": "test.local", "category": "testing"})
    assert "Saved" in res[0].text
    
    res = await call_tool("get_behavior_map", {})
    behaviors = json.loads(res[0].text)
    assert behaviors.get("test.local") == "testing"
    logger.info("OK.")

async def test_activity():
    logger.info("Testing 'get_host_activity' (Requires eBPF)...")
    
    # 1. Ensure BPF is loaded
    bpf_instance = bpf_manager.get_bpf()
    if not bpf_instance:
        logger.warning("eBPF not loaded. get_host_activity test will be limited to empty state.")
    else:
        # 2. Manually trigger a poll of the BPF maps
        try:
            aggregator.process_ebpf_data(bpf_instance)
            logger.info("Successfully processed real eBPF data maps.")
        except Exception as e:
            logger.error(f"Failed to process eBPF data: {e}")
    
    # 3. Call tool
    res = await call_tool("get_host_activity", {"host_name": "nonexistent"})
    data = json.loads(res[0].text)
    assert isinstance(data, dict)
    logger.info("OK.")

async def test_history():
    logger.info("Testing 'get_history_report'...")
    today_str = str(date.today())
    res = await call_tool("get_history_report", {"date": today_str})
    data = json.loads(res[0].text)
    assert data is not None
    logger.info("OK.")

async def main():
    if os.getuid() != 0:
        logger.error("This test MUST be run as root (to touch iptables/dnsmasq/eBPF).")
        return

    backup_system()
    try:
        # 1. Initial eBPF load for the entire test suite
        if not bpf_manager.load():
            logger.warning("eBPF load failed. Some tests will be skipped or limited.")

        # 2. Run tools tests
        await test_ping()
        await test_dnsmasq_update()
        await test_firewall()
        await test_behavior()
        await test_activity()
        await test_history()
        
        logger.info("\nALL FUNCTIONAL TESTS PASSED ON REAL PLATFORM.")
    except Exception as e:
        logger.error(f"Tests FAILED: {e}", exc_info=True)
    finally:
        restore_system()

if __name__ == "__main__":
    asyncio.run(main())
