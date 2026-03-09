import os
import pwd
import grp
import logging

logger = logging.getLogger(__name__)

def drop_privileges(user_name="nobody"):
    """
    Drops privileges to the specified user and their primary group.
    """
    if os.getuid() != 0:
        logger.info("Process is not running as root. Skipping privilege drop.")
        return

    try:
        # Get the UID and GID for the user
        user_info = pwd.getpwnam(user_name)
        uid = user_info.pw_uid
        gid = user_info.pw_gid

        # Set the group ID
        os.setgroups([])  # Clear supplementary groups
        os.setgid(gid)
        os.setuid(uid)

        # Set environment variables for the new user
        os.environ['HOME'] = user_info.pw_dir
        os.environ['USER'] = user_name
        
        logger.info(f"Successfully dropped privileges to user: {user_name} (uid={uid}, gid={gid})")
    except KeyError:
        raise ValueError(f"User '{user_name}' does not exist on the system.")
    except Exception as e:
        raise RuntimeError(f"Failed to drop privileges: {e}")

def check_is_root():
    """
    Checks if the current process is running as root.
    """
    return os.getuid() == 0
