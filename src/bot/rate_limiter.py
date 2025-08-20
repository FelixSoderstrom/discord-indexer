import asyncio
import time
import logging
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass
from collections import deque
import discord


@dataclass
class RateLimitInfo:
    """Information about Discord's rate limits."""

    limit: int
    remaining: int
    reset_after: float
    retry_after: Optional[float] = None


class DiscordRateLimiter:
    """
    Rate limiter for Discord API calls that supports parallel processing.

    Handles Discord's rate limits (50 requests per second) while allowing
    unlimited parallel processing of fetched data. Provides both synchronous
    and asynchronous rate limiting with automatic retry logic.
    """

    def __init__(
        self,
        max_requests_per_second: int = 50,
        burst_limit: int = 100,
        retry_delay: float = 1.0,
        max_retries: int = 3,
    ):
        self.max_requests_per_second = max_requests_per_second
        self.burst_limit = burst_limit
        self.retry_delay = retry_delay
        self.max_retries = max_retries

        # Rate limiting state
        self.request_times = deque(maxlen=burst_limit)
        self.current_requests = 0
        self.last_reset = time.time()

        # Rate limit info from Discord responses
        self.rate_limit_info: Optional[RateLimitInfo] = None

        # Logging
        self.logger = logging.getLogger(__name__)

        # Semaphore for controlling concurrent requests
        self.request_semaphore = asyncio.Semaphore(max_requests_per_second)

    async def acquire(self) -> None:
        """
        Acquire permission to make a Discord API request.

        Waits if necessary to respect rate limits.
        """
        await self.request_semaphore.acquire()

        now = time.time()

        # Check if we need to wait due to rate limiting
        if (
            self.request_times
            and len(self.request_times) >= self.max_requests_per_second
        ):
            oldest_request = self.request_times[0]
            time_since_oldest = now - oldest_request

            if time_since_oldest < 1.0:
                wait_time = 1.0 - time_since_oldest
                self.logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

        # Record this request
        self.request_times.append(now)
        self.current_requests += 1

    def release(self) -> None:
        """Release the request semaphore after API call completes."""
        self.request_semaphore.release()
        self.current_requests = max(0, self.current_requests - 1)

    async def execute_with_rate_limit(
        self, api_call: Callable[[], Awaitable[Any]]
    ) -> Any:
        """
        Execute an API call with automatic rate limiting.

        Args:
            api_call: Async function that makes Discord API call

        Returns:
            Result of the API call

        Raises:
            discord.HTTPException: If rate limit exceeded and max retries reached
        """
        for attempt in range(self.max_retries + 1):
            try:
                await self.acquire()

                try:
                    result = await api_call()
                    return result
                finally:
                    self.release()

            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = (
                        e.retry_after if hasattr(e, "retry_after") else self.retry_delay
                    )

                    if attempt < self.max_retries:
                        self.logger.warning(
                            f"Rate limited, retrying in {retry_after}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        self.logger.error(
                            f"Max retries reached for rate limited request"
                        )
                        raise
                else:
                    raise

        raise RuntimeError("Unexpected retry loop exit")

    async def batch_fetch_messages(
        self,
        channels: List[discord.TextChannel],
        messages_per_channel: int = 100,
        max_concurrent_channels: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Fetch messages from multiple channels with rate limiting and parallel processing.

        This method demonstrates the recommended approach:
        1. Rate-limited fetching (respects Discord limits)
        2. Parallel processing of fetched data (unlimited)

        Args:
            channels: List of Discord text channels to fetch from
            messages_per_channel: Maximum messages to fetch per channel
            max_concurrent_channels: Maximum channels to fetch from simultaneously

        Returns:
            List of all fetched message data
        """
        self.logger.info(f"Starting batch fetch from {len(channels)} channels")

        # Create semaphore to limit concurrent channel fetching
        channel_semaphore = asyncio.Semaphore(max_concurrent_channels)

        async def fetch_channel_messages(
            channel: discord.TextChannel,
        ) -> List[Dict[str, Any]]:
            """Fetch messages from a single channel with rate limiting."""
            async with channel_semaphore:
                self.logger.debug(f"Fetching messages from #{channel.name}")

                async def api_call():
                    messages = []
                    async for message in channel.history(
                        limit=messages_per_channel, oldest_first=True
                    ):
                        messages.append(message)
                    return messages

                # Execute with rate limiting
                messages = await self.execute_with_rate_limit(api_call)

                # Process messages (this can be unlimited - no rate limiting needed)
                processed_messages = []
                for message in messages:
                    message_data = self._extract_message_data(message)
                    processed_messages.append(message_data)

                self.logger.info(
                    f"Fetched and processed {len(processed_messages)} messages from #{channel.name}"
                )
                return processed_messages

        # Fetch from all channels with controlled concurrency
        tasks = [fetch_channel_messages(channel) for channel in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results and handle any errors
        all_messages = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(
                    f"Error fetching from channel {channels[i].name}: {result}"
                )
            else:
                all_messages.extend(result)

        self.logger.info(f"Batch fetch complete: {len(all_messages)} total messages")
        return all_messages

    def _extract_message_data(self, message: discord.Message) -> Dict[str, Any]:
        """
        Extract relevant data from a Discord message.

        This is a copy of the method from DiscordBot for consistency.
        """
        guild_id = message.guild.id if message.guild else None
        guild_name = message.guild.name if message.guild else None

        return {
            "id": message.id,
            "content": message.content,
            "author": {
                "id": message.author.id,
                "name": message.author.name,
                "display_name": message.author.display_name,
            },
            "channel": {"id": message.channel.id, "name": message.channel.name},
            "guild": {"id": guild_id, "name": guild_name},
            "timestamp": message.created_at.isoformat(),
            "attachments": [att.url for att in message.attachments],
            "has_embeds": len(message.embeds) > 0,
            "message_type": str(message.type),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status for monitoring."""
        return {
            "current_requests": self.current_requests,
            "max_requests_per_second": self.max_requests_per_second,
            "request_queue_size": len(self.request_times),
            "last_reset": self.last_reset,
            "rate_limit_info": self.rate_limit_info,
        }

    async def reset(self) -> None:
        """Reset the rate limiter state."""
        self.request_times.clear()
        self.current_requests = 0
        self.last_reset = time.time()
        self.rate_limit_info = None
        self.logger.info("Rate limiter reset")
