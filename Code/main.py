import os
import sys
import time
import ctypes.wintypes as wintypes

RecordLog = True  # 记录日志

if getattr(sys, 'frozen', False):
    path = os.path.dirname(sys.executable)
# 开发环境：脚本所在目录
else:
    path = os.path.dirname(os.path.abspath(__file__))

path = os.path.dirname(path)
LogPath = os.path.join(path, "Cache\\CollapsiblePanel.log")  # 日志路径


class Logging:
    def __init__(self):
        if not RecordLog: return
        try:
            self.file = open(LogPath, "a", encoding="utf-8")
            self.file.write(time.strftime("%Y年%m月%d日 %H:%M:%S\n", time.localtime(time.time())))
        except Exception as e:
            self.file = open(LogPath, "w", encoding="utf-8")  # 创建新文件
            self.file.write(time.strftime("%Y年%m月%d日 %H:%M:%S\n", time.localtime(time.time())))
            self.write(e, "error")

    def write(self, message: str, type_: str):
        if not RecordLog: return
        self.file.write(f"\t[{type_}]: {message}\n")

    def close(self, exit_code: int = 0) -> None:
        if not RecordLog: return
        self.write(f"程序退出，退出代码为{exit_code}", "info")
        self.file.close()


logging = Logging()

ConfigPath = os.path.join(path, "Assets\\data\\config.json")           # 配置路径
IconPathRoot = os.path.join(path, "Assets\\icons")                     # 图标根路径
QssPathRoot = os.path.join(path, "Assets\\styles")                     # qss根路径
AppMappingPath = os.path.join(path, "Assets\\data\\app_mapping.json")  # app映射表路径

import json
import pylnk3
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QGridLayout
from PySide6.QtCore import Qt, QRect, QSize, QTimer, QPropertyAnimation, QEasingCurve

from appWidget import AppWidget
from controlWidget import ControlWidget
from settingsWidget import SettingsWidget

ScreenSize: QSize = None  # 屏幕尺寸


