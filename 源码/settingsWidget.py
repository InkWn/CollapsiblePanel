__all__ = ["SettingsWidget"]

import os
import sys
import copy
import json
import winreg
from PySide6.QtWidgets import QApplication, QWidget, QFrame, QMessageBox, QScrollArea, QListWidget
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QStyle, QSizePolicy, QLineEdit
from PySide6.QtWidgets import QCheckBox, QLabel, QRadioButton, QSpinBox, QButtonGroup, QPushButton, QSpacerItem
from PySide6.QtCore import QSize, Qt

from declaration import CollapsiblePanel


# 自定义布局
class SettingsLayout(QGridLayout):
    def __init__(self, proportion: list[int], parent, HSpacing: int = 15, VSpacing: int = 7, padding: int = 10):
        """
        :param proportion: 各列所占比例
        :param parent:     父控件，会自动绑定到父控件的布局
        :param HSpacing:   列间距
        :param VSpacing:   行间距
        :param padding:    左边距，仅每行第一次调用有效
        """
        super().__init__(parent)
        proportion.insert(0, 0)
        self.setHorizontalSpacing(HSpacing)
        self.setVerticalSpacing(VSpacing)
        self.setAlignment(Qt.AlignmentFlag.AlignTop)
        for i, p in enumerate(proportion):
            self.setColumnStretch(i, p)
        parent.setLayout(self)
        # 参数
        self.__parent = parent
        self.__padding = padding
        self.__totalColumn = len(proportion)  # 总列数
        self.rowIndex = 0
        self.columnIndex = 0

    def addTitle(self, text: str) -> tuple[QLabel, QFrame]:
        """添加大标题"""
        if self.columnIndex > 0: self.addRow()
        layout = QHBoxLayout(self.__parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel(text, self.__parent)
        label.setObjectName("title-label")
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        line = QFrame(self.__parent)
        line.setObjectName("title-line")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(label)
        layout.addWidget(line)
        self.addLayout(layout, self.rowIndex, 0, 1, self.__totalColumn)
        self.addRow()
        return label, line

    def addRow(self):
        self.rowIndex += 1
        self.columnIndex = 0

    def addColWidget(self, widget: QWidget, span: int = 1):
        """添加控件"""
        if self.columnIndex == 0:
            spacer = QSpacerItem(self.__padding, 0)
            self.addItem(spacer, self.rowIndex, 0)
            self.columnIndex += 1
        self.addWidget(widget, self.rowIndex, self.columnIndex, 1, span)
        self.columnIndex += span
        if self.columnIndex > self.__totalColumn: raise ValueError("超出总列数，请调用 addRow() 换行")

    def addColSpacer(self, span: int = 1) -> QSpacerItem:
        """添加行空白"""
        if self.columnIndex == 0:
            spacer = QSpacerItem(self.__padding, 0)
            self.addItem(spacer, self.rowIndex, 0)
            self.columnIndex += 1
        spacer = QSpacerItem(0, 0)
        self.addItem(spacer, self.rowIndex, self.columnIndex, 1, span)
        self.columnIndex += span
        if self.columnIndex > self.__totalColumn:
            raise ValueError("超出总列数，请调用 addRow() 换行")
        return spacer


# 添加依赖控件
class AddDependencyWidget(QWidget):
    def __init__(self, identifyGroups: list, parent: "SettingsWidget"):
        super().__init__(parent)
        self.identifyGroups = identifyGroups.copy()
        self.parent = parent

        self.mainLayout = QVBoxLayout(self)
        self.inputLayout = QHBoxLayout()

        self.listWidget = QListWidget()
        self.listWidget.setMinimumHeight(100)
        self.listWidget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.listWidget.addItems(self.identifyGroups)

        self.lineEdit = QLineEdit()
        self.lineEdit.setPlaceholderText("输入新项目...")
        self.inputLayout.addWidget(self.lineEdit)

        self.addBtn = QPushButton("添加")
        self.addBtn.setShortcut("Return")
        self.addBtn.clicked.connect(self.addItem)
        self.inputLayout.addWidget(self.addBtn)

        self.delBtn = QPushButton("删除选中")
        self.delBtn.setShortcut("Delete")
        self.delBtn.clicked.connect(self.delItem)
        self.inputLayout.addWidget(self.delBtn)

        self.mainLayout.addWidget(self.listWidget)
        self.mainLayout.addLayout(self.inputLayout)
        self.setLayout(self.mainLayout)

    def addItem(self):
        text = self.lineEdit.text().strip()
        if not text: return
        if text in self.identifyGroups: return

        self.listWidget.addItem(text)
        self.identifyGroups.append(text)
        self.parent.changeIdentify("add", text)
        self.lineEdit.clear()

    def delItem(self):
        for item in self.listWidget.selectedItems():
            row = self.listWidget.row(item)
            delItem = self.listWidget.takeItem(row)
            if delItem:
                text = item.text()
                self.identifyGroups.remove(text)
                self.parent.changeIdentify("del", text)


class SettingsWidget(QScrollArea):
    def __init__(
            self, ConfigPath: str, config: dict,
            screenSize: QSize, logging, parent: "CollapsiblePanel"
    ):
        super().__init__(parent)
        self.setObjectName("settingsWidget")
        self.setWidgetResizable(True)
        # 参数
        self.config = copy.deepcopy(config)     # 原配置
        self.newConfig = copy.deepcopy(config)  # 新配置
        self.configPath = ConfigPath
        self.screenSize = screenSize
        self.logging = logging
        self.parent = parent

        self.mainWidget = QWidget(self)
        self.mainLayout = SettingsLayout([0, 0, 0, 0, 1], self.mainWidget)
        self.mainLayout.setContentsMargins(5, 5, 5, 10)

        self.setWidget(self.mainWidget)

        self.__initControl()
        self.__buildControl()
        self.__initConfig()
        self.__connectControl()
        self.__buildLyt()

    def hideEvent(self, event) -> None:
        self.writeConfig()
        super().hideEvent(event)

    def __initControl(self):
        """初始化控件"""
        self.themeSet: tuple[QRadioButton] = (QRadioButton("暗黑主题", self), QRadioButton("亮色主题", self))

        self.placementSetEdit = QSpinBox()
        self.placementSetRadios: tuple[QRadioButton] = (
            QRadioButton("左上角", self), QRadioButton("中心", self), QRadioButton("右上角", self)
        )  # 选择

        self.aniSpeedSet = QSpinBox()
        self.isTopSet = QCheckBox("窗口是否置顶", self)
        self.autoStartupSet = QCheckBox("程序自启动", self)
        self.isLockedSet = QCheckBox("启动时锁定窗口", self)
        self.alwaysOnEdgeSet = QCheckBox("窗口永远处于边缘", self)
        self.collapseOnOpenSet = QCheckBox("打开文件夹/应用时折叠窗口", self)

        self.n_reset = QPushButton("重置", self)
        self.n_winXSet = QSpinBox()
        self.n_winYSet = QSpinBox()
        self.n_titleIconSizeSet = QSpinBox()
        self.n_appIconSizeSet = QSpinBox()
        self.demonstrationItem = QWidget(self)

        self.n_opacitySet = QSpinBox()

        self.c_reset = QPushButton("重置", self)
        self.c_winXSet = QSpinBox()
        self.c_winYSet = QSpinBox()
        self.c_opacitySet = QSpinBox()

        self.addDependencyWidget = AddDependencyWidget(self.config["windows"]["identifyGroups"], self)

    def __buildControl(self):
        """构建控件"""
        btnGroup_1 = QButtonGroup(self)  # 创建组
        for i in self.themeSet: btnGroup_1.addButton(i)

        btnGroup_2 = QButtonGroup(self)  # 创建组
        for i in self.placementSetRadios: btnGroup_2.addButton(i)

        # 需要先获取窗口宽度
        self.placementSetEdit.setRange(0, self.screenSize.width() - self.config["normal"]["winSize"][0])
        self.placementSetEdit.setSingleStep(10)
        self.placementSetEdit.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.aniSpeedSet.setRange(100, 1500)
        self.aniSpeedSet.setSingleStep(50)
        self.aniSpeedSet.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.aniSpeedSet.setSuffix("ms")

        # normal
        self.n_winXSet.setRange(100, self.screenSize.width() // 2)
        self.n_winXSet.setSingleStep(10)
        self.n_winXSet.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.n_winXSet.setSuffix("px")

        self.n_winYSet.setRange(100, self.screenSize.height() // 3)
        self.n_winYSet.setSingleStep(10)
        self.n_winYSet.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.n_winYSet.setSuffix("px")

        self.n_titleIconSizeSet.setRange(16, 128)
        self.n_titleIconSizeSet.setSingleStep(1)
        self.n_titleIconSizeSet.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.n_titleIconSizeSet.setSuffix("px")

        self.n_appIconSizeSet.setRange(16, 128)
        self.n_appIconSizeSet.setSingleStep(1)
        self.n_appIconSizeSet.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.n_appIconSizeSet.setSuffix("px")

        self.demonstrationItem.setObjectName("item")
        lyt = QVBoxLayout(self.demonstrationItem)
        lyt.setSpacing(0)
        lyt.setContentsMargins(0, 2, 0, 2)
        self.itemIcon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        self.itemIconLabel = QLabel(self)
        self.itemIconLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.itemLabel = QLabel("示例图标", self)
        lyt.addWidget(self.itemIconLabel, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        lyt.addWidget(self.itemLabel, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.n_opacitySet.setRange(10, 100)
        self.n_opacitySet.setSingleStep(5)
        self.n_opacitySet.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.n_opacitySet.setSuffix("%")

        # collapsible
        self.c_winXSet.setRange(20, self.parent.width())
        self.c_winXSet.setSingleStep(10)
        self.c_winXSet.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.c_winXSet.setSuffix("px")

        self.c_winYSet.setRange(4, self.screenSize.height() // 10)
        self.c_winYSet.setSingleStep(1)
        self.c_winYSet.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.c_winYSet.setSuffix("px")

        self.c_opacitySet.setRange(10, 100)
        self.c_opacitySet.setSingleStep(5)
        self.c_opacitySet.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.c_opacitySet.setSuffix("%")

    def __initConfig(self):
        if self.config["windows"]["theme"] == "dark": self.themeSet[0].setChecked(True)
        else: self.themeSet[1].setChecked(True)

        placement = self.config["windows"]["placement"]
        if isinstance(placement, str):
            if placement == "center": self.placementSetRadios[1].setChecked(True)
            elif placement == "right": self.placementSetRadios[2].setChecked(True)
            else: self.placementSetRadios[0].setChecked(True)  # 默认left
        elif isinstance(placement, int or float):
            self.placementSetEdit.setValue(int(placement))

        self.aniSpeedSet.setValue(int(self.config["windows"]["aniSpeed"]))
        self.isTopSet.setChecked(self.config["windows"]["isTop"])
        self.autoStartupSet.setChecked(self.__isAutoStartup())
        self.isLockedSet.setChecked(self.config["windows"]["isLocked"])
        self.alwaysOnEdgeSet.setChecked(self.config["windows"]["alwaysOnEdge"])
        self.collapseOnOpenSet.setChecked(self.config["windows"]["collapseOnOpen"])

        self.n_winXSet.setValue(self.config["normal"]["winSize"][0])
        self.n_winYSet.setValue(self.config["normal"]["winSize"][1])
        self.n_titleIconSizeSet.setValue(self.config["normal"]["titleIconSize"])
        self.n_appIconSizeSet.setValue(self.config["normal"]["appIconSize"])
        self.__setDemonstrationItem(self.config["normal"]["appIconSize"])
        self.n_opacitySet.setValue(self.config["normal"]["opacity"] * 100)

        self.c_winXSet.setValue(self.config["collapsible"]["winSize"][0])
        self.c_winYSet.setValue(self.config["collapsible"]["winSize"][1])
        self.c_opacitySet.setValue(self.config["collapsible"]["opacity"] * 100)

    def __connectControl(self):
        if self.parent is None: return

        self.themeSet[0].clicked.connect(lambda: self.__setTheme("dark"))
        self.themeSet[1].clicked.connect(lambda: self.__setTheme("light"))

        self.placementSetEdit.valueChanged.connect(lambda value: self.__setPlacement(value))
        self.placementSetRadios[0].clicked.connect(lambda: self.__setPlacement("left"))
        self.placementSetRadios[1].clicked.connect(lambda: self.__setPlacement("center"))
        self.placementSetRadios[2].clicked.connect(lambda: self.__setPlacement("right"))

        self.aniSpeedSet.valueChanged.connect(lambda value: self.__setAniSpeed(value))

        self.isTopSet.toggled.connect(lambda checked: self.__setTop(checked))
        self.autoStartupSet.toggled.connect(self.__setAutoStartup)
        self.isLockedSet.toggled.connect(lambda checked: self.__setLock(checked))
        self.alwaysOnEdgeSet.toggled.connect(lambda checked: self.__setAlwaysOnEdge(checked))
        self.collapseOnOpenSet.toggled.connect(lambda checked: self.__setCollapseOnOpen(checked))

        self.n_reset.clicked.connect(lambda: self.__resetConfig("normal"))
        self.n_winXSet.valueChanged.connect(lambda value: self.__setWinSize("normal", 0, value))
        self.n_winYSet.valueChanged.connect(lambda value: self.__setWinSize("normal", 1, value))
        self.n_titleIconSizeSet.valueChanged.connect(lambda value: self.__setNTitleIconSize(value))
        self.n_appIconSizeSet.valueChanged.connect(lambda value: self.__setNAppIconSize(value))
        self.n_opacitySet.valueChanged.connect(lambda value: self.__setOpacity("normal", value))

        self.c_reset.clicked.connect(lambda: self.__resetConfig("collapsible"))
        self.c_winXSet.valueChanged.connect(lambda value: self.__setWinSize("collapsible", 0, value))
        self.c_winYSet.valueChanged.connect(lambda value: self.__setWinSize("collapsible", 1, value))
        self.c_opacitySet.valueChanged.connect(lambda value: self.__setOpacity("collapsible", value))

    def __buildLyt(self):
        """构建布局"""
        self.mainLayout.addTitle("基础设置")
        self.mainLayout.addColWidget(QLabel("主题选择"))
        self.mainLayout.addColWidget(self.themeSet[0])
        self.mainLayout.addColWidget(self.themeSet[1])
        self.mainLayout.addRow()

        self.mainLayout.addColWidget(QLabel("初始启动位置"))
        self.mainLayout.addColWidget(self.placementSetEdit, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColSpacer(1)
        for radio in self.placementSetRadios:
            self.mainLayout.addColWidget(radio)
        self.mainLayout.addRow()

        self.mainLayout.addColWidget(QLabel("动画播放速度"))
        self.mainLayout.addColWidget(self.aniSpeedSet, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(self.isTopSet, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(self.autoStartupSet, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(self.isLockedSet, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(self.alwaysOnEdgeSet, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(self.collapseOnOpenSet, 2)

        self.mainLayout.addTitle("正常窗口设置")
        self.mainLayout.addColWidget(QLabel("窗口宽度"))
        self.mainLayout.addColWidget(self.n_winXSet, 2)
        self.mainLayout.addColWidget(self.n_reset)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(QLabel("窗口高度"))
        self.mainLayout.addColWidget(self.n_winYSet, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(QLabel("标题栏图标大小"))
        self.mainLayout.addColWidget(self.n_titleIconSizeSet, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(QLabel("应用图标大小"))
        self.mainLayout.addColWidget(self.n_appIconSizeSet, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(self.demonstrationItem)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(QLabel("窗口不透明度"))
        self.mainLayout.addColWidget(self.n_opacitySet, 2)

        self.mainLayout.addTitle("折叠窗口设置")
        self.mainLayout.addColWidget(QLabel("窗口宽度"))
        self.mainLayout.addColWidget(self.c_winXSet, 2)
        self.mainLayout.addColWidget(self.c_reset)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(QLabel("窗口高度"))
        self.mainLayout.addColWidget(self.c_winYSet, 2)
        self.mainLayout.addRow()
        self.mainLayout.addColWidget(QLabel("窗口不透明度"))
        self.mainLayout.addColWidget(self.c_opacitySet, 2)

        self.mainLayout.addTitle("添加可识别项")
        self.mainLayout.addColWidget(self.addDependencyWidget, 4)

    def writeConfig(self) -> bool:
        if self.parent is None: return
        if self.config == self.newConfig: return
        try:
            with open(self.configPath, "w", encoding="utf-8") as f:
                json.dump(self.newConfig, f, indent=4)
        except Exception as e:
            self.logging.write(f"写入配置信息错误：{e}", "error")
            return False
        self.config = copy.deepcopy(self.newConfig)
        return True

    def changeIdentify(self, type_1: str, type_2: str) -> None:
        if type_1 == "add":   self.newConfig["windows"]["identifyGroups"].append(type_2)
        elif type_1 == "del": self.newConfig["windows"]["identifyGroups"].remove(type_2)
        self.parent.changeIdentify(type_1, type_2)

    @staticmethod
    def __isAutoStartup() -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ  # 只读权限
            )
            value, reg_type = winreg.QueryValueEx(key, "CollapsiblePanel")
            winreg.CloseKey(key)
            return True
        except Exception as e:  # 不存在
            return False

    def __setTheme(self, theme: str):
        self.parent.switchTheme(theme)
        self.newConfig["windows"]["theme"] = theme

    def __setPlacement(self, value: int | str):
        self.parent.setPlacement(value)
        self.newConfig["windows"]["placement"] = value

    def __setAniSpeed(self, value: int):
        self.parent.setAniSpeed(value)
        self.newConfig["windows"]["aniSpeed"] = value

    def __setTop(self, state: bool):
        self.parent.setWindowsTop(state)
        self.newConfig["windows"]["isTop"] = state

    def __setAutoStartup(self):
        def set_autostart(state: bool) -> bool:
            try:
                # 获取当前程序所在目录
                if getattr(sys, 'frozen', False):  # 已打包
                    path = os.path.abspath(sys.executable)
                else:  # py脚本
                    path = os.path.abspath(sys.argv[0])

                # 打开注册表
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_WRITE
                )

                if state:
                    winreg.SetValueEx(key, "CollapsiblePanel", 0, winreg.REG_SZ, f'"{path}"')
                else:  # 删除注册表项
                    try:
                        winreg.DeleteValue(key, "CollapsiblePanel")
                    except Exception: pass  # 如果不存在就不管

                winreg.CloseKey(key)
                return True

            except Exception as e:
                self.logging.write("设置程序自启动失败，错误信息：{e}", "error")
                return False

        state = not self.__isAutoStartup()
        if not set_autostart(state):
            self.parent.setHasActivePopup(True)
            QApplication.beep()
            QMessageBox.information(self.parent, "提示", "设置程序自启动失败，详细请查看日志")
            self.parent.setHasActivePopup(False)
            self.autoStartupSet.setChecked(False)
            self.autoStartupSet.setEnabled(False)
            self.newConfig["windows"]["autoStartup"] = False

    def __setLock(self, state: bool):
        self.parent.setLock(state)
        self.newConfig["windows"]["isLocked"] = state

    def __setAlwaysOnEdge(self, state: bool):
        self.parent.setAlwaysOnEdge(state)
        self.newConfig["windows"]["alwaysOnEdge"] = state

    def __setCollapseOnOpen(self, state: bool):
        self.parent.setCollapseOnOpen(state)
        self.newConfig["windows"]["collapseOnOpen"] = state

    def __setWinSize(self, arg_1: str, arg_2: int, value: int):
        self.parent.setWindowsSize(arg_1, arg_2, value)
        self.newConfig[arg_1]["winSize"][arg_2] = value
        if arg_1 == "normal":
            self.setMaximumHeight(self.n_winYSet.value() - self.n_titleIconSizeSet.value())
            self.placementSetEdit.setMaximum(self.screenSize.width() - value)
        else:
            self.c_winXSet.setMaximum(self.parent.width())

    def __setNTitleIconSize(self, value: int):
        self.parent.setNTitleIconSize(value)
        self.newConfig["normal"]["titleIconSize"] = value

    def __setNAppIconSize(self, value: int):
        self.__setDemonstrationItem(value)
        self.parent.setNAppIconSize(value)
        self.newConfig["normal"]["appIconSize"] = value

    def __setDemonstrationItem(self, appIconSize: int):
        def calcFontSize(size: int) -> int:
            if size <= 48: fontSize = int(size * 0.4)
            elif size <= 96: fontSize = int(size * 0.35)
            else: fontSize = int(size * 0.3)

            fontSize = max(8, min(fontSize, 72))
            return fontSize

        self.itemIconLabel.setPixmap(self.itemIcon.pixmap(appIconSize, appIconSize))
        self.itemIconLabel.setFixedSize(appIconSize * 2.5, appIconSize * 2)
        font = self.itemLabel.font()
        font.setPointSize(calcFontSize(appIconSize))
        self.itemLabel.setFont(font)

    def __setOpacity(self, arg_1: str, value: int):
        value = round(value / 100, 2)
        self.parent.setOpacity(arg_1, value)
        self.newConfig[arg_1]["opacity"] = value

    def __resetConfig(self, arg_1: str):
        config = self.config[arg_1]
        if arg_1 == "normal":
            self.n_winXSet.setValue(config["winSize"][0])
            self.n_winYSet.setValue(config["winSize"][1])
            self.n_titleIconSizeSet.setValue(config["titleIconSize"])
            self.n_appIconSizeSet.setValue(config["appIconSize"])
            self.n_opacitySet.setValue(config["opacity"] * 100)
        elif arg_1 == "collapsible":
            self.c_winXSet.setValue(config["winSize"][0])
            self.c_winYSet.setValue(config["winSize"][1])
            self.c_opacitySet.setValue(config["opacity"] * 100)
        self.newConfig[arg_1] = copy.deepcopy(config)
