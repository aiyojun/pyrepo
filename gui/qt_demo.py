import sys

from PyQt5.QtCore import Qt, QTimer, QFileSystemWatcher, pyqtSignal, QDir, QDateTime
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QFontMetrics
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QFileDialog, \
    QWidget, QMainWindow, QMenu, QAction, \
    QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, \
    QAbstractItemView, QVBoxLayout, QHBoxLayout, QGridLayout


class QMyApplicationWindow(QWidget):
    # define signal
    sig1 = pyqtSignal()
    sig2 = pyqtSignal([str])
    button = QPushButton()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        # signal and slot binding
        self.button.clicked.connect(lambda: self.sig2[str].emit('xxx'))

    def do_task(self):
        self.sig1.emit()
        self.sig2[str].emit('xxx')


def get_desktop():
    return QApplication.instance().desktop()


def main():
    app = QApplication(sys.argv)
    # window = QMainWindow()
    window = QMyApplicationWindow()
    window.show()
    return sys.exit(app.exec_())


if __name__ == '__main__':
    main()
