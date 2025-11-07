# core/index_manager.py
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime

from .document_processor import DocumentProcessor
from .vector_store import VectorStore
from models.config import AppConfig, DirectoryConfig


class IndexManager:
    def __init__(self, config: AppConfig, model_manager, vector_store):
        self.config = config
        self.model_manager = model_manager
        self.vector_store = vector_store
        self.document_processor = DocumentProcessor()
        self._lock = threading.Lock()
        self.is_indexing = False

    def add_directory(self, directory_path: str, config: DirectoryConfig = None) -> bool:
        """添加目录到管理"""
        path = Path(directory_path).resolve()
        if not path.exists() or not path.is_dir():
            return False
            
        if config is None:
            config = DirectoryConfig(path=str(path))
            
        with self._lock:
            self.config.directories[str(path)] = config
            self.config.save()
            
        return True

    def remove_directory(self, directory_path: str) -> bool:
        """移除目录"""
        path = str(Path(directory_path).resolve())
        
        with self._lock:
            if path in self.config.directories:
                # 删除对应的向量集合
                config = self.config.directories[path]
                self.vector_store.delete_collection(config.collection_name)
                
                del self.config.directories[path]
                self.config.save()
                return True
                
        return False

    def index_directory(self, directory_path: str, rebuild: bool = False) -> Dict[str, Any]:
        """索引单个目录"""
        if self.is_indexing:
            return {"success": False, "message": "正在索引其他目录，请稍后"}
            
        self.is_indexing = True
        try:
            path = str(Path(directory_path).resolve())
            if path not in self.config.directories:
                return {"success": False, "message": "目录未配置"}
                
            config = self.config.directories[path]
            
            # 如果需要重建，先删除现有集合
            if rebuild and self.vector_store.collection_exists(config.collection_name):
                self.vector_store.delete_collection(config.collection_name)
            
            # 处理文档
            self.document_processor.chunk_size = config.chunk_size
            self.document_processor.chunk_overlap = config.chunk_overlap
            
            documents = self.document_processor.process_directory(path)
            
            if not documents:
                return {"success": False, "message": "未找到可处理的文档"}
            
            # 添加到向量存储
            count = self.vector_store.add_documents(config.collection_name, documents)
            
            # 更新配置
            config.last_indexed = self._current_timestamp()
            self.config.save()
            
            return {
                "success": True, 
                "message": f"成功索引 {count} 个文档块",
                "document_count": count
            }
            
        except Exception as e:
            return {"success": False, "message": f"索引失败: {str(e)}"}
        finally:
            self.is_indexing = False

    def search_all(self, query: str) -> List[Dict[str, Any]]:
        """跨所有目录搜索"""
        enabled_directories = [
            config for config in self.config.directories.values() 
            if config.enabled and self.vector_store.collection_exists(config.collection_name)
        ]
        
        if not enabled_directories:
            return []
        
        # 并行搜索所有目录
        all_results = []
        
        if self.config.global_settings.enable_parallel_search:
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_dir = {
                    executor.submit(
                        self.vector_store.search,
                        config.collection_name,
                        query,
                        self.config.global_settings.max_results_per_directory
                    ): config for config in enabled_directories
                }
                
                for future in as_completed(future_to_dir):
                    config = future_to_dir[future]
                    try:
                        results = future.result()
                        # 添加目录信息
                        for result in results:
                            result['directory'] = config.path
                            result['collection_name'] = config.collection_name
                        all_results.extend(results)
                    except Exception as e:
                        print(f"搜索目录失败 {config.path}: {e}")
        else:
            # 串行搜索
            for config in enabled_directories:
                try:
                    results = self.vector_store.search(
                        config.collection_name,
                        query,
                        self.config.global_settings.max_results_per_directory
                    )
                    for result in results:
                        result['directory'] = config.path
                        result['collection_name'] = config.collection_name
                    all_results.extend(results)
                except Exception as e:
                    print(f"搜索目录失败 {config.path}: {e}")
        
        # 按相似度重新排序
        all_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        return all_results

    def search_single(self, directory_path: str, query: str) -> List[Dict[str, Any]]:
        """搜索单个目录"""
        path = str(Path(directory_path).resolve())
        if path not in self.config.directories:
            return []
            
        config = self.config.directories[path]
        if not config.enabled or not self.vector_store.collection_exists(config.collection_name):
            return []
        
        results = self.vector_store.search(
            config.collection_name,
            query,
            self.config.global_settings.max_results_per_directory * 2  # 单个目录可以多返回一些
        )
        
        # 添加目录信息
        for result in results:
            result['directory'] = config.path
            result['collection_name'] = config.collection_name
            
        return results

    def get_directory_status(self, directory_path: str) -> Dict[str, Any]:
        """获取目录索引状态"""
        path = str(Path(directory_path).resolve())
        if path not in self.config.directories:
            return {"exists": False}
            
        config = self.config.directories[path]
        collection_exists = self.vector_store.collection_exists(config.collection_name)
        
        return {
            "exists": True,
            "enabled": config.enabled,
            "last_indexed": config.last_indexed,
            "collection_exists": collection_exists,
            "chunk_size": config.chunk_size,
            "chunk_overlap": config.chunk_overlap
        }

    def get_all_directory_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有目录状态"""
        status = {}
        for path, config in self.config.directories.items():
            status[path] = self.get_directory_status(path)
        return status

    def _current_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().isoformat()