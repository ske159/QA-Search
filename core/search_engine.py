# core/search_engine.py
import re
from typing import List
from pathlib import Path

from .index_manager import IndexManager
from models.search_result import SearchResult


class SearchEngine:
    def __init__(self, index_manager: IndexManager):
        self.index_manager = index_manager
    
    def search(self, query: str, directory: str = None) -> List[SearchResult]:
        """执行搜索"""
        if directory:
            raw_results = self.index_manager.search_single(directory, query)
        else:
            raw_results = self.index_manager.search_all(query)
        
        # 转换为SearchResult对象
        search_results = []
        for raw_result in raw_results:
            result = SearchResult(
                overview=self._generate_overview(raw_result['content'], query),
                source_file=raw_result['metadata']['source_file'],
                filename=Path(raw_result['metadata']['source_file']).name,
                page_number=raw_result['metadata'].get('page_number', 1),
                relevance_score=raw_result['similarity'],
                highlight_snippet=self._extract_highlight(raw_result['content'], query),
                file_type=raw_result['metadata'].get('file_type', ''),
                directory=raw_result['directory']
            )
            search_results.append(result)
        
        return search_results
    
    def _generate_overview(self, content: str, query: str) -> str:
        """生成文档概述"""
        # 查找包含查询关键词的句子
        sentences = re.split(r'[.!?。！？]', content)
        query_words = query.lower().split()
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(word in sentence_lower for word in query_words if len(word) > 2):
                cleaned_sentence = sentence.strip()
                if len(cleaned_sentence) > 10:  # 确保句子有足够内容
                    return cleaned_sentence[:100] + "..." if len(cleaned_sentence) > 100 else cleaned_sentence
        
        # 如果没有匹配的句子，返回开头部分
        return content[:100] + "..." if len(content) > 100 else content
    
    def _extract_highlight(self, content: str, query: str) -> str:
        """提取高亮片段"""
        query_words = query.split()
        if not query_words:
            return content[:150] + "..." if len(content) > 150 else content
        
        # 查找包含查询词的上下文
        content_lower = content.lower()
        for word in query_words:
            if len(word) < 3:  # 忽略太短的词
                continue
                
            word_lower = word.lower()
            idx = content_lower.find(word_lower)
            if idx != -1:
                start = max(0, idx - 50)
                end = min(len(content), idx + len(word) + 100)
                snippet = content[start:end]
                
                # 高亮关键词
                highlighted = self._highlight_keywords(snippet, query_words)
                
                if start > 0:
                    highlighted = "..." + highlighted
                if end < len(content):
                    highlighted = highlighted + "..."
                return highlighted
        
        # 如果没有找到关键词，返回开头
        return content[:150] + "..." if len(content) > 150 else content
    
    def _highlight_keywords(self, text: str, keywords: List[str]) -> str:
        """在文本中高亮关键词"""
        for keyword in keywords:
            if len(keyword) < 3:
                continue
            # 使用简单的替换来高亮（在实际UI中可以使用HTML标记）
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            text = pattern.sub(f"*{keyword}*", text)
        return text