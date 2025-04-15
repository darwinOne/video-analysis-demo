import sys
import vlc
from PyQt5.QtWidgets import QApplication, QWidget, QGridLayout, QFrame
from PyQt5.QtCore import QTimer

# RTSP camera URLs
# CAMERA_URLS = [
#     "rtsp://admin:aery2021!@192.168.45.167:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif",
#     "rtsp://admin:aery2021!@192.168.45.165:554/stream1",
#     "rtsp://admin:aery2021!@192.168.45.168:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif",
#     "rtsp://admin:aery2021!@192.168.45.169:554/stream1"
# ]
CAMERA_URLS = [
    "videos/test.mp4",
    "videos/test1.mp4",
    "videos/test2.mp4",
    "videos/test.mp4"
]
class CameraStream(QFrame):
    def __init__(self, rtsp_url, parent=None):
        super().__init__(parent)
        self.rtsp_url = rtsp_url

        self.setStyleSheet("background-color: black;")
        self.instance = vlc.Instance()
        self.media_player = self.instance.media_player_new()
        self.media = self.instance.media_new(self.rtsp_url)
        self.media_player.set_media(self.media)

    def start(self):
        # This will delay setting the widget ID until it's fully initialized
        QTimer.singleShot(100, self.play_stream)

    def play_stream(self):
        win_id = int(self.winId())
        self.media_player.set_xwindow(win_id)  # Use .set_hwnd() on Windows
        self.media_player.play()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Camera RTSP Viewer")
        self.resize(1200, 800)

        layout = QGridLayout()
        self.setLayout(layout)

        self.camera_widgets = []

        for i, url in enumerate(CAMERA_URLS):
            cam_widget = CameraStream(url)
            self.camera_widgets.append(cam_widget)
            row, col = divmod(i, 2)
            layout.addWidget(cam_widget, row, col)

        # Start each stream
        for cam in self.camera_widgets:
            cam.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
