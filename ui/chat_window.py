# ui/chat_window.py
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
from functools import partial  # 添加这个导入

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QTextEdit, QPushButton, QScrollArea,
                               QLabel, QFrame, QSplitter, QMessageBox, QFileDialog,
                               QGroupBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont

from models.config import AppConfig
from core.index_manager import IndexManager
from core.search_engine import SearchEngine
from core.smart_retriever import SmartRetriever
from .directory_manager import DirectoryManagerDialog


class QAWorker(QThread):
    """问答工作线程"""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, smart_retriever, question: str, directory: str = None):
        super().__init__()
        self.smart_retriever = smart_retriever
        self.question = question
        self.directory = directory

    def run(self):
        try:
            # 搜索相关文档并生成答案
            search_results = self.smart_retriever.search_engine.search(self.question, self.directory)
            answer_result = self.smart_retriever.smart_search(self.question, search_results)
            self.finished.emit(answer_result)
        except Exception as e:
            self.error.emit(str(e))


class ChatWindow(QMainWindow):
    def __init__(self, config, index_manager, model_manager, search_engine, smart_retriever):
        super().__init__()
        self.config = config
        self.index_manager = index_manager
        self.model_manager = model_manager
        self.search_engine = search_engine
        self.smart_retriever = smart_retriever

        self.qa_worker = None
        self.current_results = []
        self.current_directory = None  # 当前选中的目录
        self.directory_buttons = {}  # 存储目录按钮的引用

        self.init_ui()
        self.load_components()

    def init_ui(self):
        """初始化简洁实用的界面"""
        self.setWindowTitle("文档智能问答助手")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1000, 700)

        # 设置现代风格
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f7fa;
            }
            QFrame {
                background-color: white;
                border-radius: 8px;
            }
            QTextEdit {
                border: 2px solid #e1e5e9;
                border-radius: 8px;
                padding: 12px;
                background-color: white;
                font-size: 14px;
                selection-background-color: #007acc;
            }
            QTextEdit:focus {
                border-color: #007acc;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
                cursor: pointer;
            }
            QPushButton.primary {
                background-color: #007acc;
                color: white;
            }
            QPushButton.primary:hover {
                background-color: #005a9e;
            }
            QPushButton.primary:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QPushButton.secondary {
                background-color: #6c757d;
                color: white;
            }
            QPushButton.secondary:hover {
                background-color: #545b62;
            }
            QPushButton.directory {
                background-color: #f8f9fa;
                color: #495057;
                border: 2px solid #e1e5e9;
                text-align: left;
                padding: 12px 16px;
                margin: 4px 0;
                font-weight: normal;
            }
            QPushButton.directory:hover {
                background-color: #e9ecef;
                border-color: #007acc;
            }
            QPushButton.directory:checked {
                background-color: #007acc;
                color: white;
                border-color: #007acc;
            }
            QPushButton.directory:checked:hover {
                background-color: #005a9e;
            }
            QGroupBox {
                border: 2px solid #e1e5e9;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QLabel {
                background-color: transparent;
            }
            #directoryPanel {
                background-color: white;
                border: 2px solid #e1e5e9;
                border-radius: 8px;
                padding: 15px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题栏
        header_frame = QFrame()
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # 标题行
        title_layout = QHBoxLayout()
        title_label = QLabel("💬 文档智能问答助手")
        title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2c3e50;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 模型状态
        self.model_status_label = QLabel("模型加载中...")
        self.model_status_label.setFont(QFont("Arial", 10))
        self.model_status_label.setStyleSheet("color: #7f8c8d;")
        title_layout.addWidget(self.model_status_label)

        header_layout.addLayout(title_layout)

        # 控制行 - 目录选择和操作按钮
        control_layout = QHBoxLayout()

        # 当前目录显示
        self.current_dir_label = QLabel("当前目录: 所有目录")
        self.current_dir_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.current_dir_label.setStyleSheet("color: #2c3e50;")
        control_layout.addWidget(self.current_dir_label)

        control_layout.addStretch()

        # 切换目录面板按钮
        self.toggle_dir_btn = QPushButton("📁 切换目录")
        self.toggle_dir_btn.setProperty("class", "secondary")
        self.toggle_dir_btn.clicked.connect(self.toggle_directory_panel)
        control_layout.addWidget(self.toggle_dir_btn)

        # 管理目录按钮
        self.manage_dirs_btn = QPushButton("⚙️ 管理目录")
        self.manage_dirs_btn.setProperty("class", "secondary")
        self.manage_dirs_btn.clicked.connect(self.manage_directories)
        control_layout.addWidget(self.manage_dirs_btn)

        header_layout.addLayout(control_layout)
        layout.addWidget(header_frame)

        # 目录选择面板 (初始隐藏)
        self.directory_panel = QFrame()
        self.directory_panel.setObjectName("directoryPanel")
        self.directory_panel.setVisible(False)
        directory_layout = QVBoxLayout(self.directory_panel)
        directory_layout.setSpacing(10)

        # 目录面板标题
        dir_panel_title = QLabel("选择搜索目录:")
        dir_panel_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        dir_panel_title.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        directory_layout.addWidget(dir_panel_title)

        # 目录按钮容器
        self.directory_buttons_container = QWidget()
        self.directory_buttons_layout = QVBoxLayout(self.directory_buttons_container)
        self.directory_buttons_layout.setSpacing(5)
        self.directory_buttons_layout.setContentsMargins(0, 0, 0, 0)

        # 添加"所有目录"按钮
        all_dirs_btn = QPushButton("🌐 所有目录")
        all_dirs_btn.setProperty("class", "directory")
        all_dirs_btn.setCheckable(True)
        all_dirs_btn.setChecked(True)
        all_dirs_btn.clicked.connect(lambda: self.select_directory(None, "所有目录"))
        self.directory_buttons_layout.addWidget(all_dirs_btn)
        self.directory_buttons[None] = all_dirs_btn

        directory_layout.addWidget(self.directory_buttons_container)
        directory_layout.addStretch()

        layout.addWidget(self.directory_panel)

        # 主内容区域 - 输入和输出
        content_splitter = QSplitter(Qt.Orientation.Vertical)

        # 上部：输入区域
        input_frame = QFrame()
        input_frame.setMaximumHeight(150)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)

        input_group = QGroupBox("💭 输入问题")
        input_group_layout = QVBoxLayout(input_group)

        input_inner_layout = QHBoxLayout()
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText("请输入您的问题...（直接输入中文）")
        self.question_input.setMaximumHeight(80)
        self.question_input.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        input_inner_layout.addWidget(self.question_input)

        self.send_btn = QPushButton("发送")
        self.send_btn.setProperty("class", "primary")
        self.send_btn.clicked.connect(self.send_question)
        self.send_btn.setEnabled(False)
        input_inner_layout.addWidget(self.send_btn)

        input_group_layout.addLayout(input_inner_layout)
        input_layout.addWidget(input_group)

        # 下部：输出区域
        output_frame = QFrame()
        output_layout = QVBoxLayout(output_frame)
        output_layout.setContentsMargins(0, 0, 0, 0)

        output_group = QGroupBox("🔍 检索结果")
        output_group_layout = QVBoxLayout(output_group)

        # 主要结果显示区域
        self.main_result_scroll = QScrollArea()
        self.main_result_scroll.setWidgetResizable(True)
        self.main_result_container = QWidget()
        self.main_result_layout = QVBoxLayout(self.main_result_container)
        self.main_result_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_result_layout.setSpacing(15)
        self.main_result_layout.setContentsMargins(15, 15, 15, 15)

        self.main_result_scroll.setWidget(self.main_result_container)
        output_group_layout.addWidget(self.main_result_scroll)

        output_layout.addWidget(output_group)

        # 设置分割器比例
        content_splitter.addWidget(input_frame)
        content_splitter.addWidget(output_frame)
        content_splitter.setSizes([150, 750])

        layout.addWidget(content_splitter, 1)

        # 连接信号
        self.question_input.textChanged.connect(self.on_text_changed)

    def toggle_directory_panel(self):
        """切换目录面板显示状态"""
        self.directory_panel.setVisible(not self.directory_panel.isVisible())
        if self.directory_panel.isVisible():
            self.toggle_dir_btn.setText("📁 隐藏目录")
            self.update_directory_buttons()
        else:
            self.toggle_dir_btn.setText("📁 切换目录")

    def update_directory_buttons(self):
        """更新目录按钮列表"""
        # 移除旧的目录按钮（保留"所有目录"按钮）
        for path, button in list(self.directory_buttons.items()):
            if path is not None:  # 保留None（所有目录）按钮
                self.directory_buttons_layout.removeWidget(button)
                button.deleteLater()
                del self.directory_buttons[path]

        # 添加新的目录按钮
        for path, config in self.config.directories.items():
            status = self.index_manager.get_directory_status(path)
            display_name = f"📂 {Path(path).name}"
            if status.get('collection_exists'):
                display_name += " ✓"
            else:
                display_name += " ✗"

            dir_btn = QPushButton(display_name)
            dir_btn.setProperty("class", "directory")
            dir_btn.setCheckable(True)
            dir_btn.setChecked(path == self.current_directory)
            # 使用partial避免lambda参数问题
            dir_btn.clicked.connect(partial(self.select_directory, path, Path(path).name))

            self.directory_buttons_layout.addWidget(dir_btn)
            self.directory_buttons[path] = dir_btn

    def select_directory(self, directory_path: str, display_name: str):
        """选择目录"""
        self.current_directory = directory_path
        self.current_dir_label.setText(f"当前目录: {display_name}")

        # 更新按钮选中状态
        for path, button in self.directory_buttons.items():
            button.setChecked(path == directory_path)

        # 自动隐藏目录面板
        self.directory_panel.setVisible(False)
        self.toggle_dir_btn.setText("📁 切换目录")

    def on_text_changed(self):
        """文本变化时启用/禁用发送按钮"""
        text = self.question_input.toPlainText().strip()
        self.send_btn.setEnabled(len(text) > 0)

    def load_components(self):
        """加载核心组件"""
        self.model_status_label.setText("正在加载AI模型...")

        # 延迟加载模型，避免界面卡顿
        QTimer.singleShot(100, self._load_components_async)

    def _load_components_async(self):
        """异步加载组件"""
        try:
            # 更新模型状态
            embedding_status = "✅" if self.model_manager.embedding_loaded else "❌"
            qa_status = "✅" if self.model_manager.qa_loaded else "❌"

            status_text = f"嵌入模型: {embedding_status} | 问答模型: {qa_status}"
            self.model_status_label.setText(status_text)

            self.send_btn.setEnabled(True)

            # 添加欢迎消息
            self.show_welcome_message()

        except Exception as e:
            self.model_status_label.setText("⚠️ 模型加载异常")
            self.send_btn.setEnabled(True)

    def show_welcome_message(self):
        """显示欢迎消息"""
        welcome_html = """
        <div style='text-align: center; padding: 40px 20px; color: #666;'>
            <h2 style='color: #2c3e50; margin-bottom: 20px;'>👋 欢迎使用文档智能问答助手</h2>
            <p style='font-size: 16px; margin-bottom: 10px;'>请在上方输入您的问题，系统将为您检索相关文档</p>
            <p style='font-size: 14px; color: #7f8c8d;'>💡 提示：点击"切换目录"选择要搜索的文档目录</p>
        </div>
        """
        self.clear_results()
        self.add_result_message(welcome_html, is_html=True)

    def send_question(self):
        """发送问题"""
        question = self.question_input.toPlainText().strip()
        if not question:
            return

        # 清空输入框
        self.question_input.clear()

        # 禁用发送按钮
        self.send_btn.setEnabled(False)

        # 显示思考中...
        self.clear_results()
        self.add_result_message("正在搜索相关文档...", is_thinking=True)

        # 在工作线程中处理问答
        self.qa_worker = QAWorker(self.smart_retriever, question, self.current_directory)
        self.qa_worker.finished.connect(self.on_qa_finished)
        self.qa_worker.error.connect(self.on_qa_error)
        self.qa_worker.start()

    def clear_results(self):
        """清空结果显示"""
        for i in reversed(range(self.main_result_layout.count())):
            widget = self.main_result_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

    def add_result_message(self, content: str, is_html: bool = False, is_thinking: bool = False):
        """添加结果消息"""
        message_frame = QFrame()

        if is_thinking:
            message_frame.setStyleSheet("""
                QFrame {
                    background-color: #fff3cd;
                    border: 2px solid #ffeaa7;
                    border-radius: 10px;
                    padding: 20px;
                }
            """)
        else:
            message_frame.setStyleSheet("""
                QFrame {
                    background-color: white;
                    border: 2px solid #e1e5e9;
                    border-radius: 10px;
                    padding: 20px;
                }
            """)

        message_layout = QVBoxLayout(message_frame)
        message_layout.setSpacing(10)

        content_label = QLabel()
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)

        if is_html:
            content_label.setText(content)
        else:
            if is_thinking:
                content_label.setText(
                    f"<div style='color: #856404; font-size: 16px; text-align: center;'>{content}</div>")
            else:
                content_label.setText(f"<div style='color: #333333; font-size: 16px;'>{content}</div>")

        message_layout.addWidget(content_label)
        self.main_result_layout.addWidget(message_frame)

        # 滚动到底部
        QTimer.singleShot(50, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.main_result_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_qa_finished(self, result: Dict):
        """问答完成处理"""
        self.send_btn.setEnabled(True)
        self.clear_results()

        # 显示答案
        answer = result['answer']
        confidence = result.get('confidence', 0)
        model_used = result.get('model_used', False)
        sources = result.get('sources', [])

        # 构建答案显示
        confidence_text = f"<small style='color: #666;'>(置信度: {confidence:.1%})</small>" if confidence > 0 else ""
        model_text = " [AI生成]" if model_used else " [基础搜索]"

        answer_html = f"""
        <div style='margin-bottom: 20px;'>
            <h3 style='color: #2c3e50; margin-bottom: 10px;'>💡 答案{model_text} {confidence_text}</h3>
            <div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #007acc;'>
                <p style='margin: 0; font-size: 16px; line-height: 1.6;'>{answer}</p>
            </div>
        </div>
        """
        self.add_result_message(answer_html, is_html=True)

        # 显示来源信息
        if sources:
            self.show_sources(sources)

    def on_qa_error(self, error: str):
        """问答错误处理"""
        self.send_btn.setEnabled(True)
        self.clear_results()

        error_html = f"""
        <div style='text-align: center; color: #dc3545;'>
            <h3>❌ 处理失败</h3>
            <p>{error}</p>
        </div>
        """
        self.add_result_message(error_html, is_html=True)

    def show_sources(self, sources: List[Dict]):
        """显示答案来源"""
        if not sources:
            return

        # 显示Top1结果（最相关的结果）
        top1_source = sources[0]
        self.show_top1_source(top1_source)

        # 显示其他结果（如果有的话）
        other_sources = sources[1:]
        if other_sources:
            self.show_other_sources(other_sources)

    def show_top1_source(self, source: Dict):
        """显示最相关的结果"""
        filename = source.get('filename', '未知文件')
        file_path = source.get('file', '')
        similarity = source.get('similarity', 0)
        content_preview = source.get('content_preview', '')

        top1_html = f"""
        <div style='margin: 20px 0;'>
            <h3 style='color: #27ae60; margin-bottom: 15px;'>🎯 最相关结果</h3>
            <div style='background-color: #e8f5e8; padding: 20px; border-radius: 8px; border: 2px solid #27ae60;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;'>
                    <h4 style='margin: 0; color: #2c3e50;'>📄 {filename}</h4>
                    <span style='background-color: #27ae60; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px;'>
                        匹配度: {similarity:.1%}
                    </span>
                </div>
                <div style='margin-bottom: 15px;'>
                    <p style='margin: 0 0 10px 0; font-weight: bold; color: #666;'>相关内容:</p>
                    <div style='background-color: white; padding: 12px; border-radius: 6px; border: 1px solid #ddd;'>
                        <p style='margin: 0; font-size: 14px; line-height: 1.5;'>{content_preview}</p>
                    </div>
                </div>
        """

        # 添加打开文件按钮
        if file_path and Path(file_path).exists():
            # 使用QPushButton而不是HTML按钮
            top1_html += "</div></div>"
            self.add_result_message(top1_html, is_html=True)

            # 添加实际的打开文件按钮
            button_frame = QFrame()
            button_frame.setStyleSheet("QFrame { background-color: transparent; }")
            button_layout = QHBoxLayout(button_frame)
            button_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

            open_btn = QPushButton("📂 打开源文件")
            open_btn.setProperty("class", "primary")
            # 使用partial避免lambda参数问题
            open_btn.clicked.connect(partial(self.open_file, file_path))
            button_layout.addWidget(open_btn)

            self.main_result_layout.addWidget(button_frame)
        else:
            top1_html += "</div></div>"
            self.add_result_message(top1_html, is_html=True)

    def show_other_sources(self, sources: List[Dict]):
        """显示其他相关结果"""
        other_html = """
        <div style='margin: 20px 0;'>
            <h3 style='color: #6c757d; margin-bottom: 15px;'>📚 其他相关文件</h3>
            <div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px;'>
        """

        for i, source in enumerate(sources, 1):
            filename = source.get('filename', '未知文件')
            file_path = source.get('file', '')
            similarity = source.get('similarity', 0)

            other_html += f"""
                <div style='display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #e9ecef;'>
                    <span style='font-size: 14px;'>📎 {filename}</span>
                    <div>
                        <span style='color: #666; font-size: 12px; margin-right: 10px;'>{similarity:.1%}</span>
            """

            other_html += "</div></div>"

        other_html += "</div></div>"
        self.add_result_message(other_html, is_html=True)

        # 为每个其他文件添加实际的打开按钮
        for source in sources:
            file_path = source.get('file', '')
            filename = source.get('filename', '未知文件')

            if file_path and Path(file_path).exists():
                button_frame = QFrame()
                button_frame.setStyleSheet("QFrame { background-color: transparent; padding: 5px 0; }")
                button_layout = QHBoxLayout(button_frame)
                button_layout.setContentsMargins(0, 0, 0, 0)

                file_label = QLabel(f"📎 {filename}")
                file_label.setStyleSheet("font-size: 14px;")
                button_layout.addWidget(file_label)

                button_layout.addStretch()

                open_btn = QPushButton("打开")
                open_btn.setProperty("class", "secondary")
                open_btn.setFixedWidth(60)
                # 使用partial避免lambda参数问题
                open_btn.clicked.connect(partial(self.open_file, file_path))
                button_layout.addWidget(open_btn)

                self.main_result_layout.addWidget(button_frame)

    def open_file(self, file_path: str):
        """打开文件"""
        try:
            if Path(file_path).exists():
                # 使用系统默认程序打开文件
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":  # macOS
                    os.system(f'open "{file_path}"')
                else:  # Linux
                    os.system(f'xdg-open "{file_path}"')
            else:
                QMessageBox.warning(self, "打开失败", f"文件不存在:\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{str(e)}")

    def manage_directories(self):
        """管理目录"""
        dialog = DirectoryManagerDialog(self.index_manager, self)
        dialog.directories_updated.connect(self.on_directories_updated)
        dialog.exec()

    def on_directories_updated(self):
        """目录更新后处理"""
        self.config.save()
        self.update_directory_buttons()
        self.model_status_label.setText("目录配置已更新")

    def closeEvent(self, event):
        """关闭事件处理"""
        if self.qa_worker and self.qa_worker.isRunning():
            self.qa_worker.terminate()
            self.qa_worker.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)

    # 加载配置和组件
    config = AppConfig()
    config.load()

    from core.model_manager import ModelManager
    from core.vector_store import VectorStore
    from core.index_manager import IndexManager
    from core.search_engine import SearchEngine
    from core.smart_retriever import SmartRetriever

    model_manager = ModelManager(config)
    model_manager.load_embedding_model()
    model_manager.load_qa_model()

    vector_store = VectorStore(model_manager)
    index_manager = IndexManager(config, model_manager, vector_store)
    search_engine = SearchEngine(index_manager)
    smart_retriever = SmartRetriever(model_manager)
    smart_retriever.search_engine = search_engine

    window = ChatWindow(config, index_manager, model_manager, search_engine, smart_retriever)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()