# 主窗口
class CollapsiblePanel(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        # 系统参数
        try:
            win_config: dict = config["windows"]
            self.theme = win_config.get("theme", "dark")
            if self.theme not in ["dark", "light"]: self.theme = "dark"  # 默认dark
            self.placement: str | int = win_config.get("placement", "center")
            self.aniSpeed: int = win_config.get("aniSpeed", 200)
            self.isTop = win_config.get("isTop", True)
            self.isLocked = win_config.get("isLocked", False)
            self.alwaysOnEdge = win_config.get("alwaysOnEdge", False)
            self.collapseOnOpen = win_config.get("collapseOnOpen", True)  # 打开程序时折叠窗口
            self.identifyGroups = win_config.get("identifyGroups", [".exe"])
            # 正常状态窗口参数
            n_config: dict = config["normal"]
            self.n_winSize = n_config.get("winSize", [500, 240])
            self.n_titleIconSize = n_config.get("titleIconSize", 22)
            self.n_appIconSize = n_config.get("appIconSize", 32)
            self.n_opacity = n_config.get("opacity", 0.8)
            # 折叠状态窗口参数
            c_config = config["collapsible"]
            self.c_winSize = c_config.get("winSize", [200, 6])
            self.c_opacity = c_config.get("opacity", 0.6)
        except Exception as e: raise f"config.json配置'{e}'错误"
        # 变量
        self.winIsExpand = True             # 窗口展开中
        self.settingsIsExpand = False       # 设置界面展开中
        self.hasDraggingWidget = False      # 有控件正在拖动
        self.hasActivePopup = False         # 有弹出式窗口
        self.firstStart = True              # 初始启动
        self.isCollapsibleFromUser = False  # 用户手动折叠窗口

        self.offset: int = (self.n_winSize[0] - self.c_winSize[0]) // 2  # 正常窗口和折叠窗口的偏移大小
        self.geometriesCache = {"collapsed": QRect(0, 0, 0, 0), "expanded": QRect(0, 0, 0, 0)}  # 各状态geometry的缓存
        # app映射表
        try:
            with open(AppMappingPath, "r", encoding="utf-8") as f:
                self.appMapping = json.load(f)
        except FileNotFoundError:
            with open(AppMappingPath, "w", encoding="utf-8") as f:
                self.appMapping = {"folder": {}, "exec": {}}
                json.dump(self.appMapping, f)
        # 主控件
        self.mainWidget = QWidget(self)
        self.mainLayout = QVBoxLayout(self.mainWidget)
        self.mainWidget.setLayout(self.mainLayout)
        self.setCentralWidget(self.mainWidget)
        # 监视栏
        self.monitorWidget = QWidget(self)
        # 操作区
        self.activeWidget = QWidget(self)
        self.activeLayout = QGridLayout(self.activeWidget)
        # 功能栏
        self.controlWidget = ControlWidget(IconPathRoot, self.n_titleIconSize, self.theme, ScreenSize, self)
        # 设置界面
        self.settingsWidget = SettingsWidget(ConfigPath, config, ScreenSize, logging, self)
        # 文件滚动栏
        self.folderWidget = AppWidget("folder", self.n_appIconSize, self.appMapping, self.collapseOnOpen, self)
        # 可执行文件滚动栏
        self.execWidget = AppWidget("exec", self.n_appIconSize, self.appMapping, self.collapseOnOpen, self)
        # 动画
        self.windowsAni = QPropertyAnimation(self, b"geometry")
        self.settingsAni = QPropertyAnimation(self.settingsWidget, b"maximumHeight")
        # 计时器
        if not self.isLocked:
            self.startupAniTimer = QTimer()  # 启动动画计时器
            self.startupAniTimer.timeout.connect(self.__startupAni)
            self.startupAniTimer.setSingleShot(True)
            self.startupAniTimer.start(1000)
        else: self.startupAniTimer = None

        self.saveAppMappingTimer = QTimer()  # 保存软件样式表计时器
        self.saveAppMappingTimer.timeout.connect(self.__saveAppMapping)
        self.saveAppMappingTimer.setSingleShot(True)
        self.saveAppMappingTimer.start(5000)
        # 构建
        self.__init()

    def nativeEvent(self, eventType, message):
        if os.name == "nt":
            if eventType == b"windows_generic_MSG":
                msg = wintypes.MSG.from_address(message.__int__())
                if msg.message == 0x0011:  # 系统关机
                    logging.write("系统关机，已自动保存数据", "info")
                    self.close()
                    return True, 1
        return super().nativeEvent(eventType, message)

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path: str = url.toLocalFile()
                if path.lower().endswith(tuple(self.identifyGroups + [".lnk"])) or os.path.isdir(path):
                    event.accept()
        else: event.ignore()

    def dropEvent(self, event) -> bool:
        """处理放下事件"""
        mime = event.mimeData()
        for url in mime.urls():
            path = url.toLocalFile()
            if not path: continue
            if path in self.folderWidget.paths + self.execWidget.paths: continue  # 已存在

            if path.lower().endswith(".lnk"):
                try:
                    targetPath = pylnk3.parse(path).path
                except Exception as e:
                    logging.write(f"提取路径:‘{path}'的lnk文件的目标位置失败，错误信息：{e}", "warning")
                    # 添加快捷方式到 folder
                    self.addItem("folder", self.folderWidget.getAppName(path), path)
                    return
                if targetPath in self.folderWidget.paths: continue
                if os.path.isdir(targetPath):
                    self.addItem("folder", self.folderWidget.getAppName(path), targetPath)
                else:
                    self.addItem("exec", self.execWidget.getAppName(path), targetPath)
                continue
            elif os.path.isdir(path):
                self.addItem("folder", self.folderWidget.getAppName(path), path)
            elif path.lower().endswith(tuple(self.identifyGroups)):
                self.addItem("exec", self.execWidget.getAppName(path), path)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        if self.startupAniTimer:
            self.startupAniTimer.stop()
            self.startupAniTimer = None
            return

        if self.winIsExpand or self.__isProhibitAni(): return
        self.expandWindowsFromSystem()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)

        # 锁定、拖拽状态与有弹窗或本就折叠状态时不折叠
        if not self.winIsExpand or self.__isProhibitAni(): return
        self.collapseWindowsFromSystem()

    def close(self) -> None:
        super().close()
        if self.placement == "top":
            self.settingsWidget.newConfig["windows"]["placement"] = self.pos().x()

        self.settingsWidget.writeConfig()
        self.__saveAppMapping()
        QApplication.quit()

    def __init(self) -> None:
        self.setAcceptDrops(True)

        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)
        self.activeLayout.setContentsMargins(5, 5, 5, 5)
        self.activeLayout.setSpacing(2)

        self.mainLayout.addWidget(
            self.monitorWidget, 0,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.mainLayout.addWidget(self.activeWidget, 1)

        self.activeLayout.addWidget(self.controlWidget, 0, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignTop)
        self.activeLayout.addWidget(self.settingsWidget, 1, 0, 1, 2)
        self.activeLayout.addWidget(self.folderWidget, 2, 0, 1, 1)
        self.activeLayout.addWidget(self.execWidget, 2, 1, 1, 1)

        self.activeLayout.setRowStretch(2, 1)

        self.monitorWidget.hide()
        self.settingsWidget.hide()

        self.__init_monitorWidget()
        self.__init_ani()

        self.setWindowsSize("normal", 0, self.n_winSize[0])
        self.setWindowsSize("normal", 1, self.n_winSize[1])

        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowsTop(self.isTop)
        self.switchTheme(self.theme)
        self.setWindowOpacity(self.n_opacity)

    def __init_monitorWidget(self) -> None:
        self.monitorWidget.setObjectName("MonitorWidget")

        lyt = QVBoxLayout()
        self.monitorWidget.setLayout(lyt)

        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.addStretch(1)  # 占位

        self.monitorWidget.setWindowOpacity(self.c_opacity)
        self.monitorWidget.setFixedSize(self.c_winSize[0], self.c_winSize[1])

    def __init_ani(self) -> None:
        self.windowsAni.setDuration(self.aniSpeed)
        self.windowsAni.setEasingCurve(QEasingCurve.Type.OutCurve)

        self.settingsAni.setDuration(self.aniSpeed)
        self.settingsAni.setEasingCurve(QEasingCurve.Type.OutCurve)

    def switchTheme(self, theme: str) -> None:
        if self.firstStart: self.firstStart = False
        elif theme == self.theme: return

        with open(f"{QssPathRoot}\\{theme}.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())
        self.controlWidget.switchTheme(theme)
        self.theme = theme

    def addItem(self, type_: str, name: str, path: str) -> None:
        if type_ == "folder": self.folderWidget.addItem(name, path)
        elif type_ == "exec": self.execWidget.addItem(name, path)

        self.appMapping[type_][name] = path
        self.saveAppMappingTimer.start()

    def delItem(self, type_: str, name: str) -> None:
        if type_ not in ["folder", "exec"]: return
        del self.appMapping[type_][name]
        self.saveAppMappingTimer.start()

    def clearItems(self, type_: str) -> None:
        if type_ not in ["folder", "exec"]: return
        self.appMapping[type_] = {}
        self.saveAppMappingTimer.start()

    def swapItems(self, type_: str, name1: str, name2: str) -> None:
        def swapKeys(d, key1, key2) -> dict:  # 交换键的位置
            if key1 in d and key2 in d:
                keys = list(d.keys())
                idx1, idx2 = keys.index(key1), keys.index(key2)
                keys[idx1], keys[idx2] = keys[idx2], keys[idx1]
                return {k: d[k] for k in keys}
            return d.copy()
        self.appMapping[type_] = swapKeys(self.appMapping[type_], name1, name2)
        self.saveAppMappingTimer.start()

    def collapseWindowsFromSystem(self) -> None:
        """由系统折叠窗口"""
        self.windowsAni.setStartValue(self.geometriesCache["expanded"])
        self.windowsAni.setEndValue(self.geometriesCache["collapsed"])
        self.windowsAni.setDuration(self.aniSpeed)
        self.windowsAni.start()

        self.activeWidget.hide()
        self.monitorWidget.show()
        self.winIsExpand = False
        self.setWindowOpacity(self.c_opacity)

    def collapseWindowsFromUser(self) -> None:
        self.isCollapsibleFromUser = self.isLocked
        if self.isLocked: self.isLocked = False  # 先解锁，不然折叠后展开不了窗口
        self.collapseWindowsFromSystem()

    def expandWindowsFromSystem(self) -> None:
        """由系统展开窗口"""
        self.windowsAni.setStartValue(self.geometriesCache["collapsed"])
        self.windowsAni.setEndValue(self.geometriesCache["expanded"])
        self.windowsAni.setDuration(self.aniSpeed)
        self.windowsAni.start()

        # 不是设置界面，隐藏monitorWidget
        if not self.settingsIsExpand: self.monitorWidget.hide()
        # 上次窗口折叠是因为用户手动点击
        if self.isCollapsibleFromUser:
            self.controlWidget.setLock(self.isCollapsibleFromUser)
            self.isCollapsibleFromUser = False

        self.activeWidget.show()
        self.winIsExpand = True
        self.setWindowOpacity(self.n_opacity)

    def collapseSettings(self) -> None:
        def __finished():
            self.settingsWidget.hide()
            self.folderWidget.show()
            self.execWidget.show()

        self.settingsAni.setStartValue(self.n_winSize[1] - self.n_titleIconSize)
        self.settingsAni.setEndValue(0)

        self.settingsAni.finished.disconnect()
        self.settingsAni.finished.connect(__finished)
        self.settingsAni.setDuration(self.aniSpeed)
        self.settingsAni.start()

        self.monitorWidget.hide()
        self.settingsIsExpand = False

    def expandSettings(self) -> None:
        self.settingsAni.setStartValue(0)
        self.settingsAni.setEndValue(self.n_winSize[1] - self.n_titleIconSize)

        self.settingsAni.finished.disconnect()
        self.settingsAni.setDuration(self.aniSpeed)
        self.settingsAni.start()

        self.folderWidget.hide()
        self.execWidget.hide()
        self.monitorWidget.show()
        self.settingsWidget.show()
        self.settingsIsExpand = True

    def changeIdentify(self, type_1: str, type_2: str) -> None:
        """
        改变依赖
        :param type_1:  "add", "del"
        :param type_2:  ".???", 如".exe"
        """
        if type_1 == "add":   self.identifyGroups.append(type_2)
        elif type_1 == "del": self.identifyGroups.remove(type_2)

    def setAniSpeed(self, value: int) -> None: self.aniSpeed = value
    def setAlwaysOnEdge(self, state: bool) -> None: self.alwaysOnEdge = state
    def setHasDraggingWidget(self, flag: bool) -> None: self.hasDraggingWidget = flag
    def setHasActivePopup(self, flag: bool) -> None: self.hasActivePopup = flag
    def setNTitleIconSize(self, titleIconSize: int) -> None: self.controlWidget.setNTitleIconSize(titleIconSize)
    def setLock(self, flag: bool) -> None: self.isLocked = flag
    def setPlacementSpinBoxBlockSig(self, flag: bool) -> None: self.settingsWidget.placementSetEdit.blockSignals(flag)
    def setPlacementSpinBoxValue(self, value: int) -> None: self.settingsWidget.placementSetEdit.setValue(value)

    def setCollapseOnOpen(self, flag: bool) -> None:
        self.folderWidget.collapseOnOpen = flag
        self.execWidget.collapseOnOpen = flag
        # self.collapseOnOpen = flag

    def setNAppIconSize(self, appIconSize: int) -> None:
        self.folderWidget.setNAppIconSize(appIconSize)
        self.execWidget.setNAppIconSize(appIconSize)
        # self.n_appIconSize = appIconSize

    def setOpacity(self, arg_1: str, value: float) -> None:
        if arg_1 == "normal":
            self.n_opacity = value
            self.setWindowOpacity(self.n_opacity)
        elif arg_1 == "collapsible":
            self.c_opacity = value
            self.monitorWidget.setWindowOpacity(self.c_opacity)

    def setPlacement(self, placement: str | int) -> None:
        """设置方向，y轴总是为0，参数：top, left, center, right"""
        if self.winIsExpand: winSize = self.n_winSize
        else: winSize = self.c_winSize

        if isinstance(placement, str):
            if placement == "top": self.move(self.pos().x(), 0)
            elif placement == "left": self.move(0, 0)
            elif placement == "center": self.move(ScreenSize.width() / 2 - winSize[0] / 2, 0)
            elif placement == "right": self.move(ScreenSize.width() - winSize[0], 0)
        else: self.move(placement, 0)

        self.placement = placement
        self.updateGeometriesState()

    def setWindowsSize(self, arg_1: str, arg_2: int, value: int) -> None:
        """
        设置窗口大小
        :param arg_1: "normal" / "collapsible"
        :param arg_2: 0: width / 1: height
        :param value: 值
        """
        lastValue: int
        if arg_1 == "normal":
            lastValue = self.n_winSize[arg_2]
            self.n_winSize[arg_2] = value
            if self.winIsExpand:
                self.resize(self.n_winSize[0], self.n_winSize[1])
        elif arg_1 == "collapsible":
            lastValue = self.n_winSize[arg_2]
            self.c_winSize[arg_2] = value
            self.monitorWidget.setFixedSize(self.c_winSize[0], self.c_winSize[1])
        else: raise "arg_1为未知参数"

        self.offset: int = (self.n_winSize[0] - self.c_winSize[0]) // 2
        if isinstance(self.placement, int):
            if self.firstStart: self.setPlacement(self.placement)  # 初始启动，直接设置初始位置
            else: self.move(self.pos().x() - (value - lastValue), 0)  # 偏移窗口
        elif isinstance(self.placement, str):
            self.setPlacement(self.placement)

        self.updateGeometriesState()

    def setWindowsTop(self, state: bool = None) -> None:
        """设置置顶，如果state是None，则取反"""
        if state is None: state = not self.isTop

        flags = self.windowFlags()
        if state: self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else: self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        self.isTop = state
        self.show()

    def updateGeometriesState(self) -> None:
        """更新各状态的geometry"""
        expanded_x = self.pos().x() - (0 if self.winIsExpand else self.offset)
        collapsed_x = self.pos().x() + (self.offset if self.winIsExpand else 0)

        self.geometriesCache.update({
            "expanded": QRect(expanded_x, 0, self.n_winSize[0], self.n_winSize[1]),
            "collapsed": QRect(collapsed_x, 0, self.c_winSize[0], self.c_winSize[1])
        })

    def __isProhibitAni(self) -> bool: return self.isLocked or self.hasDraggingWidget or self.hasActivePopup

    def __saveAppMapping(self) -> None:
        with open(AppMappingPath, "w", encoding="utf-8") as f:
            json.dump(self.appMapping, f, ensure_ascii=False, indent=4)

    def __startupAni(self) -> None:
        self.startupAniTimer = None
        self.collapseWindowsFromSystem()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ScreenSize = app.primaryScreen().size()
    # 读取配置
    try:
        with open(ConfigPath, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        logging.write(f"加载config.json数据发生错误：{e}", "error")
        logging.close(1)
        sys.exit(1)
    # 启动程序
    try:
        window = CollapsiblePanel(config=config)
        window.show()
        app.exec()
        logging.close()
        sys.exit()
    except Exception as e:
        logging.write(e, "error")
        logging.close(1)
        sys.exit(1)
