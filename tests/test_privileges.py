import unittest
from unittest.mock import patch, MagicMock
import os
from src.gbot.privileges import drop_privileges

class TestPrivileges(unittest.TestCase):
    @patch("os.getuid")
    @patch("pwd.getpwnam")
    @patch("os.setuid")
    @patch("os.setgid")
    @patch("os.setgroups")
    @patch("os.environ")
    def test_drop_privileges_as_root(self, mock_environ, mock_setgroups, mock_setgid, mock_setuid, mock_getpwnam, mock_getuid):
        # Setup: process is root
        mock_getuid.return_value = 0
        
        # Setup: user 'nobody' exists
        mock_user = MagicMock()
        mock_user.pw_uid = 65534
        mock_user.pw_gid = 65534
        mock_user.pw_dir = "/nonexistent"
        mock_getpwnam.return_value = mock_user
        
        # Act
        drop_privileges("nobody")
        
        # Assert: privileges are dropped
        mock_setuid.assert_called_with(65534)
        mock_setgid.assert_called_with(65534)
        mock_setgroups.assert_called_with([])
        mock_environ.__setitem__.assert_any_call("USER", "nobody")

    @patch("os.getuid")
    def test_drop_privileges_as_non_root(self, mock_getuid):
        # Setup: process is not root
        mock_getuid.return_value = 1000
        
        # Act
        # Should not throw any exception and should not call setuid
        drop_privileges("nobody")
        
    @patch("os.getuid")
    @patch("pwd.getpwnam")
    def test_drop_privileges_nonexistent_user(self, mock_getpwnam, mock_getuid):
        # Setup: process is root
        mock_getuid.return_value = 0
        
        # Setup: user does not exist
        mock_getpwnam.side_effect = KeyError("user not found")
        
        # Act & Assert
        with self.assertRaises(ValueError):
            drop_privileges("nonexistent_user")

if __name__ == '__main__':
    unittest.main()
