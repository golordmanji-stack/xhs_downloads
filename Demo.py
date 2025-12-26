import sys
import os
import time

from PyQt5.QtCore import QUrl, Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar, QLineEdit,
                             QTabWidget, QStatusBar, QMessageBox, QStyle,
                             QHBoxLayout, QWidget, QSpacerItem, QSizePolicy, QVBoxLayout)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
from PyQt5.QtGui import QKeySequence, QFont
from PyQt5.QtWidgets import QAction, QShortcut

# 设置环境变量以避免一些兼容性问题
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-web-security --no-sandbox"


class BrowserTab(QWebEngineView):
    def __init__(self, parent=None):
        super(BrowserTab, self).__init__(parent)

        # 启用必要的Web引擎设置
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)

        self.loadFinished.connect(self.on_load_finished)
        self.loadProgress.connect(self.on_load_progress)
        self.urlChanged.connect(self.on_url_changed)

    def capture_fully_rendered_html(self, callback, max_wait=15000):
        """获取完全渲染后的HTML"""
        print("开始等待页面完全渲染...")
        start_time = time.time()

        def attempt_capture(attempt=1):
            current_time = time.time()
            elapsed = (current_time - start_time) * 1000  # 转毫秒

            if elapsed >= max_wait:
                print("达到最大等待时间，强制获取HTML")
                self.get_final_html(callback)
                return

            # 检查页面状态
            check_script = """
            (function() {
                // 基础检查
                if (document.readyState !== 'complete') return 'document_not_ready';

                // jQuery AJAX检查
                if (window.jQuery && jQuery.active) return 'ajax_loading';

                // 图片加载检查
                var images = Array.from(document.images);
                var loadingImages = images.filter(img => !img.complete);
                if (loadingImages.length > 0) return 'images_loading';

                // 自定义组件加载检查（如果有）
                if (window.isPageFullyLoaded && !window.isPageFullyLoaded()) {
                    return 'custom_loading';
                }

                return 'ready';
            })();
            """

            def check_status(status):
                if status == 'ready':
                    print(f"页面完全就绪，耗时: {elapsed:.0f}ms")
                    self.get_final_html(callback)
                else:
                    wait_time = min(500 * attempt, 2000)  # 递增等待时间，最大2秒
                    print(f"页面状态: {status}, 等待 {wait_time}ms 后重试...")
                    QTimer.singleShot(wait_time, lambda: attempt_capture(attempt + 1))

            self.page().runJavaScript(check_script, check_status)

        # 开始检查
        attempt_capture()

    def on_load_finished(self, success):
        if success:
            print(f"页面加载完成: {self.url().toString()}")
        else:
            print("页面加载失败")

    def on_load_progress(self, progress):
        # 可以在这里更新进度条
        pass

    def on_url_changed(self, url):
        # URL变化时的处理
        pass

    def createWindow(self, windowType):
        # 处理新窗口打开请求（如target="_blank"的链接）
        if windowType == QWebEnginePage.WebBrowserTab:
            # 获取主窗口并创建新标签页
            main_window = self.get_main_window()
            if main_window:
                return main_window.add_new_tab()
        return None

    def get_main_window(self):
        # 获取主窗口实例
        parent = self.parent()
        while parent:
            if isinstance(parent, BrowserWindow):
                return parent
            parent = parent.parent()
        return None


class NavigationBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser_window = parent
        self.init_ui()

    def init_ui(self):
        # 创建水平布局
        layout = QHBoxLayout()
        layout.setSpacing(0)  # 设置按钮间距
        layout.setContentsMargins(0, 0, 0, 0)  # 设置边距

        # 设置导航栏样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #e0e0e0;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 8px 12px;
                border-radius: 6px;
                color: #5f6368;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e8f0fe;
                color: #1a73e8;
            }
            QPushButton:pressed {
                background-color: #d2e3fc;
            }
        """)

        # 添加左侧弹性空间
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # 添加右侧弹性空间
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.setLayout(layout)
        self.setFixedHeight(0)  # 固定高度

    def navigate_to(self, url):
        if self.browser_window and self.browser_window.current_browser():
            self.browser_window.current_browser().load(QUrl(url))


class BrowserWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tabs = None
        self.url_bar = None
        self.status_bar = None
        self.nav_bar = None
        self.browsers = []  # 保存所有浏览器实例的引用
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("浏览器")
        self.setGeometry(100, 100, 1400, 900)

        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建顶部工具栏
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        # 创建导航栏
        self.nav_bar = NavigationBar(self)
        main_layout.addWidget(self.nav_bar)

        # 创建标签页控件
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)

        # 设置标签页样式
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: white;
            }
            QTabBar::tab {
                background: #f1f3f4;
                border: 1px solid #dadce0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                margin-right: 2px;
                color: #5f6368;
            }
            QTabBar::tab:selected {
                background: white;
                border-color: #dadce0;
                color: #202124;
            }
            QTabBar::tab:hover:!selected {
                background: #e8f0fe;
            }
        """)

        main_layout.addWidget(self.tabs)

        central_widget.setLayout(main_layout)

        # 添加状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 添加快捷键
        self.setup_shortcuts()

        # 添加初始标签页
        self.add_new_tab(QUrl("https://www.xiaohongshu.com"))

    def create_toolbar(self):
        """创建顶部工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)

        # 设置工具栏样式
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e0e0e0;
                spacing: 10px;
                padding: 0 15px;
            }
            QToolButton {
                background-color: transparent;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #f1f3f4;
            }
            QLineEdit {
                border: 2px solid #dfe1e5;
                border-radius: 24px;
                padding: 8px 20px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #1a73e8;
                background: white;
            }
        """)

        # 后退按钮
        back_btn = QAction("◀", self)
        back_btn.triggered.connect(self.navigate_back)
        toolbar.addAction(back_btn)

        # 前进按钮
        forward_btn = QAction("▶", self)
        forward_btn.triggered.connect(self.navigate_forward)
        toolbar.addAction(forward_btn)

        # 刷新按钮
        refresh_btn = QAction("↻", self)
        refresh_btn.triggered.connect(self.navigate_refresh)
        toolbar.addAction(refresh_btn)

        # 主页按钮
        home_btn = QAction("🏠", self)
        home_btn.triggered.connect(self.navigate_home)
        toolbar.addAction(home_btn)

        # 地址栏
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("输入网址或搜索内容...")
        self.url_bar.setFixedHeight(40)
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        toolbar.addWidget(self.url_bar)

        # 添加弹性空间
        toolbar.addSeparator()

        # 新标签页按钮
        new_tab_btn = QAction("➕", self)
        new_tab_btn.triggered.connect(lambda: self.add_new_tab())
        toolbar.addAction(new_tab_btn)

        return toolbar

    def setup_shortcuts(self):
        """设置快捷键"""
        # Ctrl+T - 新建标签页
        shortcut_new_tab = QShortcut(QKeySequence("Ctrl+T"), self)
        shortcut_new_tab.activated.connect(lambda: self.add_new_tab())

        # Ctrl+W - 关闭当前标签页
        shortcut_close_tab = QShortcut(QKeySequence("Ctrl+W"), self)
        shortcut_close_tab.activated.connect(self.close_current_tab)

        # Ctrl+R - 刷新
        shortcut_refresh = QShortcut(QKeySequence("Ctrl+R"), self)
        shortcut_refresh.activated.connect(self.navigate_refresh)

        # Ctrl+L - 聚焦地址栏
        shortcut_focus_url = QShortcut(QKeySequence("Ctrl+L"), self)
        shortcut_focus_url.activated.connect(self.focus_url_bar)

    def add_new_tab(self, url=None):
        try:
            if url is None:
                url = QUrl("https://www.xiaohongshu.com")
            elif isinstance(url, bool):
                url = QUrl("https://www.xiaohongshu.com")

            browser = BrowserTab()
            browser.load(url)

            # 保存浏览器实例引用
            self.browsers.append(browser)

            browser.titleChanged.connect(lambda title, browser=browser:
                                         self.update_tab_title(browser, title))
            browser.urlChanged.connect(lambda url, browser=browser:
                                       self.update_url_bar(url, browser))
            browser.loadProgress.connect(lambda progress, browser=browser:
                                         self.update_status_bar(progress, browser))

            title = "加载中..."
            index = self.tabs.addTab(browser, title)
            self.tabs.setCurrentIndex(index)

            return browser

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建标签页时出错: {str(e)}")
            return None

    def close_tab(self, index):
        try:
            if self.tabs.count() > 1:
                widget = self.tabs.widget(index)
                if widget in self.browsers:
                    self.browsers.remove(widget)
                self.tabs.removeTab(index)
                widget.deleteLater()
            else:
                self.close()
        except Exception as e:
            print(f"关闭标签页时出错: {e}")

    def close_current_tab(self):
        current_index = self.tabs.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)

    def current_browser(self):
        return self.tabs.currentWidget()

    def navigate_to_url(self):
        try:
            url_text = self.url_bar.text().strip()
            if not url_text:
                return

            if not url_text.startswith(('http://', 'https://')):
                url_text = 'https://' + url_text

            browser = self.current_browser()
            if browser:
                browser.load(QUrl(url_text))
        except Exception as e:
            QMessageBox.warning(self, "导航错误", f"无法导航到该URL: {str(e)}")

    def navigate_back(self):
        browser = self.current_browser()
        if browser and browser.history().canGoBack():
            browser.back()

    def navigate_forward(self):
        browser = self.current_browser()
        if browser and browser.history().canGoForward():
            browser.forward()

    def navigate_refresh(self):
        browser = self.current_browser()
        if browser:
            browser.reload()

    def navigate_home(self):
        browser = self.current_browser()
        if browser:
            browser.load(QUrl("https://www.xiaohongshu.com"))

    def update_tab_title(self, browser, title):
        try:
            index = self.tabs.indexOf(browser)
            if index != -1:
                # 限制标题长度
                if len(title) > 20:
                    title = title[:20] + "..."
                self.tabs.setTabText(index, title)
                self.tabs.setTabToolTip(index, title)
        except Exception as e:
            print(f"更新标签标题时出错: {e}")

    def update_url_bar(self, url, browser):
        try:
            if browser == self.current_browser():
                self.url_bar.setText(url.toString())
                self.url_bar.setCursorPosition(0)
        except Exception as e:
            print(f"更新地址栏时出错: {e}")

    def update_status_bar(self, progress, browser):
        if browser == self.current_browser():
            if progress < 100:
                self.status_bar.showMessage(f"加载中... {progress}%")
            else:
                self.status_bar.showMessage("加载完成")

    def tab_changed(self, index):
        # 切换标签页时更新地址栏
        if index >= 0:
            browser = self.tabs.widget(index)
            if browser:
                self.update_url_bar(browser.url(), browser)

    def focus_url_bar(self):
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    def closeEvent(self, event):
        # 清理所有浏览器实例
        for browser in self.browsers:
            try:
                browser.stop()
                browser.deleteLater()
            except:
                pass
        self.browsers.clear()
        event.accept()


if __name__ == '__main__':
    # 设置高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # 设置应用程序字体
    font = QFont("Microsoft YaHei", 10)  # 使用微软雅黑字体
    app.setFont(font)

    app.setApplicationName("浏览器")
    app.setApplicationVersion("1.01")

    window = BrowserWindow()
    window.show()

    try:
        sys.exit(app.exec_())
    except Exception as e:
        print(f"应用程序错误: {e}")
