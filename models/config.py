# models/config.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, List
from pathlib import Path
import json
import os
import dataclasses


@dataclass
class ModelConfig:
    """模型配置"""
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_model_path: str = "./models/embedding/"
    device: str = "cpu"


@dataclass
class DirectoryConfig:
    """目录配置"""
    path: str
    enabled: bool = True
    chunk_size: int = 500
    chunk_overlap: int = 50
    collection_name: str = None
    last_indexed: str = None

    def __post_init__(self):
        if not self.collection_name:
            path_hash = hash(self.path) % 10000
            self.collection_name = f"docs_{abs(path_hash):04d}"


@dataclass
class GlobalConfig:
    """全局配置"""
    max_results_per_directory: int = 10
    enable_parallel_search: bool = True
    show_relevance_scores: bool = True
    auto_index_new_files: bool = True


class AppConfig:
    """应用配置"""

    def __init__(self):
        self.directories: Dict[str, DirectoryConfig] = {}
        self.global_settings = GlobalConfig()
        self.model_settings = ModelConfig()
        self.config_dir = Path.home() / ".doc_search_assistant"
        self.config_path = self.config_dir / "config.json"

    def save(self):
        """保存配置到文件"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "directories": {
                path: {
                    "enabled": config.enabled,
                    "chunk_size": config.chunk_size,
                    "chunk_overlap": config.chunk_overlap,
                    "collection_name": config.collection_name,
                    "last_indexed": config.last_indexed
                } for path, config in self.directories.items()
            },
            "global_settings": asdict(self.global_settings),
            "model_settings": asdict(self.model_settings)
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self):
        """从文件加载配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 加载目录配置
                self.directories.clear()
                for path, config_data in data.get("directories", {}).items():
                    self.directories[path] = DirectoryConfig(path=path, **config_data)

                # 加载全局设置 - 只传递存在的字段
                global_data = data.get("global_settings", {})
                valid_global_fields = {f.name for f in dataclasses.fields(GlobalConfig)}
                filtered_global_data = {k: v for k, v in global_data.items() if k in valid_global_fields}
                self.global_settings = GlobalConfig(**filtered_global_data)

                # 加载模型设置
                model_data = data.get("model_settings", {})
                valid_model_fields = {f.name for f in dataclasses.fields(ModelConfig)}
                filtered_model_data = {k: v for k, v in model_data.items() if k in valid_model_fields}

                # 为了向后兼容，如果配置文件中存在已移除的字段，忽略它们
                if 'qa_model' in filtered_model_data:
                    del filtered_model_data['qa_model']
                if 'qa_model_path' in filtered_model_data:
                    del filtered_model_data['qa_model_path']
                if 'vl_model' in filtered_model_data:
                    del filtered_model_data['vl_model']
                if 'vl_model_path' in filtered_model_data:
                    del filtered_model_data['vl_model_path']

                self.model_settings = ModelConfig(**filtered_model_data)

            except Exception as e:
                print(f"加载配置失败: {e}")
                # 使用默认配置
                self.global_settings = GlobalConfig()
                self.model_settings = ModelConfig()

    def get_enabled_directories(self) -> List[DirectoryConfig]:
        """获取启用的目录配置"""
        return [config for config in self.directories.values() if config.enabled]