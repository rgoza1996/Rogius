"""
Renamer Agent for Rogius

Automatically generates AI titles for chats with >5 user prompts.
Processes queue oldest-to-newest when inference engine is idle.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# Note: ai_client is in tui folder - adjust import path as needed
from tui.ai_client import ChatMessage


@dataclass
class RenamerState:
    """State for the Renamer agent."""
    queue: list[str] = field(default_factory=list)  # chat IDs in order (oldest first)
    processing: bool = False
    last_processed: Optional[str] = None
    streaming_active: bool = False
    current_chat_id: Optional[str] = None


class RenamerAgent:
    """
    Agent that monitors chats and generates AI titles when:
    1. Chat has >= 5 user prompts (and multiples of 5)
    2. Inference engine is not streaming
    3. Chat is eligible (not user-titled)
    """

    def __init__(self, ai_client, storage_dir: Path):
        """
        Initialize the RenamerAgent.

        Args:
            ai_client: AIClient instance for generating titles
            storage_dir: Path to chat storage directory
        """
        self.ai_client = ai_client
        self.storage_dir = storage_dir
        self.state = RenamerState()
        self._processing_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def set_streaming_state(self, is_streaming: bool):
        """Update streaming state - called when chat streaming starts/stops."""
        self.state.streaming_active = is_streaming

    def enqueue_chat(self, chat_id: str) -> bool:
        """
        Add chat to renamer queue if not already present.
        Returns True if added, False if already in queue.
        """
        if chat_id not in self.state.queue:
            self.state.queue.append(chat_id)
            print(f"[Renamer] Enqueued chat: {chat_id}")
            return True
        return False

    def dequeue_chat(self, chat_id: str) -> bool:
        """
        Remove chat from renamer queue (e.g., when user manually titles).
        Returns True if removed, False if not in queue.
        """
        if chat_id in self.state.queue:
            self.state.queue.remove(chat_id)
            print(f"[Renamer] Dequeued chat: {chat_id}")
            return True
        return False

    def get_queue(self) -> list[str]:
        """Get current queue of chat IDs."""
        return self.state.queue.copy()

    def get_status(self) -> dict:
        """Get current renamer status."""
        return {
            "queue_length": len(self.state.queue),
            "processing": self.state.processing,
            "streaming_active": self.state.streaming_active,
            "last_processed": self.state.last_processed,
            "current_chat": self.state.current_chat_id,
            "queue": self.state.queue
        }

    def _load_chat(self, chat_id: str) -> Optional[dict]:
        """Load a chat file from storage."""
        chat_file = self.storage_dir / f"{chat_id}.json"
        if not chat_file.exists():
            return None
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Renamer] Error loading chat {chat_id}: {e}")
            return None

    def _save_chat(self, chat: dict) -> bool:
        """Save a chat file to storage."""
        chat_file = self.storage_dir / f"{chat['id']}.json"
        try:
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(chat, f, indent=2)
            return True
        except Exception as e:
            print(f"[Renamer] Error saving chat {chat['id']}: {e}")
            return False

    def _update_chat_index(self, chat_id: str, title: str) -> bool:
        """Update the chat index file with new title."""
        index_file = self.storage_dir / "index.json"
        if not index_file.exists():
            return False
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)

            for entry in index:
                if entry["id"] == chat_id:
                    entry["title"] = title
                    entry["updatedAt"] = int(datetime.now().timestamp() * 1000)
                    break

            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2)
            return True
        except Exception as e:
            print(f"[Renamer] Error updating index for {chat_id}: {e}")
            return False

    async def _generate_title(self, messages: list[dict]) -> Optional[str]:
        """
        Generate an AI title from conversation messages.
        Uses the same logic as generateAITitle() in chat-storage.ts.
        """
        if not messages:
            return None

        # Get last few messages for context (up to 4 messages to save tokens)
        context = messages[-4:]
        conversation = []
        for m in context:
            role = "User" if m.get("role") == "user" else "AI"
            content = m.get("content", "")[:200]
            if len(m.get("content", "")) > 200:
                content += "..."
            conversation.append(f"{role}: {content}")

        conv_text = '\n\n'.join(conversation)
        prompt_text = f"""Based on the following conversation, generate a concise 2-5 word title that captures the main topic. The title should be descriptive but brief. Respond with ONLY the title, nothing else.

