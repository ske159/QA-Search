# core/vector_store.py
import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, model_manager, persist_directory: str = "./chroma_data"):
        self.model_manager = model_manager
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )

    def create_collection(self, collection_name: str) -> chromadb.Collection:
        """创建或获取集合"""
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(self, collection_name: str, documents: List[Dict]):
        """添加文档到集合"""
        if not self.model_manager.embedding_loaded:
            logger.error("嵌入模型未加载，无法添加文档")
            return 0

        collection = self.create_collection(collection_name)

        # 准备数据
        ids = []
        contents = []
        metadatas = []

        for doc in documents:
            content = doc.get('content', '').strip()
            if not content:
                continue

            ids.append(doc['chunk_id'])
            contents.append(content)

            metadata = {
                'source_file': doc.get('source_file', ''),
                'file_type': doc.get('file_type', ''),
                'file_name': doc.get('file_name', ''),
                'page_number': doc.get('page_number', 1)
            }
            metadatas.append(metadata)

        if not ids:
            return 0

        # 使用模型生成嵌入
        embeddings = self.model_manager.get_embedding(contents).tolist()

        # 分批添加
        batch_size = 100
        total_added = 0

        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            batch_documents = contents[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]

            try:
                collection.add(
                    embeddings=batch_embeddings,
                    documents=batch_documents,
                    metadatas=batch_metadatas,
                    ids=batch_ids
                )
                total_added += len(batch_ids)
            except Exception as e:
                logger.error(f"添加批次失败: {e}")
                continue

        logger.info(f"✅ 成功添加 {total_added} 个文档块到集合 {collection_name}")
        return total_added

    def search(self, collection_name: str, query: str, n_results: int = 10) -> List[Dict]:
        """搜索文档"""
        try:
            collection = self.client.get_collection(collection_name)

            # 生成查询向量
            query_embedding = self.model_manager.get_embedding([query]).tolist()

            results = collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=['documents', 'metadatas', 'distances']
            )

            # 转换结果为更易用的格式
            search_results = []
            for i in range(len(results['documents'][0])):
                search_results.append({
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'similarity': 1 - results['distances'][0][i]
                })

            return search_results
        except Exception as e:
            logger.error(f"搜索失败 {collection_name}: {e}")
            return []

    def delete_collection(self, collection_name: str):
        """删除集合"""
        try:
            self.client.delete_collection(collection_name)
            return True
        except Exception as e:
            logger.error(f"删除集合失败 {collection_name}: {e}")
            return False

    def collection_exists(self, collection_name: str) -> bool:
        """检查集合是否存在"""
        try:
            self.client.get_collection(collection_name)
            return True
        except:
            return False