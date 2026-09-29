import ScreenCloud
from PythonQt.QtCore import QFile, QSettings, QUrl
from PythonQt.QtGui import QWidget, QDialog, QDesktopServices, QMessageBox
from PythonQt.QtUiTools import QUiLoader
import requests, time, os

###############################
## This is a temporary fix, should be removed when a newer python version is used ##
import logging
logging.captureWarnings(True)
###############################


class MareUploader():
    EXPIRE_OPTIONS = [
        ("1h",  "1h"),
        ("6h",  "6h"),
        ("12h", "12h"),
        ("1d",  "1d"),
        ("3d",  "3d"),
        ("7d",  "7d"),
    ]

    def __init__(self):
        self.uil = QUiLoader()
        self.loadSettings()

    def showSettingsUI(self, parentWidget):
        self.parentWidget = parentWidget
        self.settingsDialog = self.uil.load(QFile(workingDir + "/settings.ui"), parentWidget)

        combo = self.settingsDialog.group_expire.combo_expire
        combo.clear()
        for label, _value in self.EXPIRE_OPTIONS:
            combo.addItem(label)

        self.settingsDialog.group_name.input_name.connect("textChanged(QString)", self.nameFormatEdited)
        self.settingsDialog.connect("accepted()", self.saveSettings)

        self.loadSettings()
        self.settingsDialog.group_clipboard.radio_dontcopy.setChecked(not self.copyLink)
        self.updateUi()
        self.settingsDialog.open()

    def updateUi(self):
        if self.host == "mare.by":
            self.settingsDialog.group_host.radio_mare.setChecked(True)
        else:
            self.settingsDialog.group_host.radio_temp_mare.setChecked(True)

        is_temp = (self.host == "temp.mare.by")
        self.settingsDialog.group_expire.setEnabled(is_temp)
        combo = self.settingsDialog.group_expire.combo_expire
        for i, (label, value) in enumerate(self.EXPIRE_OPTIONS):
            if value == self.expire:
                combo.setCurrentIndex(i)
                break

        self.settingsDialog.group_name.input_name.setText(self.nameFormat)
        self.settingsDialog.adjustSize()

    def loadSettings(self):
        settings = QSettings()
        settings.beginGroup("uploaders")
        settings.beginGroup("mare")
        self.host = settings.value("host", "temp.mare.by")
        self.expire = settings.value("expire", "1d")
        self.copyLink = settings.value("copy-link", "true") in ['true', True]
        self.nameFormat = settings.value("name-format", "Screenshot at %H:%M:%S")
        settings.endGroup()
        settings.endGroup()

    def saveSettings(self):
        settings = QSettings()
        settings.beginGroup("uploaders")
        settings.beginGroup("mare")
        settings.setValue("host", "mare.by" if self.settingsDialog.group_host.radio_mare.checked else "temp.mare.by")
        settings.setValue("expire", self.EXPIRE_OPTIONS[self.settingsDialog.group_expire.combo_expire.currentIndex][1])
        settings.setValue("copy-link", not self.settingsDialog.group_clipboard.radio_dontcopy.checked)
        settings.setValue("name-format", self.settingsDialog.group_name.input_name.text)
        settings.endGroup()
        settings.endGroup()

    def isConfigured(self):
        self.loadSettings()
        return True

    def getFilename(self):
        self.loadSettings()
        return ScreenCloud.formatFilename(self.nameFormat)

    def upload(self, screenshot, name):
        self.loadSettings()

        timestamp = time.time()
        try:
            tmpDir = QDesktopServices.storageLocation(QDesktopServices.TempLocation)
        except AttributeError:
            from PythonQt.QtCore import QStandardPaths  # fix for Qt5
            tmpDir = QStandardPaths.writableLocation(QStandardPaths.TempLocation)

        ext = ScreenCloud.getScreenshotFormat()
        tmpFilename = tmpDir + "/" + ScreenCloud.formatFilename(str(timestamp)) + "." + ext
        screenshot.save(QFile(tmpFilename), ext)

        if self.host == "temp.mare.by":
            url = "https://temp.mare.by/api/upload"
            params = {"output": "text", "expire": self.expire}
        else:
            url = "https://mare.by/api/upload"
            params = {"output": "text"}

        try:
            with open(tmpFilename, "rb") as fh:
                files = {"files[]": (os.path.basename(tmpFilename), fh, "image/" + ext)}
                resp = requests.post(url, params=params, files=files, timeout=60)
        except Exception as e:
            ScreenCloud.setError("Failed to upload to " + self.host + ". " + str(e))
            return False

        if resp.status_code != 200:
            ScreenCloud.setError("Failed to upload to %s. HTTP %d: %s"
                                 % (self.host, resp.status_code, resp.text[:300]))
            return False

        direct_link = resp.text.strip()

        if not direct_link.startswith("http"):
            ScreenCloud.setError("Unexpected response from %s: %s"
                                 % (self.host, direct_link[:200]))
            return False

        if self.copyLink:
            ScreenCloud.setUrl(direct_link)
        return True

    def nameFormatEdited(self, nameFormat):
        self.settingsDialog.group_name.label_example.setText(ScreenCloud.formatFilename(nameFormat, False))