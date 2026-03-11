import asyncio
import logging
import sys
import argparse
from gbot.config import load_config
from gbot.mcp_client import GmonClient
from gbot.mcp_mock import MockGmonClient
from gbot.brain import GeminiBrain
from gbot.scheduler import GbotScheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - gbot - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

class GbotApp:
    def __init__(self, is_test=False):
        self.config = load_config()
        self.is_test = is_test
        
        # Initialize Gmon Client (Mocked if in test mode)
        if self.is_test:
            self.gmon = MockGmonClient()
        else:
            self.gmon = GmonClient()
            
        # Initialize Brain
        self.brain = GeminiBrain(self.config)
        
        # Initialize Channels (Dynamic imports to avoid ModuleNotFoundError in test environments)
        if not self.is_test:
            from gbot.channels.zoho_cliq import ZohoCliqChannel
            from gbot.calendar_sync import CalendarSync
            from gbot.zoho_auth import ZohoAuth
            
            self.auth = ZohoAuth(self.config)
            self.chat = ZohoCliqChannel(self.config, self.brain.query, auth=self.auth)
            self.scheduler = GbotScheduler(self.config, self.gmon, self.chat)
            self.calendar = CalendarSync(self.config, self.scheduler, auth=self.auth)
        else:
            # For integration testing with real APIs in test mode
            from gbot.channels.zoho_cliq import ZohoCliqChannel
            from gbot.zoho_auth import ZohoAuth
            
            self.auth = ZohoAuth(self.config)
            self.chat = ZohoCliqChannel(self.config, self.brain.query, auth=self.auth)
            self.scheduler = GbotScheduler(self.config, self.gmon, self.chat)
            
            # For calendar we still use a mock in test mode unless specifically needed
            self.calendar = MagicMockAsync()

    async def run(self):
        logger.info(f"Starting gbot (Test Mode: {self.is_test})")
        
        # 1. Connect to gmon
        try:
            await self.gmon.connect()
            logger.info("Connected to gmon.")
        except Exception as e:
            if not self.is_test:
                logger.error(f"Failed to connect to gmon: {e}")
                return
            logger.warning(f"Gmon connection failed, but continuing in test mode: {e}")

        # 2. Start background tasks
        tasks = [
            asyncio.create_task(self.scheduler.run_loop()),
            asyncio.create_task(self.calendar.run_loop() if not self.is_test else self.calendar.mock_loop()),
            asyncio.create_task(self.chat.run_server(run_once=self.is_test))
        ]
        
        logger.info("gbot is now fully operational.")
        
        if self.is_test:
            # In test mode, we run until one message is processed or timeout
            logger.info("Test mode: Waiting for one message or 60s timeout...")
            try:
                # FIRST_COMPLETED will fire when one of the pollers returns after one message
                done, pending = await asyncio.wait(tasks, timeout=60, return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    logger.warning("Test mode timed out without processing any message.")
            except Exception as e:
                logger.error(f"Error during test execution: {e}")
            
            for task in tasks:
                task.cancel()
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Shutdown requested.")
        finally:
            await self.gmon.disconnect()

class MagicMockAsync:
    """A minimal mock that allows calling methods and awaiting them."""
    def __getattr__(self, name):
        async def mock_coro(*args, **kwargs):
            return None
        return mock_coro
    async def mock_loop(self):
        while True: await asyncio.sleep(3600)

async def main():
    parser = argparse.ArgumentParser(description="gbot Intelligent Gateway")
    parser.add_argument("-test", action="store_true", help="Run in test mode with mocked MCP")
    args = parser.parse_args()

    app = GbotApp(is_test=args.test)
    try:
        await app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
