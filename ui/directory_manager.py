# ui/directory_manager.py
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                               QListWidgetItem, QPushButton, QLabel, QMessageBox,
                               QFileDialog, QGroupBox, QCheckBox, QSpinBox,
                               QFormLayout, QProgressBar)
from PySide6.QtCore import Signal, Qt
from pathlib import Path

from models.config import DirectoryConfig


class DirectoryManagerDialog(QDialog):
    directories_updated = Signal()

    def __init__(self, index_manager, parent=None):
        super().__init__(parent)
        self.index_manager = index_manager
        self.config = index_manager.config

        self.init_ui()
        self.load_directories()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("目录管理")
        self.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout(self)

        # 目录列表
        self.dirs_list = QListWidget()
        self.dirs_list.itemSelectionChanged.connect(self.on_directory_selected)
        layout.addWidget(QLabel("已管理的目录:"))
        layout.addWidget(self.dirs_list)

        # 按钮组
        button_layout = QHBoxLayout()

        self.add_button = QPushButton("添加目录")
        self.add_button.clicked.connect(self.on_add_directory)
        button_layout.addWidget(self.add_button)

        self.remove_button = QPushButton("移除目录")
        self.remove_button.clicked.connect(self.on_remove_directory)
        self.remove_button.setEnabled(False)
        button_layout.addWidget(self.remove_button)

        self.index_button = QPushButton("索引目录")
        self.index_button.clicked.connect(self.on_index_directory)
        self.index_button.setEnabled(False)
        button_layout.addWidget(self.index_button)

        self.rebuild_button = QPushButton("重建索引")
        self.rebuild_button.clicked.connect(self.on_rebuild_index)
        self.rebuild_button.setEnabled(False)
        button_layout.addWidget(self.rebuild_button)

        layout.addLayout(button_layout)

        # 目录配置
        self.config_group = QGroupBox("目录配置")
        self.config_group.setEnabled(False)
        config_layout = QFormLayout(self.config_group)

        self.enabled_check = QCheckBox("启用此目录")
        config_layout.addRow("启用:", self.enabled_check)

        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(100, 2000)
        self.chunk_size_spin.setValue(500)
        self.chunk_size_spin.setSuffix(" 字符")
        config_layout.addRow("分块大小:", self.chunk_size_spin)

        self.chunk_overlap_spin = QSpinBox()
        self.chunk_overlap_spin.setRange(0, 500)
        self.chunk_overlap_spin.setValue(50)
        self.chunk_overlap_spin.setSuffix(" 字符")
        config_layout.addRow("重叠大小:", self.chunk_overlap_spin)

        self.status_label = QLabel("未选择目录")
        config_layout.addRow("状态:", self.status_label)

        layout.addWidget(self.config_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 关闭按钮
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        close_layout.addWidget(self.close_button)

        layout.addLayout(close_layout)

        # 连接配置变更信号
        self.enabled_check.stateChanged.connect(self.on_config_changed)
        self.chunk_size_spin.valueChanged.connect(self.on_config_changed)
        self.chunk_overlap_spin.valueChanged.connect(self.on_config_changed)

    def load_directories(self):
        """加载目录列表"""
        self.dirs_list.clear()
        for path, config in self.config.directories.items():
            item = QListWidgetItem(path)
            item.setData(Qt.ItemDataRole.UserRole, config)

            # 显示状态
            status = self.index_manager.get_directory_status(path)
            if status.get('collection_exists'):
                item.setText(f"{path} ✓")
            else:
                item.setText(f"{path} ✗ (未索引)")

            self.dirs_list.addItem(item)

    def on_directory_selected(self):
        """目录选择改变"""
        selected_items = self.dirs_list.selectedItems()
        if not selected_items:
            self.remove_button.setEnabled(False)
            self.index_button.setEnabled(False)
            self.rebuild_button.setEnabled(False)
            self.config_group.setEnabled(False)
            self.status_label.setText("未选择目录")
            return

        item = selected_items[0]
        config = item.data(Qt.ItemDataRole.UserRole)

        self.remove_button.setEnabled(True)
        self.index_button.setEnabled(True)
        self.rebuild_button.setEnabled(True)
        self.config_group.setEnabled(True)

        # 加载配置
        self.current_config = config
        self.enabled_check.setChecked(config.enabled)
        self.chunk_size_spin.setValue(config.chunk_size)
        self.chunk_overlap_spin.setValue(config.chunk_overlap)

        # 显示状态
        status = self.index_manager.get_directory_status(config.path)
        if status.get('collection_exists'):
            last_indexed = status.get('last_indexed', '未知')
            self.status_label.setText(f"已索引 (最后更新: {last_indexed})")
        else:
            self.status_label.setText("未索引")

    def on_add_directory(self):
        """添加目录"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择要管理的目录"
        )

        if directory:
            path = str(Path(directory).resolve())

            if path in self.config.directories:
                QMessageBox.information(self, "提示", "该目录已在管理列表中")
                return

            # 添加目录
            success = self.index_manager.add_directory(path)
            if success:
                self.load_directories()
                self.directories_updated.emit()

                # 询问是否立即索引
                reply = QMessageBox.question(
                    self, "索引目录",
                    "是否立即索引此目录?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self.current_config = self.config.directories[path]
                    self.on_index_directory()
            else:
                QMessageBox.warning(self, "错误", "添加目录失败")

    def on_remove_directory(self):
        """移除目录"""
        selected_items = self.dirs_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        config = item.data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要从管理中移除目录?\n{config.path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.index_manager.remove_directory(config.path)
            if success:
                self.load_directories()
                self.directories_updated.emit()
                self.config_group.setEnabled(False)
            else:
                QMessageBox.warning(self, "错误", "移除目录失败")

    def on_index_directory(self):
        """索引目录"""
        if not hasattr(self, 'current_config'):
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 无限进度条

        # 禁用按钮
        self.set_buttons_enabled(False)

        # 在工作线程中执行索引
        from .main_window import IndexWorker
        self.index_worker = IndexWorker(
            self.index_manager, self.current_config.path, rebuild=False
        )
        self.index_worker.progress.connect(self.on_index_progress)
        self.index_worker.finished.connect(self.on_index_finished)
        self.index_worker.error.connect(self.on_index_error)
        self.index_worker.start()

    def on_rebuild_index(self):
        """重建索引"""
        if not hasattr(self, 'current_config'):
            return

        reply = QMessageBox.question(
            self, "确认重建",
            "重建索引将删除现有的索引数据并重新处理所有文档。\n确定要继续吗?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)

            # 禁用按钮
            self.set_buttons_enabled(False)

            # 在工作线程中执行重建
            from .main_window import IndexWorker
            self.index_worker = IndexWorker(
                self.index_manager, self.current_config.path, rebuild=True
            )
            self.index_worker.progress.connect(self.on_index_progress)
            self.index_worker.finished.connect(self.on_index_finished)
            self.index_worker.error.connect(self.on_index_error)
            self.index_worker.start()

    def on_index_progress(self, message: str):
        """索引进度更新"""
        self.status_label.setText(message)

    def on_index_finished(self, result: dict):
        """索引完成"""
        self.progress_bar.setVisible(False)
        self.set_buttons_enabled(True)

        if result.get('success'):
            QMessageBox.information(self, "完成", result['message'])
            self.load_directories()  # 刷新状态显示
            self.directories_updated.emit()
        else:
            QMessageBox.warning(self, "索引失败", result['message'])

    def on_index_error(self, error_msg: str):
        """索引错误"""
        self.progress_bar.setVisible(False)
        self.set_buttons_enabled(True)
        QMessageBox.critical(self, "索引错误", f"索引过程中发生错误:\n{error_msg}")

    def on_config_changed(self):
        """配置变更"""
        if hasattr(self, 'current_config'):
            self.current_config.enabled = self.enabled_check.isChecked()
            self.current_config.chunk_size = self.chunk_size_spin.value()
            self.current_config.chunk_overlap = self.chunk_overlap_spin.value()

            self.config.save()
            self.directories_updated.emit()

    def set_buttons_enabled(self, enabled: bool):
        """设置按钮启用状态"""
        self.add_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        self.index_button.setEnabled(enabled)
        self.rebuild_button.setEnabled(enabled)
        self.close_button.setEnabled(enabled)