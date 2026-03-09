import asyncio
import logging
import sys
from src.gbot.config import load_config
from src.gbot.privileges import drop_privileges, check_is_root
from src.gbot.mcp_client import GmonClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("gbot")

class GbotApp:
    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        self.gmon = GmonClient(self.config.gmon_path)

    async def run(self):
        logger.info("Starting gbot...")
        
        # 1. Start gmon while still having root privileges (if running as root)
        # Note: In our current GmonClient implementation, it starts the process
        # during connect().
        logger.info("Initializing gmon connection (Root context)...")
        await self.gmon.connect()
        
        # Verify connectivity
        pong = await self.gmon.call_ping("initialization")
        logger.info(f"gmon responded: {pong}")

        # 2. Drop privileges
        target_user = self.config.drop_to_user
        logger.info(f"Dropping privileges to {target_user}...")
        drop_privileges(target_user)

        # 3. Running as normal user now
        logger.info("gbot is now running as a normal user. Starting main loop...")
        
        try:
            # Here we would initialize Google Chat, Gmail, etc.
            # For Phase 1, we'll just keep it alive.
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Shutting down...")
        finally:
            await self.gmon.disconnect()

async def main():
    app = GbotApp()
    try:
        await app.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
