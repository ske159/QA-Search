# ui/main_window.py
import sys
import os
from pathlib import Path
from typing import List

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                               QListWidgetItem, QLabel, QTextEdit, QSplitter,
                               QComboBox, QProgressBar, QMessageBox, QFileDialog,
                               QTabWidget, QGroupBox, QCheckBox, QSpinBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon, QAction

from models.config import AppConfig
from models.search_result import SearchResult
from core.index_manager import IndexManager
from core.search_engine import SearchEngine
from .directory_manager import DirectoryManagerDialog


class SearchWorker(QThread):
    """搜索工作线程"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, search_engine, query: str, directory: str = None):
        super().__init__()
        self.search_engine = search_engine
        self.query = query
        self.directory = directory

    def run(self):
        try:
            results = self.search_engine.search(self.query, self.directory)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class IndexWorker(QThread):
    """索引工作线程"""
    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, index_manager, directory_path: str, rebuild: bool = False):
        super().__init__()
        self.index_manager = index_manager
        self.directory_path = directory_path
        self.rebuild = rebuild

    def run(self):
        try:
            self.progress.emit(f"开始索引目录: {self.directory_path}")
            result = self.index_manager.index_directory(self.directory_path, self.rebuild)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self, config, index_manager, model_manager, search_engine):
        super().__init__()
        self.config = config
        self.index_manager = index_manager
        self.model_manager = model_manager
        self.search_engine = search_engine

        self.search_worker = None
        self.index_worker = None

        self.init_ui()
        self.setup_menus()

        # 加载目录状态
        self.update_directory_status()

        # 显示模型状态
        self.update_model_status()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("文档智能搜索助手")
        self.setGeometry(100, 100, 1200, 800)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        layout = QVBoxLayout(central_widget)

        # 搜索栏
        search_group = self.create_search_group()
        layout.addWidget(search_group)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：搜索结果列表
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.on_result_selected)
        splitter.addWidget(self.results_list)

        # 右侧：详情面板
        detail_widget = self.create_detail_widget()
        splitter.addWidget(detail_widget)

        splitter.setSizes([400, 600])
        layout.addWidget(splitter, 1)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.statusBar().addWidget(self.status_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)

    def create_search_group(self) -> QGroupBox:
        """创建搜索组"""
        group = QGroupBox("搜索")
        layout = QVBoxLayout(group)

        # 第一行：搜索输入和按钮
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入您要搜索的问题...")
        self.search_input.returnPressed.connect(self.on_search)

        # 添加中文输入支持
        self.search_input.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.search_input.setInputMethodHints(Qt.InputMethodHint.ImhMultiLine)

        search_layout.addWidget(self.search_input)

        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.on_search)
        search_layout.addWidget(self.search_button)

        layout.addLayout(search_layout)

        # 第二行：搜索选项
        options_layout = QHBoxLayout()

        options_layout.addWidget(QLabel("搜索范围:"))

        self.search_scope_combo = QComboBox()
        self.search_scope_combo.addItem("所有目录", None)
        # 目录选项将在update_directory_status中动态添加
        self.search_scope_combo.currentIndexChanged.connect(self.on_scope_changed)
        options_layout.addWidget(self.search_scope_combo)

        self.auto_search_check = QCheckBox("实时搜索")
        options_layout.addWidget(self.auto_search_check)

        options_layout.addStretch()

        self.manage_dirs_button = QPushButton("管理目录")
        self.manage_dirs_button.clicked.connect(self.on_manage_directories)
        options_layout.addWidget(self.manage_dirs_button)

        layout.addLayout(options_layout)

        return group

    def create_detail_widget(self) -> QWidget:
        """创建详情面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 详情标签
        detail_label = QLabel("文档详情")
        detail_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(detail_label)

        # 基本信息
        info_group = QGroupBox("基本信息")
        info_layout = QVBoxLayout(info_group)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        info_layout.addWidget(self.info_text)

        layout.addWidget(info_group)

        # 内容预览
        content_group = QGroupBox("内容预览")
        content_layout = QVBoxLayout(content_group)

        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        content_layout.addWidget(self.content_text)

        layout.addWidget(content_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.open_file_button = QPushButton("打开文件")
        self.open_file_button.clicked.connect(self.on_open_file)
        self.open_file_button.setEnabled(False)
        button_layout.addWidget(self.open_file_button)

        self.open_folder_button = QPushButton("打开所在文件夹")
        self.open_folder_button.clicked.connect(self.on_open_folder)
        self.open_folder_button.setEnabled(False)
        button_layout.addWidget(self.open_folder_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        return widget

    def setup_menus(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")

        manage_dirs_action = QAction("管理目录", self)
        manage_dirs_action.triggered.connect(self.on_manage_directories)
        tools_menu.addAction(manage_dirs_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self.on_about)
        help_menu.addAction(about_action)

    def update_directory_status(self):
        """更新目录状态显示"""
        # 保存当前选择的目录
        current_data = self.search_scope_combo.currentData()

        # 清空并重新添加目录选项
        self.search_scope_combo.clear()
        self.search_scope_combo.addItem("所有目录", None)

        for path, config in self.config.directories.items():
            status = self.index_manager.get_directory_status(path)
            display_name = f"{Path(path).name}"
            if status.get('collection_exists'):
                display_name += " ✓"
            else:
                display_name += " ✗ (未索引)"

            self.search_scope_combo.addItem(display_name, path)

        # 恢复之前的选择
        if current_data:
            index = self.search_scope_combo.findData(current_data)
            if index >= 0:
                self.search_scope_combo.setCurrentIndex(index)

    def update_model_status(self):
        """更新模型状态显示"""
        embedding_status = "✅ 已加载" if self.model_manager.embedding_loaded else "❌ 未加载"
        qa_status = "✅ 已加载" if self.model_manager.qa_loaded else "❌ 未加载"

        status_text = f"嵌入模型: {embedding_status} | 问答模型: {qa_status}"
        self.status_label.setText(status_text)

    def on_search(self):
        """执行搜索"""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "输入错误", "请输入搜索内容")
            return

        # 获取搜索范围
        directory = self.search_scope_combo.currentData()

        # 清空之前的结果
        self.results_list.clear()
        self.info_text.clear()
        self.content_text.clear()
        self.open_file_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)

        # 显示搜索中状态
        self.status_label.setText("搜索中...")
        self.search_button.setEnabled(False)

        # 在工作线程中执行搜索
        self.search_worker = SearchWorker(self.search_engine, query, directory)
        self.search_worker.finished.connect(self.on_search_finished)
        self.search_worker.error.connect(self.on_search_error)
        self.search_worker.start()

    def on_search_finished(self, results: List[SearchResult]):
        """搜索完成处理"""
        self.search_button.setEnabled(True)

        if not results:
            self.status_label.setText("未找到相关文档")
            QMessageBox.information(self, "搜索结果", "未找到相关文档")
            return

        # 显示结果
        for result in results:
            item = QListWidgetItem(f"{result.filename} ({result.relevance_score:.1%})")
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.results_list.addItem(item)

        self.status_label.setText(f"找到 {len(results)} 个结果")

        # 自动选择第一个结果
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

    def on_search_error(self, error_msg: str):
        """搜索错误处理"""
        self.search_button.setEnabled(True)
        self.status_label.setText("搜索失败")
        QMessageBox.critical(self, "搜索错误", f"搜索过程中发生错误:\n{error_msg}")

    def on_result_selected(self, item):
        """结果项被选中"""
        result = item.data(Qt.ItemDataRole.UserRole)
        if not result:
            return

        # 显示基本信息
        info_text = f"""文件: {result.filename}
路径: {result.source_file}
目录: {result.directory}
类型: {result.file_type}
匹配度: {result.relevance_score:.1%}
页码: 第{result.page_number}页

概述: {result.overview}"""

        self.info_text.setText(info_text)

        # 显示内容预览
        self.content_text.setText(result.highlight_snippet)

        # 启用操作按钮
        self.open_file_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)

        # 保存当前选中的结果
        self.current_result = result

    def on_open_file(self):
        """打开文件"""
        if hasattr(self, 'current_result'):
            success = self.current_result.open_file()
            if not success:
                QMessageBox.warning(self, "打开失败", "无法打开文件，请检查文件是否存在")

    def on_open_folder(self):
        """打开文件所在文件夹"""
        if hasattr(self, 'current_result'):
            success = self.current_result.open_containing_folder()
            if not success:
                QMessageBox.warning(self, "打开失败", "无法打开文件夹")

    def on_scope_changed(self):
        """搜索范围改变"""
        # 可以在这里添加范围改变的逻辑
        pass

    def on_manage_directories(self):
        """打开目录管理对话框"""
        dialog = DirectoryManagerDialog(self.index_manager, self)
        dialog.directories_updated.connect(self.on_directories_updated)
        dialog.exec()

    def on_directories_updated(self):
        """目录更新后处理"""
        self.config.save()
        self.update_directory_status()
        self.status_label.setText("目录配置已更新")

    def on_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于",
                          "文档智能搜索助手 v1.0\n\n"
                          "基于本地AI的文档检索系统\n"
                          "支持多目录管理和智能搜索")

    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止工作线程
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.terminate()
            self.search_worker.wait()

        if self.index_worker and self.index_worker.isRunning():
            self.index_worker.terminate()
            self.index_worker.wait()

        event.accept()