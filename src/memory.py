"""RAG-based memory system for 41Agent."""

import os
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .config import config


@dataclass
class MemoryItem:
    """A single memory item."""

    id: str
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime
    embedding: Optional[List[float]] = None


class MemoryStore:
    """RAG-based memory store using ChromaDB."""

    def __init__(self):
        self.client = chromadb.Client(
            Settings(
                persist_directory=config.chroma_db_path,
                anonymized_telemetry=False,
            )
        )
        # Ensure directory exists
        Path(config.chroma_db_path).mkdir(parents=True, exist_ok=True)

        # Create collections
        self.episodic_collection = self.client.get_or_create_collection(
            name="episodic_memory",
            metadata={"description": "Past experiences and conversations"},
        )
        self.factual_collection = self.client.get_or_create_collection(
            name="factual_memory", metadata={"description": "Facts and knowledge"}
        )
        self.procedural_collection = self.client.get_or_create_collection(
            name="procedural_memory", metadata={"description": "Skills and procedures"}
        )

        # Embedding model
        self.embedding_model = SentenceTransformer(config.embedding_model)

    async def add_memory(
        self,
        content: str,
        memory_type: str = "episodic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a memory to the store.

        Args:
            content: The memory content
            memory_type: Type of memory (episodic, factual, procedural)
            metadata: Additional metadata

        Returns:
            Memory ID
        """
        memory_id = str(uuid.uuid4())
        embedding = self.embedding_model.encode(content).tolist()

        collection = self._get_collection(memory_type)

        collection.add(
            documents=[content],
            embeddings=[embedding],
            ids=[memory_id],
            metadatas=[{"timestamp": datetime.now().isoformat(), **(metadata or {})}],
        )

        return memory_id

    async def search(
        self,
        query: str,
        memory_type: Optional[str] = None,
        n_results: int = 5,
    ) -> List[MemoryItem]:
        """Search memories.

        Args:
            query: Search query
            memory_type: Optional filter by type
            n_results: Number of results

        Returns:
            List of matching memory items
        """
        query_embedding = self.embedding_model.encode(query).tolist()

        if memory_type:
            collection = self._get_collection(memory_type)
            results = collection.query(
                query_embeddings=[query_embedding], n_results=n_results
            )
        else:
            # Search all collections
            all_results = []
            for collection_name in [
                "episodic_memory",
                "factual_memory",
                "procedural_memory",
            ]:
                collection = self.client.get_collection(collection_name)
                results = collection.query(
                    query_embeddings=[query_embedding], n_results=n_results
                )
                all_results.extend(self._parse_results(results, collection_name))

            # Sort by distance and limit
            all_results.sort(key=lambda x: x.metadata.get("distance", float("inf")))
            return all_results[:n_results]

        return self._parse_results(results, memory_type)

    async def get_recent(
        self,
        memory_type: Optional[str] = None,
        n_results: int = 10,
    ) -> List[MemoryItem]:
        """Get recent memories.

        Args:
            memory_type: Optional filter by type
            n_results: Number of results

        Returns:
            List of recent memory items
        """
        if memory_type:
            collection = self._get_collection(memory_type)
            results = collection.get(limit=n_results)
        else:
            # Get from all collections
            all_results = []
            for collection_name in [
                "episodic_memory",
                "factual_memory",
                "procedural_memory",
            ]:
                collection = self.client.get_collection(collection_name)
                results = collection.get(limit=n_results)
                all_results.extend(self._parse_results(results, collection_name))

            # Sort by timestamp and limit
            all_results.sort(key=lambda x: x.timestamp, reverse=True)
            return all_results[:n_results]

        return self._parse_results(results, memory_type)

    async def delete_memory(self, memory_id: str, memory_type: str):
        """Delete a memory.

        Args:
            memory_id: Memory ID to delete
            memory_type: Type of memory
        """
        collection = self._get_collection(memory_type)
        collection.delete(ids=[memory_id])

    def _get_collection(self, memory_type: str):
        """Get collection by type."""
        type_map = {
            "episodic": self.episodic_collection,
            "factual": self.factual_collection,
            "procedural": self.procedural_collection,
        }
        return type_map.get(memory_type, self.episodic_collection)

    def _parse_results(self, results: Dict, memory_type: str) -> List[MemoryItem]:
        """Parse ChromaDB results into MemoryItem objects."""
        items = []

        for i in range(len(results.get("ids", []))):
            items.append(
                MemoryItem(
                    id=results["ids"][i],
                    content=results["documents"][i],
                    metadata={
                        **(results.get("metadatas", [{}])[i] or {}),
                        "memory_type": memory_type,
                        "distance": results.get("distances", [[0]])[0][i]
                        if results.get("distances")
                        else 0,
                    },
                    timestamp=datetime.fromisoformat(
                        results.get("metadatas", [{}])[i].get(
                            "timestamp", datetime.now().isoformat()
                        )
                    ),
                )
            )

        return items

    async def close(self):
        """Close the database."""
        self.client.close()


class WorkingMemory:
    """Short-term working memory for current context."""

    def __init__(self, max_tokens: int = 32000):
        self.messages: List[Dict[str, Any]] = []
        self.max_tokens = max_tokens
        self.context: Dict[str, Any] = {}

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a message to working memory."""
        self.messages.append(
            {"role": role, "content": content, "metadata": metadata or {}}
        )

        # Trim old messages if needed
        self._trim_to_limit()

    def add_context(self, key: str, value: Any):
        """Add to working context."""
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get from working context."""
        return self.context.get(key, default)

    def get_messages(self, n: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent messages."""
        if n:
            return self.messages[-n:]
        return self.messages

    def clear(self):
        """Clear working memory."""
        self.messages = []
        self.context = {}

    def _trim_to_limit(self):
        """Trim messages to stay within token limit."""
        # Simple estimation: ~4 characters per token
        while len(self.messages) > 0:
            total_chars = sum(len(m["content"]) for m in self.messages)
            if total_chars > self.max_tokens * 4:
                self.messages.pop(0)
            else:
                break


class MemoryManager:
    """Complete memory management combining RAG and working memory."""

    def __init__(self):
        self.long_term = MemoryStore()
        self.working = WorkingMemory()

    async def remember(self, content: str, importance: float = 0.5) -> str:
        """Store a memory with automatic classification.

        Args:
            content: Memory content
            importance: Importance score (0-1)

        Returns:
            Memory ID
        """
        # Classify memory type based on content
        memory_type = self._classify_memory(content)

        # Add to long-term memory
        memory_id = await self.long_term.add_memory(
            content=content,
            memory_type=memory_type,
            metadata={"importance": importance},
        )

        return memory_id

    async def recall(self, query: str, n_results: int = 5) -> List[MemoryItem]:
        """Recall memories relevant to query."""
        return await self.long_term.search(query, n_results=n_results)

    async def recall_recent(self, n: int = 10) -> List[MemoryItem]:
        """Get recent memories."""
        return await self.long_term.get_recent(n_results=n)

    def add_to_working(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add to working memory."""
        self.working.add_message(role, content, metadata)

    def get_working_messages(self, n: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get working memory messages."""
        return self.working.get_messages(n)

    async def get_contextual_memory(self, query: str, n: int = 5) -> str:
        """Get contextual memory string for a query."""
        # Get recent memories
        recent = await self.recall_recent(n=n)

        # Get relevant memories
        relevant = await self.recall(query, n_results=n)

        # Combine and format
        memory_parts = []

        if recent:
            memory_parts.append("Recent memories:")
            for mem in recent[:3]:
                memory_parts.append(f"- {mem.content}")

        if relevant:
            memory_parts.append("Relevant memories:")
            for mem in relevant[:3]:
                memory_parts.append(f"- {mem.content}")

        return "\n".join(memory_parts) if memory_parts else ""

    def _classify_memory(self, content: str) -> str:
        """Classify memory type based on content."""
        content_lower = content.lower()

        # Procedural: how-to, steps, skills
        if any(
            word in content_lower
            for word in ["how to", "steps", "procedure", "method", "skill"]
        ):
            return "procedural"

        # Factual: facts, definitions, knowledge
        if any(
            word in content_lower
            for word in ["fact", "definition", "know", "remember", "information"]
        ):
            return "factual"

        # Default: episodic (experiences, conversations)
        return "episodic"

    async def close(self):
        """Close all memory stores."""
        await self.long_term.close()
