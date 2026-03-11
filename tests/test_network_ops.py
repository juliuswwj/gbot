import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
from gmon.network_ops import DnsmasqManager, FirewallManager

class TestNetworkOps(unittest.TestCase):
    def test_dnsmasq_get_hosts(self):
        config_content = (
            "interface=eth0\n"
            "dhcp-host=AA:BB:CC:DD:EE:FF,192.168.1.10,pc-one\n"
            "dhcp-host=11:22:33:44:55:66,192.168.1.11,pc-two\n"
        )
        with patch("builtins.open", mock_open(read_data=config_content)):
            with patch("os.path.exists", return_value=True):
                mgr = DnsmasqManager("/fake/dnsmasq.conf")
                hosts = mgr.get_hosts()
                self.assertEqual(len(hosts), 2)
                self.assertEqual(hosts[0]["name"], "pc-one")
                self.assertEqual(hosts[1]["ip"], "192.168.1.11")

    @patch("subprocess.run")
    @patch("json.dump")
    def test_firewall_set_forwarding_block(self, mock_json_dump, mock_run):
        # Setup mock for db path
        with patch("os.makedirs"):
            with patch("builtins.open", mock_open(read_data="{}")):
                mgr = FirewallManager("/fake/blocks.json")
                mgr.set_forwarding([{"ip": "1.2.3.4", "action": "block", "reason": "testing"}])
                
                # Check if iptables was called to block
                # It calls D then I
                calls = [call.args[0] for call in mock_run.call_args_list]
                self.assertIn(["iptables", "-I", "FORWARD", "-s", "1.2.3.4", "-j", "DROP"], calls)

    @patch("subprocess.run")
    @patch("json.dump")
    def test_firewall_set_forwarding_allow(self, mock_json_dump, mock_run):
         with patch("os.makedirs"):
            with patch("builtins.open", mock_open(read_data='{"1.2.3.4": {"reason": "old"}}')):
                mgr = FirewallManager("/fake/blocks.json")
                mgr.set_forwarding([{"ip": "1.2.3.4", "action": "allow"}])
                
                # Check if iptables was called to delete
                calls = [call.args[0] for call in mock_run.call_args_list]
                self.assertIn(["iptables", "-D", "FORWARD", "-s", "1.2.3.4", "-j", "DROP"], calls)

if __name__ == '__main__':
    unittest.main()
