import os
import sys
import time
import math
import psutil
import requests
import hashlib
import subprocess

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

LAUNCHER_EXE = "clemtoutlauncher.exe"

LOGO_URL = "https://raw.githubusercontent.com/0xst4ck-dev/Data_SDK/refs/heads/main/logo.png"


def download(url, path, progress_signal=None):
    try:
        r = requests.get(url, stream=True, timeout=15)
        total_size = int(r.headers.get('content-length', 0))
        if r.status_code != 200: return False

        downloaded = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and progress_signal:
                        percent = int((downloaded / total_size) * 100)
                        progress_signal.emit(percent)
        return True
    except:
        return False


def get_file_hash(filepath):
    if not os.path.exists(filepath):
        return ""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return "sha256:" + sha256_hash.hexdigest()
    except:
        return ""


class UpdateWorker(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)

    def run(self):
        for p in psutil.process_iter():
            try:
                if LAUNCHER_EXE.lower() in p.name().lower(): p.terminate()
            except:
                pass
        time.sleep(0.5)

        api_url = "https://api.github.com/repos/0xst4ck-dev/clemtoutlauncher/releases/latest"
        try:
            response = requests.get(api_url, timeout=10).json()
            asset = response['assets'][0]
            download_url = asset['browser_download_url']
            github_hash = asset.get('digest')

            exe_path = os.path.join(APP_DIR, LAUNCHER_EXE)
            local_hash = get_file_hash(exe_path)

            if local_hash != github_hash:
                download(download_url, exe_path, self.progress_signal)
        except Exception as e:
            print(f"Update error (Offline mode or API issue) : {e}")

        self.finished_signal.emit("done")


class UpdaterWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setFixedSize(220, 300)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.container = QWidget(self)
        self.container.setGeometry(0, 0, 220, 300)
        self.container.setStyleSheet("""
                    QWidget {
                        background-color: #4db8ff;
                        border-radius: 25px;
                    }
                    QLabel#TitleText {
                        font-size: 15pt;
                        font-weight: 800;
                        color: white;
                        margin-top: 10px;
                    }
                    QLabel#LoadingText {
                        font-size: 9pt;
                        font-weight: 400;
                        color: rgba(255, 255, 255, 0.8);
                    }
                """)

        layout = QVBoxLayout(self.container)
        layout.addSpacing(160)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 25)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.logo = QLabel(self)
        self.logo.setFixedSize(170, 170)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(LOGO_URL, headers=headers, timeout=5)

            if response.status_code == 200:
                img_data = response.content
                qimage = QImage.fromData(img_data)

                if qimage.isNull():
                    raise Exception("Image invalide")

                pix = QPixmap.fromImage(qimage).scaled(
                    170, 170,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.logo.setPixmap(pix)
            else:
                raise Exception(f"Erreur HTTP {response.status_code}")
        except Exception as e:
            print(f"Logo error, use of the backup cloud : {e}")
            self.logo.setText("☁")
            self.logo.setStyleSheet("font-size: 80px; color: white;")

        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("clemtoutlauncher")
        self.title_label.setObjectName("TitleText")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.loading_label = QLabel("Checking updates...")
        self.loading_label.setObjectName("LoadingText")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.loading_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(160, 4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: rgba(255, 255, 255, 0.2);
                        border-radius: 2px;
                        border: none;
                    }
                    QProgressBar::chunk {
                        background-color: white;
                        border-radius: 2px;
                    }
                """)
        layout.addWidget(self.progress_bar)

        self.start_logo_animation()
        self.start_dots_animation()

        self.worker = UpdateWorker()
        self.worker.progress_signal.connect(self.update_progress_ui)
        self.worker.finished_signal.connect(self.finish_and_launch)
        self.worker.start()

        self.drag_pos = None

    def update_progress_ui(self, val):
        if self.dots_timer.isActive():
            self.dots_timer.stop()

        self.progress_bar.setValue(val)
        self.loading_label.setText(f"Downloading update... {val}%")

        if val >= 100:
            self.loading_label.setText("Installing files...")

    def start_logo_animation(self):
        self.t = 0
        self.logo_timer = QTimer(self)
        self.logo_timer.timeout.connect(self.update_logo)
        self.logo_timer.start(16)

    def update_logo(self):
        self.t += 0.05
        offset = int(12 * math.sin(self.t))

        x = (self.width() - self.logo.width()) // 2
        y = 20 + offset

        self.logo.move(x, y)
        self.logo.raise_()

    def start_dots_animation(self):
        self.dot_state = 0
        self.dots_timer = QTimer(self)
        self.dots_timer.timeout.connect(self.update_dots)
        self.dots_timer.start(400)

    def update_dots(self):
        dots = ["", ".", "..", "..."]
        self.loading_label.setText("Opening in progress" + dots[self.dot_state])
        self.dot_state = (self.dot_state + 1) % 4

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton and self.drag_pos is not None:
            self.move(e.globalPosition().toPoint() - self.drag_pos)

    def finish_and_launch(self, msg):
        exe = os.path.join(APP_DIR, LAUNCHER_EXE)
        if os.path.exists(exe):
            subprocess.Popen([exe], cwd=APP_DIR)
        self.close()


def main():
    os.makedirs(APP_DIR, exist_ok=True)
    app = QApplication(sys.argv)
    win = UpdaterWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