Conversation:
{conv_text}

Title:"""

        try:
            chat_messages = [
                ChatMessage(role="system", content="You are a helpful assistant that generates short, descriptive titles for conversations."),
                ChatMessage(role="user", content=prompt_text)
            ]

            content_parts = []
            async for chunk in self.ai_client.stream_chat_completion(chat_messages, enable_tools=False):
                if chunk.content:
                    content_parts.append(chunk.content)

            full_content = "".join(content_parts).strip()

            if full_content:
                # Clean up title (remove quotes, limit length)
                cleaned = full_content.replace('"', '').replace("'", "").strip()
                cleaned = cleaned.split('\n')[0]  # Take first line only
                cleaned = cleaned[:50]  # Limit to 50 chars
                return cleaned if cleaned else None

            return None

        except Exception as e:
            print(f"[Renamer] Error generating title: {e}")
            return None

    async def process_chat(self, chat_id: str) -> bool:
        """
        Process a single chat - generate title and save.
        Returns True if successful, False otherwise.
        """
        print(f"[Renamer] Processing chat: {chat_id}")

        chat = self._load_chat(chat_id)
        if not chat:
            return False

        # Skip if user has manually titled this chat
        if chat.get("userTitled"):
            print(f"[Renamer] Skipping user-titled chat: {chat_id}")
            return False

        messages = chat.get("messages", [])
        if not messages:
            return False

        # Generate title
        title = await self._generate_title(messages)
        if not title:
            print(f"[Renamer] Failed to generate title for: {chat_id}")
            return False

        # Update chat
        chat["title"] = title
        chat["updatedAt"] = int(datetime.now().timestamp() * 1000)

        if self._save_chat(chat) and self._update_chat_index(chat_id, title):
            print(f"[Renamer] Renamed chat '{chat_id}' to: '{title}'")
            self.state.last_processed = chat_id
            return True

        return False

    async def process_next(self) -> Optional[str]:
        """
        Process next chat in queue if streaming is not active.
        Returns chat_id if processed, None if skipped or empty.
        """
        if not self.state.queue:
            return None

        if self.state.streaming_active:
            print("[Renamer] Skipping - streaming is active")
            return None

        # Find first eligible chat in queue
        for chat_id in self.state.queue[:]:
            chat = self._load_chat(chat_id)
            if chat and not chat.get("userTitled"):
                self.state.current_chat_id = chat_id
                self.state.processing = True

                try:
                    success = await self.process_chat(chat_id)
                    if success:
                        self.state.queue.remove(chat_id)
                        return chat_id
                finally:
                    self.state.processing = False
                    self.state.current_chat_id = None

            else:
                # Remove ineligible chats from queue
                self.state.queue.remove(chat_id)

        return None

    async def start_background_processor(self, interval_seconds: float = 5.0):
        """
        Start background processing loop.
        Checks queue every interval_seconds when not streaming.
        """
        print(f"[Renamer] Starting background processor (interval: {interval_seconds}s)")

        while not self._stop_event.is_set():
            try:
                if self.state.queue and not self.state.streaming_active:
                    await self.process_next()
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[Renamer] Error in background processor: {e}")
                await asyncio.sleep(interval_seconds)

    def stop_background_processor(self):
        """Stop the background processing loop."""
        print("[Renamer] Stopping background processor")
        self._stop_event.set()
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()

    def start(self, interval_seconds: float = 5.0):
        """Start the background processor as a task."""
        self._stop_event.clear()
        self._processing_task = asyncio.create_task(
            self.start_background_processor(interval_seconds)
        )
