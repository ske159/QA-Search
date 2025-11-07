# models/search_result.py
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class SearchResult:
    """搜索结果数据模型"""
    overview: str                    # 文档概述
    source_file: str                # 源文件路径
    filename: str                   # 文件名
    page_number: int                # 页码
    relevance_score: float          # 相关度分数 (0-1)
    highlight_snippet: str          # 高亮文本片段
    file_type: str                  # 文件类型
    directory: str                  # 所属目录
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "概述": self.overview,
            "文件": f"{self.filename} (第{self.page_number}页)",
            "路径": self.source_file,
            "匹配度": f"{self.relevance_score:.1%}",
            "相关片段": self.highlight_snippet,
            "类型": self.file_type,
            "目录": self.directory
        }
    
    def get_short_path(self) -> str:
        """获取缩短的路径显示"""
        path = Path(self.source_file)
        return f".../{path.parent.name}/{path.name}"
    
    def open_file(self) -> bool:
        """打开源文件"""
        try:
            import os
            import platform
            file_path = self.source_file
            
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                os.system(f'open "{file_path}"')
            else:  # Linux
                os.system(f'xdg-open "{file_path}"')
            return True
        except Exception as e:
            print(f"打开文件失败: {e}")
            return False
    
    def open_containing_folder(self) -> bool:
        """打开文件所在文件夹"""
        try:
            import os
            import platform
            folder_path = str(Path(self.source_file).parent)
            
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":  # macOS
                os.system(f'open "{folder_path}"')
            else:  # Linux
                os.system(f'xdg-open "{folder_path}"')
            return True
        except Exception as e:
            print(f"打开文件夹失败: {e}")
            return False