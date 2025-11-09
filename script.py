# script.py - PyInstaller打包入口脚本
import os
import sys
from pathlib import Path

def setup_environment():
    """设置环境变量和路径"""
    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # 设置Qt插件路径（如果使用PySide6）
    if hasattr(sys, '_MEIPASS'):
        # 在打包环境下
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(
            sys._MEIPASS, 'PySide6', 'plugins', 'platforms'
        )

def main():
    """主函数"""
    setup_environment()
    
    # 导入并启动应用
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    
    from models.config import AppConfig
    from core.model_manager import ModelManager
    from core.vector_store import VectorStore
    from core.index_manager import IndexManager
    from core.search_engine import SearchEngine
    from core.smart_retriever import SmartRetriever
    from ui.chat_window import ChatWindow

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("文档智能问答助手")
    app.setApplicationVersion("1.0.0")

    # 设置高DPI支持
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # 加载配置
    config = AppConfig()
    config.load()

    print("正在初始化系统...")

    # 初始化模型管理器
    model_manager = ModelManager(config)

    # 加载模型
    print("正在加载嵌入模型...")
    if not model_manager.load_embedding_model():
        print("嵌入模型加载失败")
        return 1

    print("正在加载问答模型...")
    model_manager.load_qa_model()

    # 初始化其他组件
    vector_store = VectorStore(model_manager)
    index_manager = IndexManager(config, model_manager, vector_store)
    search_engine = SearchEngine(index_manager)
    smart_retriever = SmartRetriever(model_manager)
    smart_retriever.search_engine = search_engine

    # 创建聊天窗口
    window = ChatWindow(config, index_manager, model_manager, search_engine, smart_retriever)
    window.show()

    print("系统启动完成")

    # 运行应用
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())