# core/model_manager.py
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import torch
from PIL import Image

logger = logging.getLogger(__name__)


class ModelManager:
    """统一模型管理器"""

    def __init__(self, config):
        self.config = config
        self.embedding_model = None
        self.qa_pipeline = None
        self.vl_model = None  # 视觉语言模型
        self.vl_processor = None
        self.embedding_loaded = False
        self.qa_loaded = False
        self.vl_loaded = False
        self.qa_model_available = False

    def load_embedding_model(self, model_name: Optional[str] = None, model_path: Optional[str] = None):
        """加载嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer

            model_name = model_name or self.config.model_settings.embedding_model
            model_path = model_path or self.config.model_settings.embedding_model_path

            # 检查本地模型是否存在
            local_path = Path(model_path) / model_name
            if local_path.exists():
                logger.info(f"从本地加载嵌入模型: {local_path}")
                self.embedding_model = SentenceTransformer(str(local_path))
            else:
                logger.info(f"从网络加载嵌入模型: {model_name}")
                self.embedding_model = SentenceTransformer(model_name)

                # 保存到本地
                local_path.mkdir(parents=True, exist_ok=True)
                self.embedding_model.save(str(local_path))
                logger.info(f"模型已保存到: {local_path}")

            self.embedding_loaded = True
            logger.info("✅ 嵌入模型加载成功")
            return True

        except Exception as e:
            logger.error(f"嵌入模型加载失败: {e}")
            self.embedding_loaded = False
            return False

    def load_qa_model(self, model_name: Optional[str] = None, model_path: Optional[str] = None):
        """加载问答模型"""
        try:
            from transformers import AutoModelForQuestionAnswering, AutoTokenizer, pipeline

            model_name = model_name or self.config.model_settings.qa_model
            model_path = model_path or self.config.model_settings.qa_model_path

            logger.info(f"正在加载问答模型: {model_name}")

            # 检查本地模型是否存在
            local_model_path = Path(model_path) / model_name

            if local_model_path.exists():
                logger.info(f"使用本地问答模型: {local_model_path}")
                # 加载模型和tokenizer
                model = AutoModelForQuestionAnswering.from_pretrained(str(local_model_path))
                tokenizer = AutoTokenizer.from_pretrained(str(local_model_path))

                # 创建pipeline
                self.qa_pipeline = pipeline(
                    "question-answering",
                    model=model,
                    tokenizer=tokenizer,
                    device=-1  # 使用CPU
                )
            else:
                logger.info(f"从网络加载问答模型: {model_name}")
                # 直接从网络加载
                self.qa_pipeline = pipeline(
                    "question-answering",
                    model=model_name,
                    tokenizer=model_name,
                    device=-1  # 使用CPU
                )

            self.qa_loaded = True
            self.qa_model_available = True
            logger.info("✅ 问答模型加载成功")
            return True

        except Exception as e:
            logger.error(f"问答模型加载失败: {e}")
            logger.info("将使用基于规则的问答模式")
            self.qa_loaded = False
            self.qa_model_available = False
            return False

    def load_visual_language_model(self, model_name: Optional[str] = None, model_path: Optional[str] = None):
        """加载视觉语言模型 (BGE-VL-Screenshot)"""
        try:
            from transformers import AutoModel, AutoProcessor

            model_name = model_name or "BAAI/BGE-VL-Screenshot"
            model_path = model_path or self.config.model_settings.vl_model_path

            # 检查本地模型是否存在
            local_model_path = Path(model_path) / "BGE-VL-Screenshot"

            if local_model_path.exists():
                logger.info(f"从本地加载视觉语言模型: {local_model_path}")
                # 加载自定义的模型类
                import sys
                sys.path.append(str(local_model_path))

                # 加载processor和model
                self.vl_processor = AutoProcessor.from_pretrained(
                    str(local_model_path),
                    trust_remote_code=True
                )
                self.vl_model = AutoModel.from_pretrained(
                    str(local_model_path),
                    trust_remote_code=True
                )
            else:
                logger.info(f"从网络加载视觉语言模型: {model_name}")
                self.vl_processor = AutoProcessor.from_pretrained(
                    model_name,
                    trust_remote_code=True
                )
                self.vl_model = AutoModel.from_pretrained(
                    model_name,
                    trust_remote_code=True
                )

                # 保存到本地
                local_model_path.mkdir(parents=True, exist_ok=True)
                self.vl_processor.save_pretrained(str(local_model_path))
                self.vl_model.save_pretrained(str(local_model_path))
                logger.info(f"视觉语言模型已保存到: {local_model_path}")

            # 设置为评估模式
            self.vl_model.eval()
            self.vl_loaded = True
            logger.info("✅ 视觉语言模型加载成功")
            return True

        except Exception as e:
            logger.error(f"视觉语言模型加载失败: {e}")
            self.vl_loaded = False
            return False

    def get_visual_embedding(self, images: Union[str, List[str], Image.Image, List[Image.Image]],
                             texts: Optional[Union[str, List[str]]] = None):
        """获取视觉语言模型的嵌入向量"""
        if not self.vl_loaded or self.vl_model is None or self.vl_processor is None:
            raise RuntimeError("视觉语言模型未加载")

        try:
            # 处理输入数据
            if isinstance(images, str):
                images = [images]
            if isinstance(texts, str):
                texts = [texts]

            # 加载图像
            image_list = []
            for img in images:
                if isinstance(img, str):
                    image_list.append(Image.open(img).convert('RGB'))
                else:
                    image_list.append(img)

            # 预处理
            inputs = self.vl_processor(
                images=image_list,
                text=texts,
                padding=True,
                return_tensors="pt"
            )

            # 推理
            with torch.no_grad():
                outputs = self.vl_model(**inputs)
                # BGE-VL模型返回的嵌入在outputs的最后一个隐藏状态中
                embeddings = outputs.last_hidden_state.mean(dim=1)  # 平均池化

            return embeddings.numpy()

        except Exception as e:
            logger.error(f"视觉语言模型推理失败: {e}")
            raise

    def get_embedding(self, text):
        """获取文本嵌入"""
        if not self.embedding_loaded or self.embedding_model is None:
            raise RuntimeError("嵌入模型未加载")

        if isinstance(text, str):
            text = [text]
        return self.embedding_model.encode(text)

    def get_qa_answer(self, question: str, context: str):
        """使用模型生成答案"""
        if not self.qa_loaded or self.qa_pipeline is None:
            raise RuntimeError("问答模型未加载")

        try:
            # 限制上下文长度，避免超出模型限制
            max_length = 512
            if len(context) > max_length:
                context = context[:max_length]

            result = self.qa_pipeline({
                'question': question,
                'context': context
            })
            return result
        except Exception as e:
            logger.error(f"问答推理失败: {e}")
            raise

    def is_qa_available(self):
        """检查问答模型是否可用"""
        return self.qa_loaded and self.qa_model_available

    def is_vl_available(self):
        """检查视觉语言模型是否可用"""
        return self.vl_loaded

    def get_available_models(self) -> Dict[str, list]:
        """获取可用模型列表"""
        return {
            "embedding_models": [
                "all-MiniLM-L6-v2",
                "paraphrase-multilingual-MiniLM-L12-v2",
                "distiluse-base-multilingual-cased"
            ],
            "qa_models": [
                "bert-base-chinese",
                "uer/roberta-base-chinese-extractive-qa",
                "luhua/chinese_pretrain_mrc_roberta_wwm_ext_large"
            ],
            "visual_language_models": [
                "BAAI/BGE-VL-Screenshot"
            ]
        }