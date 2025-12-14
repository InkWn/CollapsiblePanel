__all__ = ["AppWidget"]

import os
from PySide6.QtWidgets import QApplication, QWidget, QFrame, QScrollArea, QMessageBox, QLayout, QVBoxLayout
from PySide6.QtWidgets import QLabel, QFileIconProvider, QMenu
from PySide6.QtCore import QFileInfo, QMimeData, QRect, QPoint, QSize
from PySide6.QtGui import Qt, QIcon, QDrag

from declaration import CollapsiblePanel


# 自定义流式布局
class FlowLayout(QLayout):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.__parent = parent
        self.__items = []
        self.setSpacing(3)

    def addItem(self, item) -> None:
        self.__items.append(item)

    def delItem(self, widget) -> bool:
        """删除控件"""
        idx = self.__findItemIndex(widget)
        if idx == -1: return False

        self.__items.pop(idx)
        self.update()
        return True

    def clearItems(self) -> None:
        """删除所有控件"""
        self.__items.clear()
        self.update()

    def swapItems(self, item1, item2) -> bool:
        """交换两个控件的位置"""
        idx1 = self.__findItemIndex(item1)
        idx2 = self.__findItemIndex(item2)

        if idx1 != -1 and idx2 != -1 and idx1 != idx2:
            # 交换列表中的位置
            self.__items[idx1], self.__items[idx2] = self.__items[idx2], self.__items[idx1]
            self.update()  # 重新布局
            return True
        return False

    def count(self): return len(self.__items)
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def itemAt(self, i): return self.__items[i] if 0 <= i < len(self.__items) else None

    def takeAt(self, i):
        if 0 <= i < len(self.__items):
            return self.__items.pop(i)
        return None

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        if not self.__items: return

        x, y, line_height = 0, 0, 0
        max_width = rect.width()  # 使用父容器的宽度作为限制

        for item in self.__items:
            widget = item.widget()
            if not widget: continue

            size = item.sizeHint()
            space = self.spacing()

            # 检查是否超出宽度，需要换行
            if x + size.width() > max_width and x > 0:
                x = 0
                y += line_height + space
                line_height = 0

            item.setGeometry(QRect(QPoint(x, y), size))
            x += size.width() + space
            line_height = max(line_height, size.height())

    def sizeHint(self) -> QSize:
        # 返回固定宽度和计算出的高度
        if not self.__parent: return QSize(1, 1)

        width = self.__parent.width()
        height = self.heightForWidth(width)
        return QSize(width, height)

    def heightForWidth(self, width) -> int:
        if not self.__items: return 0

        x, y, line_height = 0, 0, 0

        for item in self.__items:
            widget = item.widget()
            if not widget: continue

            size = item.sizeHint()
            space = self.spacing()

            if x + size.width() > width and x > 0:
                x = 0
                y += line_height + space
                line_height = 0

            x += size.width() + space
            line_height = max(line_height, size.height())

        return y + line_height

    def __findItemIndex(self, item) -> int:
        """查找控件的索引"""
        for i, item in enumerate(self.__items):
            if item.widget() == item:
                return i
        return -1


