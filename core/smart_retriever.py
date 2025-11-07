# core/smart_retriever.py
import logging
from typing import List, Dict, Any
import re

logger = logging.getLogger(__name__)


class SmartRetriever:
    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.search_engine = None  # 将在外部设置

    def smart_search(self, question: str, search_results: List[Dict]) -> Dict[str, Any]:
        """智能搜索和答案生成"""
        if not search_results:
            return {
                "answer": "抱歉，没有找到相关的文档信息。",
                "sources": [],
                "confidence": 0.0
            }

        try:
            # 将 SearchResult 对象转换为字典格式
            search_results_dict = self._convert_search_results(search_results)

            if hasattr(self.model_manager, 'is_qa_available') and self.model_manager.is_qa_available():
                return self._model_enhanced_search(question, search_results_dict)
            else:
                return self._basic_search(question, search_results_dict)
        except Exception as e:
            logger.error(f"智能搜索失败: {e}")
            return self._basic_search(question, search_results_dict)

    def _convert_search_results(self, search_results: List) -> List[Dict]:
        """将 SearchResult 对象转换为字典格式"""
        converted_results = []
        for result in search_results:
            if hasattr(result, 'to_dict'):
                # 如果是 SearchResult 对象
                result_dict = {
                    'content': getattr(result, 'overview', '') + " " + getattr(result, 'highlight_snippet', ''),
                    'metadata': {
                        'source_file': getattr(result, 'source_file', ''),
                        'file_name': getattr(result, 'filename', ''),
                        'page_number': getattr(result, 'page_number', 1)
                    },
                    'similarity': getattr(result, 'relevance_score', 0)
                }
            else:
                # 已经是字典格式
                result_dict = result
            converted_results.append(result_dict)
        return converted_results

    def _model_enhanced_search(self, question: str, search_results: List[Dict]) -> Dict[str, Any]:
        """使用模型增强的搜索"""
        # 构建上下文
        context = self._build_context(search_results)

        if not context.strip():
            return self._basic_search(question, search_results)

        # 使用模型生成答案
        try:
            qa_result = self.model_manager.get_qa_answer(question, context)

            # 提取相关出处
            sources = self._extract_sources(search_results)

            return {
                "answer": qa_result['answer'],
                "sources": sources,
                "confidence": qa_result['score'],
                "model_used": True
            }
        except Exception as e:
            logger.error(f"模型问答失败: {e}")
            return self._basic_search(question, search_results)

    def _build_context(self, context_docs: List[Dict], max_length: int = 2000) -> str:
        """构建模型上下文"""
        context_parts = []
        total_length = 0

        for doc in context_docs[:5]:  # 取前5个最相关的文档
            content = doc.get('content', '')
            if total_length + len(content) > max_length:
                # 如果超过最大长度，截断内容
                remaining_length = max_length - total_length
                if remaining_length > 100:  # 至少保留100个字符
                    content = content[:remaining_length] + "..."
                else:
                    break

            context_parts.append(content)
            total_length += len(content)

        return "\n\n".join(context_parts)

    def _extract_sources(self, context_docs: List[Dict]) -> List[Dict]:
        """提取答案相关的出处信息"""
        sources = []
        for doc in context_docs[:3]:  # 只显示前3个最相关的出处
            metadata = doc.get('metadata', {})
            sources.append({
                'file': metadata.get('source_file', ''),
                'filename': metadata.get('file_name', ''),
                'similarity': doc.get('similarity', 0),
                'content_preview': doc.get('content', '')[:150] + "..." if len(
                    doc.get('content', '')) > 150 else doc.get('content', '')
            })
        return sources

    def _basic_search(self, question: str, search_results: List[Dict]) -> Dict[str, Any]:
        """基础搜索（降级方案）"""
        if not search_results:
            return {
                "answer": "没有找到相关信息。",
                "sources": [],
                "confidence": 0.0,
                "model_used": False
            }

        # 找到最相关的文档片段
        best_doc = max(search_results, key=lambda x: x.get('similarity', 0))

        # 从文档中提取相关信息
        answer = self._extract_relevant_info(question, best_doc.get('content', ''))

        metadata = best_doc.get('metadata', {})
        sources = [{
            'file': metadata.get('source_file', ''),
            'filename': metadata.get('file_name', ''),
            'similarity': best_doc.get('similarity', 0),
            'content_preview': best_doc.get('content', '')[:100] + "..."
        }]

        return {
            "answer": answer,
            "sources": sources,
            "confidence": best_doc.get('similarity', 0.5),
            "model_used": False
        }

    def _extract_relevant_info(self, question: str, content: str) -> str:
        """从内容中提取相关信息"""
        if not content:
            return "没有找到相关内容。"

        # 简单的关键词匹配和提取
        question_lower = question.lower()
        content_lower = content.lower()

        # 查找包含问题关键词的句子
        sentences = content.split('。')
        relevant_sentences = []

        for sentence in sentences:
            sentence_lower = sentence.lower()
            # 计算句子与问题的相关性
            score = sum(1 for word in question_lower.split() if word in sentence_lower and len(word) > 1)
            if score > 0:
                relevant_sentences.append((sentence, score))

        # 按相关性排序并选择前3个句子
        relevant_sentences.sort(key=lambda x: x[1], reverse=True)
        selected_sentences = [s[0] for s in relevant_sentences[:3]]

        if selected_sentences:
            answer = "。".join(selected_sentences) + "。"
        else:
            # 如果没有找到相关句子，返回开头部分
            answer = content[:300] + "..." if len(content) > 300 else content

        return answer