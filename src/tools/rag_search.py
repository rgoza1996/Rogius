"""
RAG Search Module for Rogius Agents

Local semantic document search using LlamaIndex + Ollama embeddings.
Provides zero-cost RAG by using local embedding models via Ollama.
"""

import json
import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import aiohttp


@dataclass
class RAGResult:
    """Single RAG search result."""
    content: str          # Retrieved text chunk
    source: str           # File path or source identifier
    score: float          # Similarity score (0-1)
    metadata: Dict[str, Any]  # Additional context (line numbers, file type, etc.)


class RAGSearchClient:
    """
    Client for local RAG operations using ChromaDB + local embeddings.
    
    Supports both Ollama and LM Studio (OpenAI-compatible) embedding APIs.
    Provides zero-cost RAG using local embedding models.
    """
    
    def __init__(
        self,
        collection_name: str = "rogius_default",
        embedding_model: str = "bge-m3",
        embedding_endpoint: str = "http://localhost:11434",
        persist_dir: Optional[Path] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        api_type: str = "auto"  # "auto", "ollama", or "openai"
    ):
        """
        Initialize RAG search client.
        
        Args:
            collection_name: ChromaDB collection name for documents
            embedding_model: Model name for embeddings (bge-m3, nomic-embed-text, etc.)
            embedding_endpoint: Embedding API endpoint (Ollama or OpenAI-compatible)
            persist_dir: Directory to persist ChromaDB data
            chunk_size: Size of text chunks for indexing
            chunk_overlap: Overlap between chunks for continuity
            api_type: "ollama" for Ollama, "openai" for LM Studio/compatible, "auto" to detect
        """
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.embedding_endpoint = embedding_endpoint.rstrip('/')
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.persist_dir = persist_dir or Path.home() / ".rogius" / "vector_store"
        self.api_type = api_type
        
        # Auto-detect API type based on endpoint
        if self.api_type == "auto":
            self.api_type = self._detect_api_type()
        
        # Initialize ChromaDB
        self._init_vector_store()
    
    def _detect_api_type(self) -> str:
        """Detect whether endpoint is Ollama or OpenAI-compatible."""
        # Ollama default port is 11434
        # LM Studio and similar typically use ports like 1234, 8080, etc.
        if ":11434" in self.embedding_endpoint or "/api/embeddings" in self.embedding_endpoint:
            return "ollama"
        return "openai"
        
    def _init_vector_store(self):
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=str(self.persist_dir))
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
        except ImportError:
            raise ImportError(
                "ChromaDB not installed. Install with: pip install chromadb"
            )
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector using local API (Ollama or OpenAI-compatible).
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        if self.api_type == "ollama":
            return await self._generate_embedding_ollama(text)
        else:
            return await self._generate_embedding_openai(text)
    
    async def _generate_embedding_ollama(self, text: str) -> List[float]:
        """Generate embedding using Ollama API."""
        url = f"{self.embedding_endpoint}/api/embeddings"
        
        payload = {
            "model": self.embedding_model,
            "prompt": text
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"Ollama embedding failed: {error_text}")
                    
                    data = await response.json()
                    return data.get("embedding", [])
        except aiohttp.ClientError as e:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.embedding_endpoint}. "
                f"Make sure Ollama is running. Error: {e}"
            )
    
    async def _generate_embedding_openai(self, text: str) -> List[float]:
        """Generate embedding using OpenAI-compatible API (LM Studio, etc.)."""
        url = f"{self.embedding_endpoint}/v1/embeddings"
        
        payload = {
            "input": text,
            "model": self.embedding_model
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"Embedding API failed: {error_text}")
                    
                    data = await response.json()
                    # OpenAI format: data[0].embedding
                    if "data" in data and len(data["data"]) > 0:
                        return data["data"][0].get("embedding", [])
                    return []
        except aiohttp.ClientError as e:
            raise RuntimeError(
                f"Cannot connect to embedding API at {self.embedding_endpoint}. "
                f"Make sure LM Studio or compatible server is running. Error: {e}"
            )
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RAGResult]:
        """
        Perform semantic search over indexed documents.
        
        Args:
            query: Natural language query
            top_k: Number of results to return
            filters: Optional metadata filters (e.g., {"file_type": ".py"})
            
        Returns:
            List of RAGResult with content and metadata
        """
        # Generate query embedding
        query_embedding = await self._generate_embedding(query)
        
        if not query_embedding:
            return []
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters
        )
        
        # Format results
        rag_results = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else 0
                
                # Convert distance to similarity score (cosine distance -> similarity)
                score = 1.0 - distance
                
                rag_results.append(RAGResult(
                    content=doc,
                    source=metadata.get('source', 'unknown'),
                    score=score,
                    metadata=metadata
                ))
        
        return rag_results
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Try to end at a sentence or word boundary
            if end < len(text):
                # Look for sentence ending
                for char in ['. ', '! ', '? ', '\n']:
                    pos = text.rfind(char, start, end)
                    if pos != -1:
                        end = pos + 1
                        break
                else:
                    # Fall back to word boundary
                    pos = text.rfind(' ', start, end)
                    if pos != -1:
                        end = pos
            
            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap
            
            # Ensure we make progress
            if start >= end:
                start = end
        
        return chunks
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of file for change detection."""
        try:
            content = file_path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return ""
    
    async def index_file(
        self, 
        file_path: Path,
        file_type: Optional[str] = None
    ) -> bool:
        """
        Index a single file into the vector store.
        
        Args:
            file_path: Path to file to index
            file_type: Optional file type override
            
        Returns:
            True if indexed successfully, False otherwise
        """
        try:
            if not file_path.exists():
                return False
            
            # Read file content
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            if not content.strip():
                return False
            
            # Compute file hash for change detection
            file_hash = self._compute_file_hash(file_path)
            
            # Check if already indexed with same hash
            existing = self.collection.get(
                where={"source": str(file_path), "hash": file_hash}
            )
            if existing['ids']:
                # File unchanged, skip
                return True
            
            # Remove old entries for this file (if any)
            old_entries = self.collection.get(
                where={"source": str(file_path)}
            )
            if old_entries['ids']:
                self.collection.delete(ids=old_entries['ids'])
            
            # Chunk the content
            chunks = self._chunk_text(content)
            
            if not chunks:
                return False
            
            # Generate embeddings and index
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_path}:{i}"
                
                # Generate embedding
                embedding = await self._generate_embedding(chunk)
                
                if not embedding:
                    continue
                
                ids.append(chunk_id)
                documents.append(chunk)
                embeddings.append(embedding)
                metadatas.append({
                    "source": str(file_path),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "file_type": file_type or file_path.suffix,
                    "hash": file_hash,
                    "indexed_at": datetime.now().isoformat()
                })
            
            if ids:
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas
                )
            
            return True
            
        except Exception as e:
            print(f"[RAG] Error indexing {file_path}: {e}")
            return False
    
    async def index_directory(
        self,
        directory: Path,
        glob_pattern: str = "**/*",
        exclude_patterns: Optional[List[str]] = None,
        file_types: Optional[List[str]] = None
    ) -> int:
        """
        Index all files matching pattern in directory.
        
        Args:
            directory: Root directory to scan
            glob_pattern: File pattern (e.g., "**/*.py", "**/*.md")
            exclude_patterns: Patterns to exclude (e.g., ["**/node_modules/**"])
            file_types: Optional list of file extensions to index (e.g., [".py", ".md"])
            
        Returns:
            Number of files successfully indexed
        """
        if exclude_patterns is None:
            exclude_patterns = [
                "**/node_modules/**",
                "**/.git/**",
                "**/__pycache__/**",
                "**/dist/**",
                "**/build/**",
                "**/.next/**",
                "**/.rogius/**",
                "**/vector_store/**",
                "**/*.pyc",
                "**/*.pyo"
            ]
        
        indexed_count = 0
        
        try:
            # Find all matching files
            all_files = list(directory.glob(glob_pattern))
            
            for file_path in all_files:
                if not file_path.is_file():
                    continue
                
                # Check exclusion patterns
                excluded = False
                for pattern in exclude_patterns:
                    if file_path.match(pattern):
                        excluded = True
                        break
                
                if excluded:
                    continue
                
                # Check file type filter
                if file_types and file_path.suffix not in file_types:
                    continue
                
                # Index the file
                success = await self.index_file(file_path)
                if success:
                    indexed_count += 1
                    
        except Exception as e:
            print(f"[RAG] Error indexing directory {directory}: {e}")
        
        return indexed_count
    
    async def index_chat_message(
        self,
        role: str,
        content: str,
        session_id: str,
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Index a chat message for persistent memory.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            session_id: Chat session identifier
            timestamp: Optional Unix timestamp
            
        Returns:
            True if indexed successfully
        """
        try:
            # Create a composite text for embedding
            text = f"[{role}] {content}"
            
            # Generate embedding
            embedding = await self._generate_embedding(text)
            
            if not embedding:
                return False
            
            # Create unique ID
            ts = timestamp or datetime.now().timestamp()
            msg_id = f"chat:{session_id}:{int(ts)}:{hashlib.md5(content.encode()).hexdigest()[:8]}"
            
            # Index in the same collection (tagged as chat)
            self.collection.add(
                ids=[msg_id],
                documents=[content],  # Store just the content, not the role prefix
                embeddings=[embedding],
                metadatas=[{
                    "source": f"chat:{session_id}",
                    "role": role,
                    "session_id": session_id,
                    "timestamp": ts,
                    "type": "chat_message",
                    "indexed_at": datetime.now().isoformat()
                }]
            )
            
            return True
            
        except Exception as e:
            print(f"[RAG] Error indexing chat message: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Return index statistics.
        
        Returns:
            Dict with count, last updated, etc.
        """
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "collection_name": self.collection_name,
                "embedding_model": self.embedding_model,
                "persist_dir": str(self.persist_dir)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def clear_collection(self):
        """Clear all documents from the collection."""
        try:
            self.collection.delete(where={})
        except Exception as e:
            print(f"[RAG] Error clearing collection: {e}")


# Convenience function for direct use
async def rag_search(
    query: str,
    top_k: int = 5,
    collection_name: str = "rogius_default"
) -> List[RAGResult]:
    """
    Convenience function for quick RAG searches.
    
    Args:
        query: Search query
        top_k: Number of results
        collection_name: ChromaDB collection to search
        
    Returns:
        List of RAGResult
    """
    client = RAGSearchClient(collection_name=collection_name)
    return await client.search(query, top_k=top_k)