class Item(QFrame):
    def __init__(self, icon: QIcon, name: str, path: str, parent: "AppWidget"):
        """应用单项，实例化后应及时调用setNAppIconSize()"""
        super().__init__(parent)
        self.setObjectName("item")
        self.setToolTip(f"{name} ({path})")
        lyt = QVBoxLayout(self)
        lyt.setSpacing(0)
        lyt.setContentsMargins(0, 2, 0, 2)

        self.appIconSize: int = None
        self.icon = icon
        self.name = name
        self.path = path
        self.parent = parent

        self.iconLabel = QLabel(self)
        self.iconLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.__clickedPos = None
        self.__dragging = False

        lyt.addWidget(self.iconLabel, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        lyt.addWidget(QLabel(name, self), alignment=Qt.AlignmentFlag.AlignHCenter)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.setFrameShape(QFrame.Shape.StyledPanel)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.__delSelf(1)
        elif event.button() == Qt.MouseButton.RightButton:
            self.parent.setHasActivePopup(True)
            menu = QMenu(self)
            menu.addAction("启动", self.startFile)
            menu.addAction("移除", lambda: self.__delSelf(0))
            menu.addAction("打开文件所在位置", lambda: self.startFile(os.path.dirname(self.path)))
            menu.exec(self.mapToGlobal(event.position().toPoint()))
            self.parent.setHasActivePopup(False)

    def mouseMoveEvent(self, event):
        if self.appIconSize is None: return
        self.parent.setHasDraggingWidget(True)
        drag = QDrag(self)
        drag.setPixmap(self.icon.pixmap(self.appIconSize, self.appIconSize))
        mimeData = QMimeData()
        mimeData.setText("appItem")
        drag.setMimeData(mimeData)
        drag.exec()  # 执行拖动
        self.parent.setHasDraggingWidget(False)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.startFile()
            event.accept()
        super().mouseDoubleClickEvent(event)

    def setNAppIconSize(self, appIconSize: int, fontSize: int) -> None:
        self.appIconSize = appIconSize
        self.iconLabel.setPixmap(self.icon.pixmap(appIconSize, appIconSize))
        self.setFixedSize(appIconSize * 2.5, appIconSize * 2)
        font = self.font()
        font.setPointSize(fontSize)
        self.setFont(font)

    def startFile(self, path=None):
        if path is None: path = self.path
        if os.path.exists(path):
            os.startfile(path)
            if self.parent.collapseOnOpen:  # 打开时折叠窗口
                self.parent.collapseWindowsFromUser()
        else: self.__delSelf(2)

    def __delSelf(self, code: int) -> bool:
        """:param code: 删除方式，0：直接删除，1：存在且询问删除，>2：不存在且询问删除"""
        if code == 0:
            if self.parent.delItem(self):
                self.deleteLater()
                return True
        if code == 1:
            title = "提示"
            text = "是否从列表中移除应用？"
        else:
            title = "错误"
            text = "文件夹或应用不存在，是否从列表中移除？"

        self.parent.setHasActivePopup(True)
        QApplication.beep()
        result = QMessageBox.question(
            self.parent, title, text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if result == QMessageBox.StandardButton.Yes:
            if self.parent.delItem(self):
                self.deleteLater()
        self.parent.setHasActivePopup(False)


class AppWidget(QScrollArea):
    def __init__(
            self,
            category: str,
            appIconSize: int,
            AppMapping: dict,
            collapseOnOpen: bool,
            parent: "CollapsiblePanel"
    ):
        super().__init__(parent)
        self.setObjectName("AppWidget")
        self.category = category
        self.appIconSize = appIconSize
        self.appMapping = AppMapping
        self.collapseOnOpen = collapseOnOpen
        self.parent = parent

        self.setAcceptDrops(True)
        self.setWidgetResizable(True)

        self.mainWidget = QWidget(self)
        self.mainLayout = FlowLayout(self.mainWidget)
        self.mainLayout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.mainWidget.setLayout(self.mainLayout)
        self.setWidget(self.mainWidget)

        self.parent = parent
        self.items: list[Item] = []
        self.paths = []

        self.__init()

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.text() == "appItem":
            event.accept()
        else: event.ignore()

    def dropEvent(self, event) -> bool:
        """处理放下事件"""
        mime = event.mimeData()
        if mime.text() == "appItem":  # 内部项拖动
            item1 = event.source()
            item2 = self.childAt(event.position().toPoint())
            if not isinstance(item2, Item):  # 非item项，可能是内部的label
                item2 = item2.parent()
                if not isinstance(item2, Item):
                    event.ignore()
                    return False
            if item1 != item2:
                self.swapItems(item1, item2)
                event.accept()
                return True
            else: event.ignore()
        return False

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.parent.setHasActivePopup(True)
            menu = QMenu(self)
            menu.addAction("移除所有", self.clearItems)
            menu.exec(self.mapToGlobal(event.position().toPoint()))
            self.parent.setHasActivePopup(False)

    def __init(self) -> None:
        for name, path in self.appMapping[self.category].items():
            item = Item(QIcon(QFileIconProvider().icon(QFileInfo(path))), name, path, self)
            self.mainLayout.addWidget(item)
            self.items.append(item)
            self.paths.append(path)
        self.setNAppIconSize(self.appIconSize)

    def addItem(self, name: str, path: str) -> Item:
        item = Item(QIcon(QFileIconProvider().icon(QFileInfo(path))), name, path, self)
        item.setNAppIconSize(self.appIconSize, self._calcFontSize(self.appIconSize))
        self.mainLayout.addWidget(item)
        self.items.append(item)
        self.paths.append(path)
        return item

    def delItem(self, item: Item) -> bool:
        try: self.mainLayout.delItem(item)
        except ValueError: return False
        self.items.remove(item)
        self.parent.delItem(self.category, item.name)
        return True

    def clearItems(self) -> None:
        for item in self.items:
            item.deleteLater()
        self.mainLayout.clearItems()
        self.parent.clearItems(self.category)
        self.items = []

    def swapItems(self, item1: Item, item2: Item) -> bool:
        self.parent.swapItems(self.category, item1.name, item2.name)
        return self.mainLayout.swapItems(item1, item2)

    @staticmethod
    def getAppName(path: str) -> str: return os.path.basename(path.rstrip('\\/')).split(".")[0]
    def collapseWindowsFromUser(self) -> None: self.parent.collapseWindowsFromUser()

    def setHasDraggingWidget(self, flag: bool) -> None:
        if self.parent is None: return
        self.parent.setHasDraggingWidget(flag)

    def setHasActivePopup(self, flag: bool) -> None:
        if self.parent is None: return
        self.parent.setHasActivePopup(flag)

    def setNAppIconSize(self, appIconSize: int) -> None:
        """批量设置Item的AppIconSize"""
        fontSize = self._calcFontSize(appIconSize)
        for item in self.items: item.setNAppIconSize(appIconSize, fontSize)

    @staticmethod
    def _calcFontSize(size: int) -> int:
        if size <= 48: fontSize = int(size * 0.4)
        elif size <= 96: fontSize = int(size * 0.35)
        else: fontSize = int(size * 0.3)

        fontSize = max(8, min(fontSize, 72))
        return fontSize
