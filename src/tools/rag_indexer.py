"""
Background Indexer for Project Files

Watches project directories and incrementally updates the RAG vector store.
Provides automatic indexing with file watching for real-time updates.
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Set, Callable
from dataclasses import dataclass
from datetime import datetime

from .rag_search import RAGSearchClient


@dataclass
class IndexConfig:
    """Configuration for project indexing."""
    # File patterns to index
    include_patterns: List[str] = None
    # Patterns to exclude
    exclude_patterns: List[str] = None
    # File extensions to index
    file_extensions: List[str] = None
    # Auto-index on startup
    auto_index: bool = True
    # Enable file watching
    enable_watching: bool = False
    # Debounce time for file changes (seconds)
    debounce_seconds: float = 2.0


def _default_config() -> IndexConfig:
    """Return default indexing configuration."""
    return IndexConfig(
        include_patterns=["**/*"],
        exclude_patterns=[
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/dist/**",
            "**/build/**",
            "**/.next/**",
            "**/.rogius/**",
            "**/vector_store/**",
            "**/.venv/**",
            "**/venv/**",
            "**/*.pyc",
            "**/*.pyo",
            "**/*.so",
            "**/*.dll",
            "**/*.dylib",
            "**/package-lock.json",
            "**/yarn.lock",
            "**/Cargo.lock",
            "**/poetry.lock"
        ],
        file_extensions=[
            ".py", ".ts", ".tsx", ".js", ".jsx",
            ".md", ".mdx", ".txt",
            ".yaml", ".yml", ".json",
            ".toml", ".cfg", ".ini",
            ".rs", ".go", ".java", ".c", ".cpp", ".h",
            ".rb", ".php", ".swift", ".kt"
        ],
        auto_index=True,
        enable_watching=False,  # Disabled by default to avoid resource usage
        debounce_seconds=2.0
    )


class ProjectIndexer:
    """
    Indexes project files in background with optional file watching.
    
    Usage:
        indexer = ProjectIndexer(
            rag_client=RAGSearchClient(),
            project_root=Path("/path/to/project")
        )
        
        # Initial index
        stats = await indexer.initial_index()
        
        # Start watching (optional)
        indexer.start_watching()
    """
    
    def __init__(
        self,
        rag_client: RAGSearchClient,
        project_root: Path,
        config: Optional[IndexConfig] = None
    ):
        """
        Initialize project indexer.
        
        Args:
            rag_client: RAGSearchClient instance
            project_root: Root directory of the project
            config: Optional IndexConfig (uses defaults if not provided)
        """
        self.rag_client = rag_client
        self.project_root = Path(project_root).resolve()
        self.config = config or _default_config()
        
        # Track indexed files
        self.indexed_files: Set[Path] = set()
        self.last_indexed: Optional[datetime] = None
        
        # File watcher (if enabled)
        self._observer = None
        self._pending_updates: Set[Path] = set()
        self._debounce_task: Optional[asyncio.Task] = None
    
    async def initial_index(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> dict:
        """
        Perform initial full index of project.
        
        Args:
            progress_callback: Optional callback(current, total) for progress updates
            
        Returns:
            Dict with indexing statistics
        """
        print(f"[Indexer] Starting initial index of {self.project_root}")
        
        # Find all files to index
        files_to_index = self._collect_files()
        total_files = len(files_to_index)
        
        print(f"[Indexer] Found {total_files} files to index")
        
        indexed = 0
        failed = 0
        skipped = 0
        
        for i, file_path in enumerate(files_to_index, 1):
            try:
                # Report progress
                if progress_callback:
                    progress_callback(i, total_files)
                
                # Index the file
                success = await self.rag_client.index_file(file_path)
                
                if success:
                    self.indexed_files.add(file_path)
                    indexed += 1
                else:
                    skipped += 1
                    
            except Exception as e:
                print(f"[Indexer] Failed to index {file_path}: {e}")
                failed += 1
            
            # Small yield to prevent blocking
            if i % 10 == 0:
                await asyncio.sleep(0.01)
        
        self.last_indexed = datetime.now()
        
        stats = {
            "total_files": total_files,
            "indexed": indexed,
            "failed": failed,
            "skipped": skipped,
            "last_indexed": self.last_indexed.isoformat()
        }
        
        print(f"[Indexer] Complete: {indexed} indexed, {failed} failed, {skipped} skipped")
        
        return stats
    
    def _collect_files(self) -> List[Path]:
        """
        Collect all files matching configuration.
        
        Returns:
            List of Path objects to index
        """
        files: List[Path] = []
        
        # Use the first include pattern (usually "**/*")
        pattern = self.config.include_patterns[0] if self.config.include_patterns else "**/*"
        
        for file_path in self.project_root.glob(pattern):
            if not file_path.is_file():
                continue
            
            # Check exclusion patterns
            excluded = False
            for exclude_pattern in self.config.exclude_patterns:
                if file_path.match(exclude_pattern):
                    excluded = True
                    break
            
            if excluded:
                continue
            
            # Check file extension
            if self.config.file_extensions:
                if file_path.suffix not in self.config.file_extensions:
                    continue
            
            files.append(file_path)
        
        return files
    
    async def reindex_file(self, file_path: Path) -> bool:
        """
        Reindex a single file (useful for updates).
        
        Args:
            file_path: Path to file
            
        Returns:
            True if indexed successfully
        """
        # Ensure path is within project
        file_path = Path(file_path).resolve()
        if not str(file_path).startswith(str(self.project_root)):
            return False
        
        success = await self.rag_client.index_file(file_path)
        
        if success:
            self.indexed_files.add(file_path)
        
        return success
    
    def start_watching(self):
        """
        Start file system watcher for incremental updates.
        
        Note: Requires watchdog package. Disabled by default.
        """
        if not self.config.enable_watching:
            return
        
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
            
            class RAGEventHandler(FileSystemEventHandler):
                def __init__(self, indexer: 'ProjectIndexer'):
                    self.indexer = indexer
                
                def on_modified(self, event):
                    if isinstance(event, FileModifiedEvent) and not event.is_directory:
                        self.indexer._on_file_change(Path(event.src_path))
                
                def on_created(self, event):
                    if isinstance(event, FileCreatedEvent) and not event.is_directory:
                        self.indexer._on_file_change(Path(event.src_path))
            
            self._observer = Observer()
            handler = RAGEventHandler(self)
            self._observer.schedule(handler, str(self.project_root), recursive=True)
            self._observer.start()
            
            print(f"[Indexer] File watching started for {self.project_root}")
            
        except ImportError:
            print("[Indexer] Warning: watchdog not installed. File watching disabled.")
            print("[Indexer] Install with: pip install watchdog")
    
    def stop_watching(self):
        """Stop file system watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            print("[Indexer] File watching stopped")
    
    def _on_file_change(self, file_path: Path):
        """
        Handle file change event (internal).
        
        Args:
            file_path: Path that changed
        """
        # Check if file should be indexed
        if file_path.suffix not in (self.config.file_extensions or []):
            return
        
        # Check exclusions
        for exclude_pattern in self.config.exclude_patterns:
            if file_path.match(exclude_pattern):
                return
        
        # Add to pending updates
        self._pending_updates.add(file_path)
        
        # Debounce: schedule update after delay
        if self._debounce_task:
            self._debounce_task.cancel()
        
        self._debounce_task = asyncio.create_task(
            self._debounced_update()
        )
    
    async def _debounced_update(self):
        """Debounced update handler."""
        await asyncio.sleep(self.config.debounce_seconds)
        
        # Process all pending updates
        updates = list(self._pending_updates)
        self._pending_updates.clear()
        
        for file_path in updates:
            try:
                print(f"[Indexer] Updating: {file_path}")
                await self.reindex_file(file_path)
            except Exception as e:
                print(f"[Indexer] Error updating {file_path}: {e}")
    
    def get_stats(self) -> dict:
        """
        Get indexing statistics.
        
        Returns:
            Dict with stats
        """
        rag_stats = self.rag_client.get_stats()
        
        return {
            **rag_stats,
            "project_root": str(self.project_root),
            "indexed_files_count": len(self.indexed_files),
            "last_indexed": self.last_indexed.isoformat() if self.last_indexed else None,
            "watching_enabled": self.config.enable_watching and self._observer is not None
        }
    
    async def force_reindex(self) -> dict:
        """
        Force complete reindex of project.
        
        Returns:
            Indexing statistics
        """
        # Clear existing index
        self.rag_client.clear_collection()
        self.indexed_files.clear()
        
        # Reindex everything
        return await self.initial_index()


async def index_project(
    project_root: Path,
    collection_name: str = "rogius_default",
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> dict:
    """
    Convenience function to index a project directory.
    
    Args:
        project_root: Root directory to index
        collection_name: ChromaDB collection name
        progress_callback: Optional progress callback(current, total)
        
    Returns:
        Indexing statistics
    """
    rag_client = RAGSearchClient(collection_name=collection_name)
    indexer = ProjectIndexer(rag_client, project_root)
    
    return await indexer.initial_index(progress_callback)
