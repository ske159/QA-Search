# core/document_processor.py
import os
import fitz  # PyMuPDF
from docx import Document
from typing import List, Tuple, Dict, Any
from pathlib import Path
import chardet
import hashlib


class DocumentProcessor:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.supported_extensions = {
            '.pdf', '.docx', '.doc', '.txt',
            '.pptx', '.xlsx', '.csv', '.html', '.htm'
        }

    def process_directory(self, directory_path: str) -> List[dict]:
        """处理目录下的所有文档"""
        documents = []
        path = Path(directory_path)

        for file_path in path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                try:
                    file_docs = self.process_file(str(file_path))
                    for doc in file_docs:
                        doc['source_file'] = str(file_path)
                        doc['file_type'] = file_path.suffix.lower()
                        doc['file_name'] = file_path.name
                    documents.extend(file_docs)
                except Exception as e:
                    print(f"处理文件失败 {file_path}: {e}")

        return documents

    def process_file(self, file_path: str) -> List[dict]:
        """处理单个文件并分块"""
        text, metadata = self.extract_text_with_metadata(file_path)
        if not text.strip():
            return []

        chunks = self.split_text(text)

        # 为每个块添加元数据
        for i, chunk in enumerate(chunks):
            # 生成唯一的chunk_id
            content_hash = hashlib.md5(chunk['content'].encode()).hexdigest()[:8]
            chunk['chunk_id'] = f"{Path(file_path).stem}_{i}_{content_hash}"
            chunk.update(metadata)

        return chunks

    def extract_text_with_metadata(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """根据文件类型提取文本和元数据"""
        ext = Path(file_path).suffix.lower()
        metadata = {'page_number': 1}

        if ext == '.pdf':
            return self._extract_pdf_text(file_path)
        elif ext in ['.docx', '.doc']:
            return self._extract_docx_text(file_path), metadata
        elif ext == '.txt':
            return self._extract_txt_text(file_path), metadata
        else:
            # 其他格式暂时返回空文本
            return "", metadata

    def _extract_pdf_text(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """提取PDF文本和元数据"""
        full_text = ""
        metadata = {'page_number': 1}

        try:
            with fitz.open(file_path) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()
                    full_text += f"\n--- Page {page_num + 1} ---\n{text}"

                metadata['page_count'] = len(doc)
                if doc.metadata:
                    metadata.update(doc.metadata)

        except Exception as e:
            print(f"PDF提取错误 {file_path}: {e}")

        return full_text, metadata

    def _extract_docx_text(self, file_path: str) -> str:
        """提取Word文档文本"""
        try:
            doc = Document(file_path)
            return "\n".join([paragraph.text for paragraph in doc.paragraphs])
        except Exception as e:
            print(f"DOCX提取错误 {file_path}: {e}")
            return ""

    def _extract_txt_text(self, file_path: str) -> str:
        """提取文本文件，自动检测编码"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
            return raw_data.decode(encoding, errors='ignore')
        except Exception as e:
            print(f"TXT提取错误 {file_path}: {e}")
            return ""

    def split_text(self, text: str) -> List[dict]:
        """将文本分割成块"""
        if not text.strip():
            return []

        # 简单的按句子分割，然后合并到合适的大小
        sentences = text.replace('\n', ' ').split('.')
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # 如果当前块加上新句子不会超过限制，或者当前块为空
            if current_length + sentence_length <= self.chunk_size or not current_chunk:
                current_chunk.append(sentence)
                current_length += sentence_length + 1  # +1 for period
            else:
                # 保存当前块
                chunk_text = '. '.join(current_chunk) + '.'
                chunks.append({'content': chunk_text})

                # 开始新块，保留重叠部分
                if self.chunk_overlap > 0 and current_chunk:
                    # 计算要保留的重叠句子
                    overlap_length = 0
                    overlap_sentences = []
                    for s in reversed(current_chunk):
                        if overlap_length + len(s) <= self.chunk_overlap:
                            overlap_sentences.insert(0, s)
                            overlap_length += len(s) + 1
                        else:
                            break

                    current_chunk = overlap_sentences
                    current_length = overlap_length
                else:
                    current_chunk = []
                    current_length = 0

                # 添加新句子到当前块
                current_chunk.append(sentence)
                current_length += sentence_length + 1

        # 添加最后一个块
        if current_chunk:
            chunk_text = '. '.join(current_chunk) + '.'
            chunks.append({'content': chunk_text})

        return chunks