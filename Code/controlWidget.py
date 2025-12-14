from PySide6.QtWidgets import QApplication, QWidget, QToolButton, QHBoxLayout, QMessageBox
from PySide6.QtCore import QSize, QPoint
from PySide6.QtGui import Qt, QIcon

from declaration import CollapsiblePanel


# 功能栏
class ControlWidget(QWidget):
    def __init__(
            self, IconPathRoot: str, titleIconSize: int,
            theme: str, screenSize: QSize, parent: "CollapsiblePanel"
    ):
        super().__init__(parent)
        self.setObjectName("ControlWidget")
        # 参数
        self.iconPathRoot = IconPathRoot
        self.titleIconSize = titleIconSize
        self.theme = theme
        self.screenSize = screenSize
        self.parent = parent
        # 变量
        self.icons = {"dark": {}, "light": {}}  # 图标缓存
        self.dragging = False
        self.dragPos = QPoint()
        # 布局
        self.mainLayout = QHBoxLayout(self)
        self.leftLayout = QHBoxLayout(self)
        self.rightLayout = QHBoxLayout(self)
        # 按钮组件
        self.movingBtn = QToolButton(self)
        self.collapsedBtn = QToolButton(self)
        self.setLockBtn = QToolButton(self)
        self.settingsBtn = QToolButton(self)
        self.closeBtn = QToolButton(self)

        self.__initLyt()
        self.__initButtons()

    def __initLyt(self):
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.leftLayout.setContentsMargins(0, 0, 0, 0)
        self.rightLayout.setContentsMargins(0, 0, 0, 0)

        self.leftLayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.rightLayout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.mainLayout.addLayout(self.leftLayout, 1)
        self.mainLayout.addLayout(self.rightLayout, 1)

    def __initButtons(self):
        # ---------------右侧---------------
        self.setNTitleIconSize(self.titleIconSize)

        self.movingBtn.setToolTip("按住移动窗口")
        self.movingBtn.setAutoRaise(True)
        self.movingBtn.mousePressEvent = self.__mousePressEvent
        self.movingBtn.mouseReleaseEvent = self.__mouseReleaseEvent
        self.movingBtn.mouseMoveEvent = self.__mouseMoveEvent

        self.collapsedBtn.setToolTip("折叠窗口（会保留锁定状态）")
        self.collapsedBtn.setAutoRaise(True)
        self.collapsedBtn.clicked.connect(self.parent.collapseWindowsFromUser)

        self.setLockBtn.setToolTip("锁定/解锁 自动折叠窗口")
        self.setLockBtn.setAutoRaise(True)
        self.setLockBtn.clicked.connect(lambda: self.setLock(None))

        self.settingsBtn.setToolTip("展开/收起 设置界面")
        self.settingsBtn.setAutoRaise(True)
        self.settingsBtn.clicked.connect(lambda: self.openSettings(None))

        self.closeBtn.setToolTip("关闭窗口")
        self.closeBtn.setAutoRaise(True)
        self.closeBtn.clicked.connect(self.__closeWindows)

        self.rightLayout.addWidget(self.movingBtn)
        self.rightLayout.addWidget(self.collapsedBtn)
        self.rightLayout.addWidget(self.setLockBtn)
        self.rightLayout.addWidget(self.settingsBtn)
        self.rightLayout.addWidget(self.closeBtn)

    def switchTheme(self, theme: str):
        """切换主题，重新加载图标"""
        self.theme = theme
        self.movingBtn.setIcon(self.__loadIcon("moving"))
        self.collapsedBtn.setIcon(self.__loadIcon("collapsed"))
        if self.parent.isLocked: lockIcon = "unlock"
        else: lockIcon = "lock"
        self.setLockBtn.setIcon(self.__loadIcon(lockIcon))
        self.settingsBtn.setIcon(self.__loadIcon("settings"))
        self.closeBtn.setIcon(self.__loadIcon("close"))

    def setNTitleIconSize(self, iconSize: int):
        self.setFixedHeight(iconSize + 2)
        self.movingBtn.setIconSize(QSize(iconSize, iconSize))
        self.collapsedBtn.setIconSize(QSize(iconSize, iconSize))
        self.setLockBtn.setIconSize(QSize(iconSize, iconSize))
        self.settingsBtn.setIconSize(QSize(iconSize, iconSize))
        self.closeBtn.setIconSize(QSize(iconSize, iconSize))

    def setLock(self, state: bool = None):
        if state is None: state = not self.parent.isLocked

        if state: self.setLockBtn.setIcon(self.__loadIcon("unlock"))
        else: self.setLockBtn.setIcon(self.__loadIcon("lock"))
        self.parent.setLock(state)

    def openSettings(self, state: bool = None):
        if state is None: state = self.parent.settingsIsExpand

        if state: self.parent.collapseSettings()
        else: self.parent.expandSettings()
        self.setLock(not state)

    def __loadIcon(self, iconName: str) -> QIcon:
        """iconName是简称"""
        try:
            if self.icons[self.theme].get(iconName) is None:
                self.icons[self.theme][iconName] = QIcon(f"{self.iconPathRoot}/{self.theme}/{iconName}.svg")
            return self.icons[self.theme][iconName]
        except Exception as e: raise f"加载{self.theme}/{iconName}.svg失败，错误信息：{e}"

    def __closeWindows(self):
        self.parent.setHasActivePopup(True)
        QApplication.beep()
        msgBox = QMessageBox(self.parent)
        msgBox.setWindowTitle("关闭窗口")
        msgBox.setText("是否关闭窗口？")
        msgBox.setIcon(QMessageBox.Icon.Question)
        yesBtn = msgBox.addButton("是", QMessageBox.ButtonRole.AcceptRole)
        noBtn = msgBox.addButton("否", QMessageBox.ButtonRole.RejectRole)
        msgBox.setDefaultButton(noBtn)
        msgBox.setEscapeButton(noBtn)
        msgBox.exec()
        if msgBox.clickedButton() == yesBtn:
            self.parent.close()
            return
        self.parent.setHasActivePopup(False)

    def __mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent.setPlacementSpinBoxBlockSig(True)
            self.dragging = True
            self.dragPos = event.position().toPoint()
            event.accept()
        else: event.ignore()

    def __mouseMoveEvent(self, event):
        if self.dragging:
            targetPos = self.parent.frameGeometry().topLeft() + event.position().toPoint() - self.dragPos
            self.parent.move(targetPos)  # 移动窗口
            self.parent.setPlacementSpinBoxValue(targetPos.x())

            event.accept()
        else: event.ignore()

    def __mouseReleaseEvent(self, event):
        if self.parent.alwaysOnEdge:  # 一直处于边缘
            parentCenterPosX = self.parent.pos().x() + self.width() - self.titleIconSize * 4  # 图标的位置
            if parentCenterPosX < self.screenSize.width() / 5 * 2:  # 左
                self.parent.setPlacement("left")
            elif parentCenterPosX < self.screenSize.width() / 5 * 3 + self.parent.width() / 2:
                self.parent.setPlacement("center")
            else: self.parent.setPlacement("right")
        else:
            if self.parent.pos().x() < 0: self.parent.setPlacement("left")
            elif self.parent.pos().x() + self.parent.width() > self.screenSize.width():
                self.parent.setPlacement("right")
            else: self.parent.setPlacement("top")

        self.parent.updateGeometriesState()

        if event.button() == Qt.MouseButton.LeftButton:  # 如果释放的是左键
            self.parent.setPlacementSpinBoxBlockSig(False)
            self.dragging = False
            event.accept()
        else: event.ignore()
