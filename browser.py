import base64
import csv
import glob
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime
from html import escape
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
import urllib.error
import urllib.request
import zipfile
from urllib.parse import quote, quote_plus, urlsplit

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QRectF,
    QSettings,
    QSize,
    QStandardPaths,
    QThread,
    QTimer,
    QUrl,
    QUrlQuery,
    QVariantAnimation,
    Qt,
    Signal,
    qVersion,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPixmap,
)
from PySide6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEnginePage,
    QWebEnginePermission,
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QSystemTrayIcon,
    QTabBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    HAVE_CRYPTO = True
except ImportError:  # the password manager needs:  pip install cryptography
    HAVE_CRYPTO = False

# Where home.html and blocklist.txt are looked for: next to this script, or
# next to the .exe once the browser has been packaged.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_NAME = "Filip’s Browser"
APP_VERSION = "1.0"

# The AI assistant. It is Google's Gemini with a custom name and personality.
ASSISTANT_NAME = "Jonathan AI Assistant"
GEMINI_MODEL = "gemini-flash-latest"  # can be changed in Settings
ASSISTANT_PROMPT = (
    f"You are {ASSISTANT_NAME}, a friendly and helpful AI assistant built into {APP_NAME}. "
    "Your name is Jonathan. Give clear, accurate, concise answers. "
    "If someone asks what powers you, say you are built on Google's Gemini."
)

# name -> (search address, name of the query parameter)
ENGINES = {
    "DuckDuckGo": ("https://duckduckgo.com/", "q"),
    "Google": ("https://www.google.com/search", "q"),
    "Bing": ("https://www.bing.com/search", "q"),
    "Brave Search": ("https://search.brave.com/search", "q"),
    "Ecosia": ("https://www.ecosia.org/search", "q"),
}
DEFAULT_ENGINE = "DuckDuckGo"

# Sites shown on the home screen the first time. You can add or remove sites
# from the home screen itself ("+ Add site", or the x on a tile).
DEFAULT_SHORTCUTS = [
    {"name": "YouTube", "url": "https://www.youtube.com"},
    {"name": "Wikipedia", "url": "https://en.wikipedia.org"},
    {"name": "GitHub", "url": "https://github.com"},
    {"name": "Reddit", "url": "https://www.reddit.com"},
]

# Starter lists. Add more by editing these or by using blocklist.txt.
DEFAULT_ADS = {
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "googletagservices.com",
    "adservice.google.com",
    "adnxs.com",
    "adsrvr.org",
    "criteo.com",
    "criteo.net",
    "taboola.com",
    "outbrain.com",
    "pubmatic.com",
    "rubiconproject.com",
    "openx.net",
    "moatads.com",
    "ads-twitter.com",
    "amazon-adsystem.com",
}
DEFAULT_TRACKERS = {
    "google-analytics.com",
    "googletagmanager.com",
    "connect.facebook.net",
    "scorecardresearch.com",
    "quantserve.com",
    "hotjar.com",
    "mouseflow.com",
    "crazyegg.com",
}

# The built-in home page. Placeholders that get filled in:
#   {{ENGINE}} = name of the chosen search engine
#   {{ACTION}} = address the search form sends to
#   {{PARAM}}  = name of the search box field that engine expects
#   {{SHORTCUTS}} = the site tiles, plus the "+ Add site" tile
#   {{APP_NAME}} = the browser name
#   {{ASSISTANT_NAME}} = the AI assistant name
#   {{BACKGROUND}}, {{MARK_BACKGROUND}}, {{NOTE}} = colors and a message that
#   change in incognito windows
#   (a link to href="browser://assistant" opens the AI chat)
#   {{FONT_FACE}} = CSS that loads the Oswald font from the fonts folder (if present)
#   {{WIDGET_LAYER}} = the movable widgets and the "Widgets" button
DEFAULT_HOME_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Home</title>
<style>
  {{FONT_FACE}}
  :root { color-scheme: dark; }
  body {
    margin: 0; min-height: 100vh;
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 32px;
    background: {{BACKGROUND}};
    color: #e8eaf0; font-family: {{BODY_FONT}};
  }
  .logo {
    display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 18px;
    font-family: "Oswald", Impact, sans-serif;
  }
  .mark {
    width: 64px; height: 64px; border-radius: 18px;
    display: flex; align-items: center; justify-content: center;
    font-size: 42px; font-weight: 700; color: #fff;
    background: {{MARK_BACKGROUND}};
    box-shadow: 0 8px 24px rgba(110, 168, 255, 0.35);
  }
  .word { font-size: 56px; font-weight: 500; letter-spacing: 2px; }
  .note { margin-top: -12px; color: #8a8f9c; font-size: 15px; }
  .note:empty { display: none; }
  form { width: min(600px, 90vw); }
  .ai {
    display: inline-flex; align-items: center; gap: 10px;
    padding: 12px 26px; border-radius: 999px; text-decoration: none;
    font-size: 17px; font-weight: 600; color: #fff;
    background: linear-gradient(135deg, #6ea8ff, #8e6bff);
    box-shadow: 0 8px 24px rgba(110, 168, 255, 0.3);
  }
  .ai:hover { filter: brightness(1.12); }
  input {
    width: 100%; box-sizing: border-box; padding: 16px 22px;
    font-size: 18px; color: inherit; outline: none;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 999px;
  }
  input:focus { border-color: #6ea8ff; background: rgba(255, 255, 255, 0.12); }
  .links {
    display: flex; flex-wrap: wrap; justify-content: center; gap: 14px;
    width: min(700px, 90vw);
  }
  .tile { position: relative; }
  .tile a.site, .add {
    display: block; padding: 10px 20px; border-radius: 999px;
    text-decoration: none; color: #cfd6e6;
    background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.1);
  }
  .tile a.site:hover, .add:hover { background: rgba(110, 168, 255, 0.25); color: #fff; }
  .add { border-style: dashed; }
  .x {
    position: absolute; top: -8px; right: -8px; width: 20px; height: 20px;
    line-height: 20px; text-align: center; font-size: 14px; border-radius: 50%;
    background: #3a4256; color: #fff; text-decoration: none; opacity: 0;
  }
  .tile:hover .x { opacity: 1; }
  .x:hover { background: #c0392b; }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: none; } }
  @keyframes popIn { from { opacity: 0; transform: scale(0.85); } to { opacity: 1; transform: none; } }
  @keyframes floaty { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
  .logo { animation: fadeUp 0.7s ease-out backwards; }
  .mark { animation: floaty 4s ease-in-out 1s infinite; }
  .note { animation: fadeUp 0.7s 0.1s ease-out backwards; }
  form { animation: fadeUp 0.7s 0.15s ease-out backwards; }
  .ai { animation: fadeUp 0.7s 0.25s ease-out backwards; transition: transform 0.2s, filter 0.2s; }
  .ai:hover { transform: translateY(-2px) scale(1.04); }
  .tile, .add { animation: popIn 0.5s calc(0.35s + var(--i, 0) * 0.06s) ease-out backwards; }
  .tile a.site, .add { transition: background 0.2s, color 0.2s, transform 0.2s; }
  .tile a.site:hover, .add:hover { transform: translateY(-3px); }
  input { transition: border-color 0.2s, background 0.2s, box-shadow 0.2s; }
  input:focus { box-shadow: 0 0 0 4px rgba(110, 168, 255, 0.2); }
  .x { transition: opacity 0.2s, background 0.2s; }
  .noanim, .noanim * { animation: none !important; transition: none !important; }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
</head>
<body class="{{BODY_CLASS}}">
  <div class="logo"><div class="mark">F</div><div class="word">{{APP_NAME}}</div></div>
  <div class="note">{{NOTE}}</div>
  <form action="{{ACTION}}" method="get">
    <input type="text" name="{{PARAM}}" placeholder="Search with {{ENGINE}}" autofocus autocomplete="off">
  </form>
  <a class="ai" href="browser://assistant">✦ {{ASSISTANT_NAME}}</a>
  <div class="links">
    {{SHORTCUTS}}
  </div>
{{WIDGET_LAYER}}
</body>
</html>
"""


def load_custom_blocklist(path):
    """Read extra domains from blocklist.txt (hosts format or one domain per line)."""
    domains = set()
    if not os.path.exists(path):
        return domains
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if not line:
                continue
            domain = line.split()[-1].lower()
            if "." in domain:
                domains.add(domain)
    return domains


# Files that run programs: ask before opening them from the downloads window.
RISKY_EXTENSIONS = {
    ".exe", ".msi", ".bat", ".cmd", ".com", ".scr", ".ps1",
    ".vbs", ".js", ".jar", ".lnk", ".reg", ".hta",
}


def human_size(n):
    """1536 -> '1.5 KB'"""
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def default_download_dir():
    return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)


def unique_filename(directory, filename):
    """Return filename, or 'name (1).ext', 'name (2).ext'... if it already exists."""
    base, ext = os.path.splitext(filename)
    candidate = filename
    n = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{base} ({n}){ext}"
        n += 1
    return candidate


def service_entry(service_id, name, url, color, letter):
    return {"id": service_id, "name": name, "url": url, "color": color, "letter": letter}


# Sites that can be pinned to the sidebar.
SERVICES = [
    service_entry("whatsapp", "WhatsApp", "https://web.whatsapp.com", "#25D366", "W"),
    service_entry("instagram", "Instagram", "https://www.instagram.com", "#C13584", "I"),
    service_entry("tiktok", "TikTok", "https://www.tiktok.com", "#111111", "T"),
    service_entry("x", "X", "https://x.com", "#000000", "X"),
    service_entry("youtube", "YouTube", "https://www.youtube.com", "#FF0000", "▶"),
    service_entry("discord", "Discord", "https://discord.com/app", "#5865F2", "D"),
    service_entry("twitch", "Twitch", "https://www.twitch.tv", "#9146FF", "T"),
    service_entry("facebook", "Facebook", "https://www.facebook.com", "#1877F2", "f"),
    service_entry("messenger", "Messenger", "https://www.messenger.com", "#0084FF", "M"),
    service_entry("telegram", "Telegram", "https://web.telegram.org/k/", "#2AABEE", "T"),
    service_entry("reddit", "Reddit", "https://www.reddit.com", "#FF4500", "R"),
    service_entry("spotify", "Spotify", "https://open.spotify.com", "#1DB954", "S"),
    service_entry("linkedin", "LinkedIn", "https://www.linkedin.com", "#0A66C2", "in"),
    service_entry("pinterest", "Pinterest", "https://www.pinterest.com", "#E60023", "P"),
    service_entry("bluesky", "Bluesky", "https://bsky.app", "#1185FE", "B"),
]
# Bigger, easier-to-press controls
TOOLBAR_STYLE = """
QToolButton { padding: 5px 10px; font-size: 15px; border-radius: 7px; }
QToolButton:hover { background: rgba(128, 128, 128, 0.22); }
"""
CLOSE_BUTTON_STYLE = """
QToolButton { border: none; border-radius: 13px; font-size: 13px; }
QToolButton:hover { background: rgba(230, 60, 60, 0.9); color: white; }
"""
NEW_TAB_BUTTON_STYLE = """
QToolButton { border: none; border-radius: 9px; font-size: 22px; }
QToolButton:hover { background: rgba(128, 128, 128, 0.25); }
"""
LOAD_BAR_STYLE = """
QProgressBar { border: none; background: transparent; }
QProgressBar::chunk { background: #6ea8ff; }
"""
DEFAULT_SIDEBAR = ["whatsapp", "instagram", "tiktok", "x", "youtube", "discord", "twitch"]

SIDEBAR_STYLE = """
#sidebar { background: #0b0b12; }
#sidebar QToolButton {
    border: none; border-radius: 10px; background: transparent;
    color: #ff3b5c; font-size: 20px;
}
#sidebar QToolButton:hover { background: #1c1c28; }
#sidebar QToolButton:checked { background: #7a1a30; }
"""

# What a site is asking for, in words (anything not listed here is refused).
PERMISSION_PHRASES = {
    QWebEnginePermission.PermissionType.MediaAudioCapture: "use your microphone",
    QWebEnginePermission.PermissionType.MediaVideoCapture: "use your camera",
    QWebEnginePermission.PermissionType.MediaAudioVideoCapture: "use your camera and microphone",
    QWebEnginePermission.PermissionType.Notifications: "show notifications",
    QWebEnginePermission.PermissionType.Geolocation: "see your location",
    QWebEnginePermission.PermissionType.MouseLock: "lock your mouse pointer",
    QWebEnginePermission.PermissionType.ClipboardReadWrite: "read what you copied to the clipboard",
}
PERMISSION_NAMES = {
    QWebEnginePermission.PermissionType.MediaAudioCapture: "Microphone",
    QWebEnginePermission.PermissionType.MediaVideoCapture: "Camera",
    QWebEnginePermission.PermissionType.MediaAudioVideoCapture: "Camera and microphone",
    QWebEnginePermission.PermissionType.Notifications: "Notifications",
    QWebEnginePermission.PermissionType.Geolocation: "Location",
    QWebEnginePermission.PermissionType.MouseLock: "Mouse lock",
    QWebEnginePermission.PermissionType.ClipboardReadWrite: "Clipboard",
}

# Shows web notifications as Windows pop-ups. Created in main().
NOTIFICATIONS = None

# Whether animations are switched on (see Appearance).
ANIMATIONS_ENABLED = True


def make_icon(service):
    """A sidebar icon. Uses icons/<id>.png if you put one there, otherwise a colored tile."""
    service_id = service.get("id", "")
    if service_id and not service_id.startswith("custom:"):
        path = os.path.join(BASE_DIR, "icons", service_id + ".png")
        if os.path.exists(path):
            return QIcon(path)
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(service["color"]))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 16, 16)
    font = QFont("Segoe UI")
    font.setPixelSize(30)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("white"))
    painter.drawText(QRectF(4, 4, 56, 56), Qt.AlignmentFlag.AlignCenter, service["letter"])
    painter.end()
    return QIcon(pixmap)


def script_world_id():
    """The 'private' JavaScript world our scripts run in (invisible to the page's own scripts)."""
    world = QWebEngineScript.ScriptWorldId.ApplicationWorld
    return int(getattr(world, "value", world))


def setup_profile(profile, blocker, capture_passwords=False):
    """Settings every web profile (normal and incognito) needs."""
    profile.setUrlRequestInterceptor(blocker)
    # Present ourselves like a regular Chromium browser, so sites such as WhatsApp Web
    # don't treat us as an unsupported embedded browser.
    profile.setHttpUserAgent(re.sub(r"\s*QtWebEngine/\S+", "", profile.httpUserAgent()))
    if NOTIFICATIONS is not None:
        profile.setNotificationPresenter(NOTIFICATIONS.present)
    if capture_passwords:
        script = QWebEngineScript()
        script.setName("filips-password-capture")
        script.setSourceCode(PASSWORD_SCRIPT.replace("__TOKEN__", PASSWORD_TOKEN))
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        script.setWorldId(script_world_id())
        script.setRunsOnSubFrames(False)
        profile.scripts().insert(script)


NORMAL_BACKGROUND = "radial-gradient(circle at 50% 20%, #1f2a44, #0e1018 70%)"
NORMAL_MARK = "linear-gradient(135deg, #6ea8ff, #8e6bff)"
INCOGNITO_BACKGROUND = "#000"
INCOGNITO_MARK = "linear-gradient(135deg, #5c5c5c, #1f1f1f)"
INCOGNITO_NOTE = "Pages you visit in this window won’t be saved in your history."

PRESET_BACKGROUNDS = {
    "Midnight": NORMAL_BACKGROUND,
    "Pure black": "#000000",
    "Charcoal": "#1b1b1f",
    "Purple haze": "radial-gradient(circle at 50% 20%, #3b2160, #100818 70%)",
    "Forest": "radial-gradient(circle at 50% 20%, #1d4a36, #07120d 70%)",
    "Sunset": "linear-gradient(160deg, #3a1c5a, #a8324f 55%, #f59f4a)",
    "Ocean": "linear-gradient(160deg, #0b2c4a, #136f8f 60%, #5dd0c8)",
}
DEFAULT_PROFILE = "Default"

# --- password manager: how a page tells the browser a login was typed in ---
# A small script runs inside every page (in an isolated world the page's own
# scripts can't see) and reports a login with a secret token that is created
# fresh every time the browser starts.
PASSWORD_PREFIX = "__filips_pm__:"
PASSWORD_TOKEN = secrets.token_hex(16)
PASSWORD_SCRIPT = r"""
(function () {
  const TOKEN = "__TOKEN__";
  let lastKey = "";
  function report(scope) {
    try {
      const root = scope || document;
      const pw = root.querySelector('input[type="password"]');
      if (!pw || !pw.value) return;
      let user = "";
      const fields = root.querySelectorAll('input[type="text"], input[type="email"], input:not([type])');
      for (const f of fields) {
        if (f.value && (f.compareDocumentPosition(pw) & Node.DOCUMENT_POSITION_FOLLOWING)) user = f.value;
      }
      const key = user + "|" + pw.value;
      if (key === lastKey) return;
      lastKey = key;
      console.log("__filips_pm__:" + JSON.stringify({t: TOKEN, u: user, p: pw.value}));
    } catch (e) {}
  }
  document.addEventListener("submit", function (e) { report(e.target); }, true);
  document.addEventListener("click", function (e) {
    const el = e.target && e.target.closest ? e.target.closest('button, input[type="submit"]') : null;
    if (el && el.type === "submit") report(el.form);
  }, true);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && e.target && e.target.type === "password") report(e.target.form);
  }, true);
})();
"""
FILL_FUNCTION = r"""
(function (username, password) {
  function setValue(el, value) {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("input", {bubbles: true}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
  }
  const pw = Array.from(document.querySelectorAll('input[type="password"]')).find(function (e) { return e.offsetParent !== null; });
  if (!pw) return false;
  let user = null;
  const fields = Array.from(document.querySelectorAll('input[type="text"], input[type="email"], input:not([type])'));
  for (const f of fields) {
    if (f.offsetParent !== null && (f.compareDocumentPosition(pw) & Node.DOCUMENT_POSITION_FOLLOWING)) user = f;
  }
  if (user && username) setValue(user, username);
  setValue(pw, password);
  return true;
})
"""

# Dark look for the incognito window's own controls (tabs, toolbar, menus...).
INCOGNITO_STYLE = """
QMainWindow, QDialog, QWidget { background: #121212; color: #e8e8e8; }
QToolBar { background: #1c1c1c; border: none; spacing: 4px; }
QToolButton { color: #e8e8e8; }
QLineEdit {
    background: #2a2a2a; color: #ffffff; border: 1px solid #444;
    border-radius: 12px; padding: 4px 10px;
}
QTabBar::tab { background: #1c1c1c; color: #cccccc; padding: 6px 12px; }
QTabBar::tab:selected { background: #000000; color: #ffffff; }
QMenuBar, QMenu, QStatusBar { background: #1c1c1c; color: #e8e8e8; }
QMenu::item:selected, QMenuBar::item:selected { background: #333333; }
"""

# Windows that are open (keeps incognito windows alive until they are cleaned up).
OPEN_WINDOWS = []


def data_dir():
    """Folder where the browser keeps its own files (like history.json)."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    return os.path.join(base, "FilipsBrowser")


class Settings:
    """Remembers the user's choices between runs (stored by Qt's QSettings)."""

    def __init__(self, ini_path=None):
        if ini_path:
            self._q = QSettings(ini_path, QSettings.Format.IniFormat)  # a non-default profile
        else:
            self._q = QSettings("MyBrowser", "MyBrowser")  # the Default profile

    def get(self, key, default):
        return self._q.value(key, default, type=type(default))

    def set(self, key, value):
        self._q.setValue(key, value)


class HistoryStore(QObject):
    """Remembers the pages you visited. Saved to history.json."""

    changed = Signal()
    LIMIT = 5000

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.entries = []  # oldest first: {"url", "title", "time"}
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(2000)
        self._save_timer.timeout.connect(self.save)
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [
                {"url": str(e["url"]), "title": str(e["title"]), "time": float(e["time"])}
                for e in data
            ]
        except (OSError, ValueError, KeyError, TypeError):
            self.entries = []

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            temp = self.path + ".tmp"
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(self.entries, f)
            os.replace(temp, self.path)
        except OSError:
            pass

    def add(self, url, title):
        now = time.time()
        if self.entries and self.entries[-1]["url"] == url:
            self.entries[-1]["title"] = title or self.entries[-1]["title"]
            self.entries[-1]["time"] = now
        else:
            self.entries.append({"url": url, "title": title, "time": now})
            del self.entries[: -self.LIMIT]
        self.changed.emit()
        self._save_timer.start()

    def remove_indices(self, indices):
        for index in sorted(set(indices), reverse=True):
            if 0 <= index < len(self.entries):
                del self.entries[index]
        self.changed.emit()
        self._save_timer.start()

    def clear(self):
        self.entries = []
        self.changed.emit()
        self.save()


def origin_of(url):
    """'https://Example.com:443/login?x=1' -> 'https://example.com' ('' if not a web address)."""
    text = url.strip()
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urlsplit(text)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return ""
    scheme = parts.scheme.lower()
    if not host or scheme not in ("http", "https"):
        return ""
    default_port = 443 if scheme == "https" else 80
    suffix = f":{port}" if port and port != default_port else ""
    return f"{scheme}://{host}{suffix}"


def write_json_file(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(temp, path)
    except OSError:
        pass


class BookmarkStore(QObject):
    """Your bookmarks. Saved to bookmarks.json."""

    changed = Signal()

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.entries = []  # {"title", "url", "folder", "time"}
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [
                {
                    "title": str(e["title"]),
                    "url": str(e["url"]),
                    "folder": str(e.get("folder", "")),
                    "time": float(e.get("time", 0)),
                }
                for e in data
            ]
        except (OSError, ValueError, KeyError, TypeError):
            self.entries = []

    def save(self):
        write_json_file(self.path, self.entries)

    def contains(self, url):
        return any(e["url"] == url for e in self.entries)

    def add(self, title, url, folder=""):
        if self.contains(url):
            return False
        self.entries.append({"title": title, "url": url, "folder": folder, "time": time.time()})
        self.save()
        self.changed.emit()
        return True

    def add_many(self, items):
        known = {e["url"] for e in self.entries}
        added = 0
        for item in items:
            if item["url"] in known:
                continue
            known.add(item["url"])
            self.entries.append(
                {
                    "title": item["title"],
                    "url": item["url"],
                    "folder": item.get("folder", ""),
                    "time": time.time(),
                }
            )
            added += 1
        self.save()
        self.changed.emit()
        return added

    def remove_url(self, url):
        self.entries = [e for e in self.entries if e["url"] != url]
        self.save()
        self.changed.emit()

    def remove_indices(self, indices):
        for index in sorted(set(indices), reverse=True):
            if 0 <= index < len(self.entries):
                del self.entries[index]
        self.save()
        self.changed.emit()


class BookmarkHTMLParser(HTMLParser):
    """Reads the standard bookmark export file that Chrome, Edge, Firefox and Brave all make."""

    def __init__(self):
        super().__init__()
        self.entries = []
        self.folders = []
        self.pending_folder = ""
        self.mode = None
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "h3":
            self.mode, self.text = "h3", []
        elif tag == "a":
            self.mode, self.text = "a", []
            self.href = dict(attrs).get("href")
        elif tag == "dl":
            self.folders.append(self.pending_folder)
            self.pending_folder = ""

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "h3":
            self.pending_folder = "".join(self.text).strip()
            self.mode = None
        elif tag == "a":
            href = self.href or ""
            if href.startswith(("http://", "https://")):
                title = "".join(self.text).strip() or href
                folder = " / ".join(f for f in self.folders if f)
                self.entries.append({"title": title, "url": href, "folder": folder})
            self.mode, self.href = None, None
        elif tag == "dl" and self.folders:
            self.folders.pop()

    def handle_data(self, data):
        if self.mode:
            self.text.append(data)


def parse_bookmarks_file(path):
    """Read bookmarks from an exported .html file, or from Chrome's own 'Bookmarks' file."""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    entries = []
    if text.lstrip().startswith("{"):
        data = json.loads(text)  # raises ValueError if it isn't valid

        def walk(node, folders):
            if not isinstance(node, dict):
                return
            kind = node.get("type")
            if kind == "url":
                url = str(node.get("url", ""))
                if url.startswith(("http://", "https://")):
                    entries.append(
                        {
                            "title": str(node.get("name") or url),
                            "url": url,
                            "folder": " / ".join(f for f in folders if f),
                        }
                    )
            elif kind == "folder":
                inner = folders + [str(node.get("name", ""))]
                for child in node.get("children", []):
                    walk(child, inner)

        for root in data.get("roots", {}).values():
            walk(root, [])
    else:
        parser = BookmarkHTMLParser()
        parser.feed(text)
        entries = parser.entries
    return entries


def write_bookmarks_html(path, entries):
    folders = {}
    for entry in entries:
        folders.setdefault(entry.get("folder", ""), []).append(entry)
    lines = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Bookmarks</TITLE>",
        "<H1>Bookmarks</H1>",
        "<DL><p>",
    ]
    for folder, items in folders.items():
        if folder:
            lines.append(f"    <DT><H3>{escape(folder)}</H3>")
            lines.append("    <DL><p>")
        for item in items:
            lines.append(f'        <DT><A HREF="{escape(item["url"])}">{escape(item["title"])}</A>')
        if folder:
            lines.append("    </DL><p>")
    lines.append("</DL><p>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_password_csv(path):
    """Read a password export from Chrome, Edge, Brave, Firefox or Bitwarden: (url, user, password)."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("The file is empty.")
        names = {n.strip().lower(): n for n in reader.fieldnames if n}

        def column(*options):
            for option in options:
                if option in names:
                    return names[option]
            return None

        url_col = column("url", "origin_url", "login_uri", "website", "web site", "hostname", "origin")
        user_col = column("username", "login_username", "user name", "user", "login", "email")
        pass_col = column("password", "login_password", "pass")
        if not url_col or not pass_col:
            raise ValueError("This doesn't look like a password export (no url/password columns).")
        for row in reader:
            url = (row.get(url_col) or "").strip()
            password = row.get(pass_col) or ""
            username = (row.get(user_col) or "").strip() if user_col else ""
            if url and password:
                rows.append((url, username, password))
    return rows


def ask_new_password(parent, title="Create a browser password"):
    """Ask for a new browser password twice. Returns it, or None if cancelled or invalid."""
    first, ok = QInputDialog.getText(
        parent, title, "Choose a browser password (at least 8 characters):", QLineEdit.EchoMode.Password
    )
    if not ok:
        return None
    if len(first) < 8:
        QMessageBox.warning(parent, title, "The password must be at least 8 characters long.")
        return None
    second, ok = QInputDialog.getText(
        parent, title, "Type it again to confirm:", QLineEdit.EchoMode.Password
    )
    if not ok:
        return None
    if second != first:
        QMessageBox.warning(parent, title, "The two passwords did not match.")
        return None
    return first


class PasswordVault:
    """Saved logins, encrypted on disk with a key made from your browser password.

    The file holds only a random salt and one encrypted block, so nothing (not even
    which sites you have accounts on) can be read without the password.
    """

    def __init__(self, path):
        self.path = path
        self.salt = None
        self.key = None
        self.entries = None  # a list while unlocked, None while locked

    @staticmethod
    def derive_key(password, salt):
        kdf = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1)
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def exists(self):
        return os.path.exists(self.path)

    @property
    def is_unlocked(self):
        return self.key is not None and self.entries is not None

    def create(self, password):
        self.salt = os.urandom(16)
        self.key = self.derive_key(password, self.salt)
        self.entries = []
        self.save()

    def unlock(self, password):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            salt = base64.b64decode(data["salt"])
            key = self.derive_key(password, salt)
            plain = Fernet(key).decrypt(data["token"].encode("ascii"))
            entries = json.loads(plain.decode("utf-8"))
            if not isinstance(entries, list):
                return False
        except (OSError, ValueError, KeyError, TypeError, InvalidToken):
            return False
        self.salt, self.key, self.entries = salt, key, entries
        return True

    def lock(self):
        self.key = None
        self.entries = None

    def save(self):
        token = Fernet(self.key).encrypt(json.dumps(self.entries).encode("utf-8"))
        write_json_file(
            self.path,
            {
                "version": 1,
                "salt": base64.b64encode(self.salt).decode("ascii"),
                "token": token.decode("ascii"),
            },
        )

    def change_password(self, new_password):
        self.salt = os.urandom(16)
        self.key = self.derive_key(new_password, self.salt)
        self.save()

    def find(self, origin):
        return [e for e in self.entries if e["origin"] == origin]

    def _set(self, origin, username, password):
        for entry in self.entries:
            if entry["origin"] == origin and entry["username"] == username:
                if entry["password"] == password:
                    return "same"
                entry["password"] = password
                entry["time"] = time.time()
                return "updated"
        self.entries.append(
            {"origin": origin, "username": username, "password": password, "time": time.time()}
        )
        return "added"

    def add(self, origin, username, password):
        result = self._set(origin, username, password)
        if result != "same":
            self.save()
        return result

    def add_many(self, rows):
        added = updated = 0
        for url, username, password in rows:
            origin = origin_of(url)
            if not origin:
                continue
            result = self._set(origin, username, password)
            if result == "added":
                added += 1
            elif result == "updated":
                updated += 1
        self.save()
        return added, updated


class NotificationCenter(QObject):
    """Shows web notifications (for example WhatsApp messages) as Windows pop-ups."""

    def __init__(self, icon):
        super().__init__()
        self.window = None  # the main window, brought forward when a pop-up is clicked
        self.active = []
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(APP_NAME)
        self.tray.messageClicked.connect(self.on_clicked)
        self.tray.show()

    def present(self, notification):
        self.active.append(notification)  # keep it alive while it is shown
        del self.active[:-20]
        title = notification.title() or notification.origin().host()
        notification.show()
        self.tray.showMessage(title, notification.message(), self.tray.icon(), 8000)

    def on_clicked(self):
        if self.active:
            self.active[-1].click()
        if self.window is not None:
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()


class BlockCounter(QObject):
    """Lets the blocker (running on a background thread) tell the UI a count."""

    changed = Signal(int)


class Blocker(QWebEngineUrlRequestInterceptor):
    """Looks at every request the browser makes and cancels the ones on a blocklist."""

    def __init__(self, ad_domains, tracker_domains):
        super().__init__()
        self.ad_domains = ad_domains
        self.tracker_domains = tracker_domains
        self.block_ads = True
        self.block_trackers = True
        self.count = 0
        self.counter = BlockCounter()

    @staticmethod
    def matches(host, domains):
        # "a.b.tracker.com" matches if "a.b.tracker.com", "b.tracker.com"
        # or "tracker.com" is on the list.
        parts = host.split(".")
        for i in range(len(parts) - 1):
            if ".".join(parts[i:]) in domains:
                return True
        return False

    def interceptRequest(self, info):
        host = info.requestUrl().host().lower()
        blocked = (self.block_ads and self.matches(host, self.ad_domains)) or (
            self.block_trackers and self.matches(host, self.tracker_domains)
        )
        if blocked:
            info.block(True)
            self.count += 1
            self.counter.changed.emit(self.count)
            return
        if self.block_trackers:
            # Ask sites not to track us (not every site honors this).
            info.setHttpHeader(b"DNT", b"1")
            info.setHttpHeader(b"Sec-GPC", b"1")


AD_DOMAINS = set(DEFAULT_ADS)
TRACKER_DOMAINS = set(DEFAULT_TRACKERS)
PROFILES = {}  # profile name -> ProfileData, created when first opened


def profiles_path():
    return os.path.join(data_dir(), "profiles.json")


def load_profiles():
    """{"profiles": [{"name", "dir"}...], "pending_delete": [dir...]}  (Default is always first)."""
    result = {"profiles": [], "pending_delete": []}
    try:
        with open(profiles_path(), encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("profiles", []):
            if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("dir"), str):
                if item["name"] != DEFAULT_PROFILE:
                    result["profiles"].append({"name": item["name"], "dir": item["dir"]})
        result["pending_delete"] = [d for d in data.get("pending_delete", []) if isinstance(d, str)]
    except (OSError, ValueError, AttributeError):
        pass
    result["profiles"].insert(0, {"name": DEFAULT_PROFILE, "dir": ""})
    return result


def save_profiles(data):
    write_json_file(profiles_path(), data)


def add_profile(name):
    """Create a profile. Returns False if a profile with that name already exists."""
    data = load_profiles()
    if any(p["name"].lower() == name.lower() for p in data["profiles"]):
        return False
    folder = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "profile"
    data["profiles"].append({"name": name, "dir": f"{folder}-{int(time.time())}"})
    save_profiles(data)
    return True


def remove_profile(name):
    """Forget a profile. Its files are erased the next time the browser starts."""
    data = load_profiles()
    for item in data["profiles"]:
        if item["name"] == name and item["dir"]:
            data["pending_delete"].append(item["dir"])
    data["profiles"] = [p for p in data["profiles"] if p["name"] != name or not p["dir"]]
    save_profiles(data)
    PROFILES.pop(name, None)


def cleanup_pending_profiles():
    data = load_profiles()
    for folder in data["pending_delete"]:
        if folder and os.path.basename(folder) == folder:
            shutil.rmtree(os.path.join(data_dir(), "profiles", folder), ignore_errors=True)
    if data["pending_delete"]:
        data["pending_delete"] = []
        save_profiles(data)


class ProfileData:
    """Everything that belongs to one profile: logins and cookies, history, bookmarks,
    saved passwords, settings and its own blocker counter."""

    def __init__(self, info):
        self.name = info["name"]
        if info["dir"]:
            self.dir = os.path.join(data_dir(), "profiles", info["dir"])
        else:
            self.dir = data_dir()  # the Default profile keeps its files where they always were
        os.makedirs(self.dir, exist_ok=True)

        self.blocker = Blocker(AD_DOMAINS, TRACKER_DOMAINS)
        if info["dir"]:
            self.web_profile = QWebEngineProfile("FilipsBrowser-" + info["dir"])
            self.web_profile.setPersistentStoragePath(os.path.join(self.dir, "webdata"))
            self.web_profile.setCachePath(os.path.join(self.dir, "cache"))
            self.settings = Settings(os.path.join(self.dir, "settings.ini"))
        else:
            self.web_profile = QWebEngineProfile.defaultProfile()
            self.settings = Settings()
        self.history = HistoryStore(os.path.join(self.dir, "history.json"))
        self.bookmarks = BookmarkStore(os.path.join(self.dir, "bookmarks.json"))
        self.vault = PasswordVault(os.path.join(self.dir, "passwords.vault")) if HAVE_CRYPTO else None
        setup_profile(self.web_profile, self.blocker, capture_passwords=self.vault is not None)


def get_profile(name):
    if name not in PROFILES:
        info = next(
            (p for p in load_profiles()["profiles"] if p["name"] == name),
            {"name": DEFAULT_PROFILE, "dir": ""},
        )
        PROFILES[info["name"]] = ProfileData(info)
        name = info["name"]
    return PROFILES[name]


def save_all_profiles():
    for data in PROFILES.values():
        data.history.save()
        data.bookmarks.save()


def save_background_image(source, destination, max_bytes=900_000):
    """Shrink the chosen picture so it fits on the home page, and save it as a JPEG."""
    image = QImage(source)
    if image.isNull():
        return False
    smooth = Qt.TransformationMode.SmoothTransformation
    if image.width() > 1600:
        image = image.scaledToWidth(1600, smooth)
    for _round in range(6):
        for quality in (85, 70, 55, 40):
            if not image.save(destination, "JPG", quality):
                return False
            if os.path.getsize(destination) <= max_bytes:
                return True
        image = image.scaledToWidth(max(400, int(image.width() * 0.75)), smooth)
    return os.path.getsize(destination) <= max_bytes


def set_animations(enabled):
    global ANIMATIONS_ENABLED
    ANIMATIONS_ENABLED = bool(enabled)


class FadeInFilter(QObject):
    """Makes dialogs and pop-up windows fade in instead of appearing instantly."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show and ANIMATIONS_ENABLED and isinstance(obj, QWidget):
            if (
                obj.isWindow()
                and not isinstance(obj, QMainWindow)
                and obj.windowType() in (Qt.WindowType.Window, Qt.WindowType.Dialog)
                and obj.findChild(QWebEngineView) is None
            ):
                obj.setWindowOpacity(0.0)
                animation = QPropertyAnimation(obj, b"windowOpacity", obj)
                animation.setDuration(170)
                animation.setStartValue(0.0)
                animation.setEndValue(1.0)
                animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        return False


class AnimatedToolButton(QToolButton):
    """A button whose icon grows a little while the mouse is over it."""

    def __init__(self, base=30, grown=35):
        super().__init__()
        self.base = base
        self.grown = grown
        self.setIconSize(QSize(base, base))
        self.grow_animation = QVariantAnimation(self)
        self.grow_animation.setDuration(120)
        self.grow_animation.valueChanged.connect(
            lambda value: self.setIconSize(QSize(int(value), int(value)))
        )

    def resize_icon(self, target):
        self.grow_animation.stop()
        if not ANIMATIONS_ENABLED:
            self.setIconSize(QSize(target, target))
            return
        self.grow_animation.setStartValue(self.iconSize().width())
        self.grow_animation.setEndValue(target)
        self.grow_animation.start()

    def enterEvent(self, event):
        self.resize_icon(self.grown)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.resize_icon(self.base)
        super().leaveEvent(event)


class BigTabBar(QTabBar):
    """A tab bar with larger tabs that are easier to hit."""

    def __init__(self):
        super().__init__()
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setExpanding(False)
        self.setMovable(True)  # drag a tab to reorder it
        self.setUsesScrollButtons(True)

    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        return QSize(max(170, min(size.width() + 28, 260)), max(size.height(), 42))

    def minimumTabSizeHint(self, index):
        return QSize(110, 42)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:  # middle-click closes a tab
            index = self.tabAt(event.position().toPoint())
            if index >= 0:
                self.tabCloseRequested.emit(index)
                return
        super().mouseReleaseEvent(event)


class BrowserTabs(QTabWidget):
    def __init__(self):
        super().__init__()
        self.setTabBar(BigTabBar())


# ---------- Chrome Web Store extensions ----------
# The store's own "Add to Chrome" button only works inside Chrome, so we download the
# extension file (.crx) from the store ourselves, unpack it, and install it from a folder.

STORE_HOSTS = ("chromewebstore.google.com", "chrome.google.com")


def extension_id_from_text(text):
    """A Chrome Web Store link or a bare 32-letter extension id -> the id ('' if none)."""
    text = text.strip()
    if re.fullmatch(r"[a-p]{32}", text):
        return text
    match = re.search(r"/([a-p]{32})(?:[/?#]|$)", text)
    return match.group(1) if match else ""


def store_extension_id(url):
    """The extension id if url is a Chrome Web Store page, otherwise ''."""
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    return extension_id_from_text(url) if host in STORE_HOSTS else ""


def crx_to_zip_bytes(data):
    """A .crx file is a zip file with a small header in front. Return just the zip part."""
    if data[:4] != b"Cr24":
        raise ValueError("This isn't a Chrome extension file.")
    version = int.from_bytes(data[4:8], "little")
    if version == 3:
        start = 12 + int.from_bytes(data[8:12], "little")
    elif version == 2:
        start = 16 + int.from_bytes(data[8:12], "little") + int.from_bytes(data[12:16], "little")
    else:
        raise ValueError(f"Unsupported extension file version ({version}).")
    return data[start:]


def unpack_extension(data, folder):
    """Unpack a .crx or .zip into folder (replacing what was there). Returns the manifest."""
    if data[:4] == b"Cr24":
        data = crx_to_zip_bytes(data)
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("The extension file is damaged or isn't a real extension.")
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder, exist_ok=True)
    base = os.path.realpath(folder)
    with archive:
        for member in archive.infolist():
            name = member.filename
            if not name or name.endswith("/") or name.startswith("_metadata/"):
                continue
            target = os.path.realpath(os.path.join(folder, name))
            if not target.startswith(base + os.sep):
                continue  # ignore any file that tries to escape the folder
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(member) as source, open(target, "wb") as destination:
                shutil.copyfileobj(source, destination)
    manifest_path = os.path.join(folder, "manifest.json")
    if not os.path.exists(manifest_path):
        raise ValueError("The extension has no manifest.json, so it can't be installed.")
    with open(manifest_path, encoding="utf-8-sig") as f:
        return json.load(f)


class ExtensionDownloader(QThread):
    """Downloads an extension file from the Chrome Web Store without freezing the browser."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, extension_id, chrome_version):
        super().__init__()
        self.extension_id = extension_id
        self.chrome_version = chrome_version

    def run(self):
        url = (
            "https://clients2.google.com/service/update2/crx?response=redirect"
            f"&prodversion={self.chrome_version}&acceptformat=crx2,crx3"
            f"&x=id%3D{self.extension_id}%26uc"
        )
        agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{self.chrome_version} Safari/537.36"
        )
        try:
            request = urllib.request.Request(url, headers={"User-Agent": agent})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            if data[:4] != b"Cr24":
                raise ValueError("no extension file")
            self.succeeded.emit(data)
        except urllib.error.HTTPError as error:
            self.failed.emit(f"The Chrome Web Store refused the download (error {error.code}).")
        except ValueError:
            self.failed.emit(
                "The Chrome Web Store didn't send an extension file for this ID. "
                "It may not exist, may be unavailable, or may be restricted."
            )
        except Exception as error:
            self.failed.emit(f"Could not download the extension: {error}")


# ---------- Home screen widgets ----------
# The widgets live in the home page itself (see WIDGET_JS). The page talks to the browser
# through console messages that carry a secret token created fresh at every start, and the
# browser fetches weather and news for it (web pages can't read most news feeds directly).

HOME_PREFIX = "__filips_home__:"
HOME_TOKEN = secrets.token_hex(16)
WIDGET_IDS = (
    "clock", "weather", "news", "profiles", "notes", "todo",
    "bookmarks", "history", "calculator", "timer", "quote",
)
NEWS_SOURCES = {
    "bbc": ("BBC News - top stories", "https://feeds.bbci.co.uk/news/rss.xml"),
    "bbc-world": ("BBC News - world", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    "bbc-tech": ("BBC News - technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    "bbc-sport": ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
    "npr": ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    "guardian": ("The Guardian - world", "https://www.theguardian.com/world/rss"),
    "aljazeera": ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    "ars": ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    "verge": ("The Verge", "https://www.theverge.com/rss/index.xml"),
    "hn": ("Hacker News", "https://hnrss.org/frontpage"),
}


def sanitize_widget_state(data):
    """Keep only what a widget layout is allowed to contain (the page is trusted, but be careful)."""
    result = {"enabled": [], "pos": {}, "config": {}}
    if not isinstance(data, dict):
        return result
    enabled = data.get("enabled")
    if isinstance(enabled, list):
        for widget_id in enabled:
            if widget_id in WIDGET_IDS and widget_id not in result["enabled"]:
                result["enabled"].append(widget_id)
    positions = data.get("pos")
    if isinstance(positions, dict):
        for widget_id, spot in positions.items():
            if widget_id in WIDGET_IDS and isinstance(spot, dict):
                try:
                    x, y = float(spot.get("x")), float(spot.get("y"))
                except (TypeError, ValueError):
                    continue
                if x == x and y == y:  # skips NaN
                    result["pos"][widget_id] = {"x": min(1.0, max(0.0, x)), "y": min(1.0, max(0.0, y))}
    config = data.get("config")
    if isinstance(config, dict):
        out = result["config"]
        weather = config.get("weather")
        if isinstance(weather, dict):
            out["weather"] = {
                "city": str(weather.get("city", ""))[:80],
                "unit": "f" if weather.get("unit") == "f" else "c",
            }
        news = config.get("news")
        if isinstance(news, dict):
            source = str(news.get("source", "bbc"))
            out["news"] = {
                "source": source if source in NEWS_SOURCES or source == "custom" else "bbc",
                "custom": str(news.get("custom", ""))[:300],
            }
        notes = config.get("notes")
        if isinstance(notes, dict):
            out["notes"] = {"text": str(notes.get("text", ""))[:5000]}
        todo = config.get("todo")
        if isinstance(todo, dict) and isinstance(todo.get("items"), list):
            items = []
            for item in todo["items"]:
                if isinstance(item, dict) and str(item.get("t", "")).strip():
                    items.append({"t": str(item["t"])[:200], "d": bool(item.get("d"))})
                if len(items) >= 50:
                    break
            out["todo"] = {"items": items}
        timer = config.get("timer")
        if isinstance(timer, dict):
            try:
                minutes = int(float(timer.get("minutes", 25)))
            except (TypeError, ValueError):
                minutes = 25
            out["timer"] = {"minutes": min(180, max(1, minutes))}
        quote = config.get("quote")
        if isinstance(quote, dict):
            try:
                shift = int(float(quote.get("shift", 0)))
            except (TypeError, ValueError):
                shift = 0
            out["quote"] = {"shift": min(999, max(0, shift))}
    return result


def http_get(url, limit=3_000_000, timeout=15):
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; FilipsBrowser/1.0)"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(limit)


def build_weather(place, data, unit):
    """Turn Open-Meteo's answer into the small dictionary the weather widget shows."""
    current = data["current"]
    daily = data["daily"]
    days = []
    for index, day in enumerate(daily["time"]):
        days.append(
            {
                "date": day,
                "code": daily["weather_code"][index],
                "max": daily["temperature_2m_max"][index],
                "min": daily["temperature_2m_min"][index],
            }
        )
    return {
        "place": place.get("name", ""),
        "country": place.get("country", ""),
        "temp": current["temperature_2m"],
        "feels": current["apparent_temperature"],
        "humidity": current["relative_humidity_2m"],
        "wind": current["wind_speed_10m"],
        "code": current["weather_code"],
        "unit": unit,
        "days": days,
    }


def fetch_weather(city, unit):
    """Look a city up and get its forecast from Open-Meteo (free, no account needed)."""
    if not city.strip():
        raise ValueError("Type a city first.")
    geo = json.loads(
        http_get(
            "https://geocoding-api.open-meteo.com/v1/search?name="
            + quote(city.strip())
            + "&count=1&language=en&format=json"
        )
    )
    results = geo.get("results") or []
    if not results:
        raise ValueError(f"No place called \"{city.strip()}\" was found.")
    place = results[0]
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={place['latitude']}&longitude={place['longitude']}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min"
        "&timezone=auto&forecast_days=4"
    )
    if unit == "f":
        url += "&temperature_unit=fahrenheit&wind_speed_unit=mph"
    return build_weather(place, json.loads(http_get(url)), unit)


def parse_feed(data, limit=10):
    """Read the headlines from an RSS or Atom feed."""
    if re.search(rb"<!ENTITY", data, re.IGNORECASE):
        raise ValueError("This feed uses features that aren't allowed.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise ValueError("That address isn't an RSS or Atom news feed.")
    items = []
    for node in root.iter():
        if node.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = link = published = ""
        for child in node:
            name = child.tag.split("}")[-1]
            if name == "title":
                title = " ".join((child.text or "").split())
            elif name == "link":
                href = child.get("href")
                if href:
                    if child.get("rel", "alternate") == "alternate":
                        link = href
                elif (child.text or "").strip():
                    link = child.text.strip()
            elif name in ("pubDate", "published", "updated") and not published:
                published = (child.text or "").strip()
        if title and link.startswith(("http://", "https://")):
            items.append({"title": title[:200], "link": link, "time": published})
        if len(items) >= limit:
            break
    if not items:
        raise ValueError("No headlines were found in this feed.")
    return items


def fetch_news(source, custom):
    if source == "custom":
        url = custom.strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("Enter a feed address that starts with http:// or https://")
    else:
        url = NEWS_SOURCES.get(source, NEWS_SOURCES["bbc"])[1]
    return {"items": parse_feed(http_get(url))}


class HomeDataWorker(QThread):
    """Fetches weather or news for a home page widget without freezing the browser."""

    done = Signal(object)

    def __init__(self, job, view_id, kind, params):
        super().__init__()
        self.job = job
        self.view_id = view_id
        self.kind = kind
        self.params = params

    def run(self):
        result = {"job": self.job, "view_id": self.view_id, "kind": self.kind}
        try:
            if self.kind == "weather":
                result["data"] = fetch_weather(self.params["city"], self.params["unit"])
            else:
                result["data"] = fetch_news(self.params["source"], self.params["custom"])
            result["ok"] = True
        except ValueError as error:
            result.update(ok=False, error=str(error))
        except urllib.error.HTTPError as error:
            result.update(ok=False, error=f"The service refused the request (error {error.code}).")
        except urllib.error.URLError:
            result.update(ok=False, error="Couldn't connect. Check your internet connection.")
        except (KeyError, IndexError, TypeError):
            result.update(ok=False, error="The service sent an answer that couldn't be read.")
        except Exception as error:
            result.update(ok=False, error=f"Couldn't load this: {error}")
        self.done.emit(result)


WIDGET_CSS = r"""
#fw-layer { position: fixed; inset: 0; pointer-events: none; z-index: 5; }
.fw-card {
  position: absolute; pointer-events: auto; box-sizing: border-box; max-width: 92vw;
  background: rgba(14, 16, 26, 0.62);
  -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  color: #e8eaf0; font-size: 14px; text-align: left;
}
.fw-in { animation: fwIn 0.35s ease-out backwards; }
@keyframes fwIn { from { opacity: 0; transform: scale(0.94) translateY(8px); } to { opacity: 1; transform: none; } }
.fw-dragging { opacity: 0.92; box-shadow: 0 18px 40px rgba(0, 0, 0, 0.5); }
.fw-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 12px; cursor: grab; user-select: none; font-weight: 600;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.fw-dragging .fw-head { cursor: grabbing; }
.fw-x {
  width: 22px; height: 22px; border: none; border-radius: 50%; padding: 0;
  background: none; color: #aab0c0; cursor: pointer; font-size: 12px; opacity: 0.6;
  transition: opacity 0.2s, background 0.2s;
}
.fw-x:hover { opacity: 1; background: rgba(230, 60, 60, 0.85); color: #fff; }
.fw-body { padding: 12px; }
.fw-time { font-size: 34px; font-weight: 300; letter-spacing: 1px; }
.fw-small { font-size: 12px; color: #9aa3b5; }
.fw-error { color: #ff9b9b; font-size: 13px; }
.fw-foot { display: flex; justify-content: space-between; margin-top: 8px; }
#fw-layer form, #fw-layer .fw-form { display: flex; gap: 6px; width: auto; animation: none; margin: 0 0 8px 0; }
#fw-layer .fw-input, #fw-layer select, #fw-layer textarea {
  flex: 1; width: 100%; min-width: 0; box-sizing: border-box; padding: 7px 10px;
  border-radius: 9px; border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.08); color: inherit; font: inherit; font-size: 13px; outline: none;
}
#fw-layer select option { color: #111; }
#fw-layer .fw-input:focus, #fw-layer textarea:focus { border-color: #6ea8ff; box-shadow: none; }
#fw-layer input[type="checkbox"], #fw-panel input[type="checkbox"] {
  width: 16px; height: 16px; flex: none; padding: 0; margin: 0; border-radius: 4px; box-shadow: none; accent-color: #6ea8ff;
}
.fw-btn {
  padding: 6px 12px; border-radius: 9px; border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(110, 168, 255, 0.28); color: #fff; cursor: pointer; font: inherit; font-size: 13px;
  transition: background 0.2s, transform 0.2s;
}
.fw-btn:hover { background: rgba(110, 168, 255, 0.5); transform: translateY(-1px); }
.fw-link { background: none; border: none; color: #8fb8ff; cursor: pointer; padding: 2px 4px; font: inherit; font-size: 12px; }
.fw-link:hover { text-decoration: underline; }
.fw-wtop { display: flex; align-items: center; gap: 12px; }
.fw-wicon { font-size: 44px; }
.fw-wtemp { font-size: 34px; font-weight: 300; }
.fw-wplace { margin: 6px 0 2px; font-weight: 600; }
.fw-days { display: flex; gap: 8px; margin-top: 10px; }
.fw-day { flex: 1; text-align: center; padding: 6px 4px; border-radius: 10px; background: rgba(255, 255, 255, 0.06); }
.fw-dayicon { font-size: 22px; }
.fw-news { max-height: 300px; overflow-y: auto; margin-top: 8px; scrollbar-width: thin; }
.fw-news-item {
  display: flex; flex-direction: column; gap: 2px; padding: 8px 6px; border-radius: 8px;
  color: inherit; text-decoration: none; border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  transition: background 0.2s;
}
.fw-news-item:hover { background: rgba(255, 255, 255, 0.08); }
.fw-news-title { font-size: 13px; line-height: 1.35; }
.fw-list { display: flex; flex-direction: column; gap: 2px; max-height: 260px; overflow-y: auto; scrollbar-width: thin; }
.fw-item {
  display: block; padding: 6px 8px; border-radius: 8px; color: #cfd6e6; text-decoration: none;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: background 0.2s;
}
a.fw-item:hover { background: rgba(255, 255, 255, 0.1); color: #fff; }
.fw-current { color: #fff; font-weight: 600; }
.fw-todo { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.fw-todo-text { flex: 1; word-break: break-word; }
.fw-done .fw-todo-text { text-decoration: line-through; opacity: 0.55; }
#fw-layer textarea.fw-notes { min-height: 130px; resize: vertical; }
.fw-calc-screen {
  text-align: right; font-size: 28px; padding: 6px 10px; margin-bottom: 8px;
  background: rgba(0, 0, 0, 0.25); border-radius: 9px; overflow: hidden;
}
.fw-calc-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.fw-key {
  padding: 9px 0; border: none; border-radius: 9px; background: rgba(255, 255, 255, 0.1);
  color: #fff; font: inherit; font-size: 16px; cursor: pointer; transition: background 0.15s, transform 0.1s;
}
.fw-key:hover { background: rgba(255, 255, 255, 0.2); }
.fw-key:active { transform: scale(0.95); }
.fw-wide { grid-column: span 2; }
.fw-quote { font-size: 15px; line-height: 1.45; font-style: italic; }
.fw-quote-by { text-align: right; margin: 6px 0 4px; }
.fw-toggle {
  position: fixed; right: 18px; bottom: 18px; z-index: 30; padding: 10px 16px; border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.15); background: rgba(14, 16, 26, 0.7); color: #e8eaf0;
  cursor: pointer; font: inherit; font-size: 14px; -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
  transition: transform 0.2s, background 0.2s;
}
.fw-toggle:hover { transform: translateY(-2px); background: rgba(110, 168, 255, 0.4); }
.fw-panel {
  position: fixed; right: 18px; bottom: 68px; z-index: 30; width: 250px; max-height: 70vh; overflow-y: auto;
  padding: 12px; box-sizing: border-box; border-radius: 16px; color: #e8eaf0; font-size: 14px; text-align: left;
  background: rgba(14, 16, 26, 0.88); border: 1px solid rgba(255, 255, 255, 0.12);
  -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  animation: fwIn 0.25s ease-out backwards;
}
.fw-panel[hidden] { display: none !important; }
.fw-panel-title { font-weight: 600; margin-bottom: 8px; }
.fw-panel-row { display: flex; align-items: center; gap: 10px; padding: 5px 4px; border-radius: 8px; cursor: pointer; }
.fw-panel-row:hover { background: rgba(255, 255, 255, 0.08); }
.fw-panel .fw-btn { margin: 8px 0 6px; width: 100%; }
"""

WIDGET_JS = r"""
(function () {
  "use strict";
  var BOOT = window.FILIPS_HOME;
  if (!BOOT) return;
  var state = BOOT.state;
  if (!state.enabled) state.enabled = [];
  if (!state.pos) state.pos = {};
  if (!state.config) state.config = {};

  // ---------- helpers ----------
  function send(action, data) {
    console.log("__filips_home__:" + JSON.stringify({t: BOOT.token, a: action, d: data}));
  }
  var saveTimer = null;
  function save() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () { send("state", state); }, 400);
  }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }
  function cfgFor(id) {
    if (!state.config[id]) state.config[id] = {};
    return state.config[id];
  }
  function ago(value) {
    var t = Date.parse(value);
    if (isNaN(t)) return "";
    var mins = Math.round((Date.now() - t) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return mins + " min ago";
    var hours = Math.round(mins / 60);
    if (hours < 24) return hours + " h ago";
    return Math.round(hours / 24) + " d ago";
  }

  var WEATHER = {
    0: ["Clear sky", "\u2600\uFE0F"], 1: ["Mainly clear", "\uD83C\uDF24\uFE0F"], 2: ["Partly cloudy", "\u26C5"],
    3: ["Overcast", "\u2601\uFE0F"], 45: ["Fog", "\uD83C\uDF2B\uFE0F"], 48: ["Rime fog", "\uD83C\uDF2B\uFE0F"],
    51: ["Light drizzle", "\uD83C\uDF26\uFE0F"], 53: ["Drizzle", "\uD83C\uDF26\uFE0F"], 55: ["Heavy drizzle", "\uD83C\uDF27\uFE0F"],
    56: ["Freezing drizzle", "\uD83C\uDF27\uFE0F"], 57: ["Freezing drizzle", "\uD83C\uDF27\uFE0F"],
    61: ["Light rain", "\uD83C\uDF26\uFE0F"], 63: ["Rain", "\uD83C\uDF27\uFE0F"], 65: ["Heavy rain", "\uD83C\uDF27\uFE0F"],
    66: ["Freezing rain", "\uD83C\uDF27\uFE0F"], 67: ["Freezing rain", "\uD83C\uDF27\uFE0F"],
    71: ["Light snow", "\uD83C\uDF28\uFE0F"], 73: ["Snow", "\uD83C\uDF28\uFE0F"], 75: ["Heavy snow", "\u2744\uFE0F"],
    77: ["Snow grains", "\u2744\uFE0F"], 80: ["Rain showers", "\uD83C\uDF26\uFE0F"], 81: ["Rain showers", "\uD83C\uDF27\uFE0F"],
    82: ["Violent showers", "\u26C8\uFE0F"], 85: ["Snow showers", "\uD83C\uDF28\uFE0F"], 86: ["Snow showers", "\uD83C\uDF28\uFE0F"],
    95: ["Thunderstorm", "\u26C8\uFE0F"], 96: ["Thunderstorm with hail", "\u26C8\uFE0F"], 99: ["Thunderstorm with hail", "\u26C8\uFE0F"]
  };
  function weatherInfo(code) { return WEATHER[code] || ["Unknown", "\uD83C\uDF21\uFE0F"]; }

  var QUOTES = [
    ["A journey of a thousand miles begins with a single step.", "Lao Tzu"],
    ["Well begun is half done.", "Aristotle"],
    ["The unexamined life is not worth living.", "Socrates"],
    ["Fortune favors the bold.", "Virgil"],
    ["Energy and persistence conquer all things.", "Benjamin Franklin"],
    ["The best way out is always through.", "Robert Frost"],
    ["Nothing in life is to be feared, it is only to be understood.", "Marie Curie"],
    ["No man ever steps in the same river twice.", "Heraclitus"],
    ["Great things are done by a series of small things brought together.", "Vincent van Gogh"]
  ];

  // ---------- the widgets ----------
  function buildClock(body) {
    var time = el("div", "fw-time");
    var date = el("div", "fw-small");
    body.appendChild(time);
    body.appendChild(date);
    function tick() {
      var now = new Date();
      time.textContent = now.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"});
      date.textContent = now.toLocaleDateString([], {weekday: "long", day: "numeric", month: "long", year: "numeric"});
    }
    tick();
    var timer = setInterval(tick, 1000);
    return {destroy: function () { clearInterval(timer); }};
  }

  function buildWeather(body, ctx) {
    var cfg = ctx.cfg;
    if (!cfg.unit) cfg.unit = "c";
    if (!cfg.city) cfg.city = "";
    var form = el("form", "fw-form");
    var input = el("input", "fw-input");
    input.placeholder = "City, e.g. Athens";
    input.maxLength = 80;
    input.value = cfg.city;
    var go = el("button", "fw-btn", "Go");
    go.type = "submit";
    form.appendChild(input);
    form.appendChild(go);
    var out = el("div", "fw-weather");
    var foot = el("div", "fw-foot");
    var unitButton = el("button", "fw-link");
    unitButton.type = "button";
    var refresh = el("button", "fw-link", "Refresh");
    refresh.type = "button";
    foot.appendChild(unitButton);
    foot.appendChild(refresh);
    body.appendChild(form);
    body.appendChild(out);
    body.appendChild(foot);

    function unitLabel() { unitButton.textContent = cfg.unit === "f" ? "Show \u00B0C" : "Show \u00B0F"; }
    function load() {
      if (!cfg.city) { out.textContent = "Type your city above to see the weather."; return; }
      out.textContent = "Loading\u2026";
      send("fetch", {kind: "weather", city: cfg.city, unit: cfg.unit});
    }
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      cfg.city = input.value.trim();
      ctx.save();
      load();
    });
    unitButton.addEventListener("click", function () {
      cfg.unit = cfg.unit === "f" ? "c" : "f";
      ctx.save();
      unitLabel();
      load();
    });
    refresh.addEventListener("click", load);
    var timer = setInterval(load, 30 * 60 * 1000);
    unitLabel();
    load();

    return {
      kind: "weather",
      destroy: function () { clearInterval(timer); },
      onData: function (payload) {
        out.textContent = "";
        if (!payload.ok) { out.appendChild(el("div", "fw-error", payload.error)); return; }
        var d = payload.data;
        var info = weatherInfo(d.code);
        var deg = d.unit === "f" ? "\u00B0F" : "\u00B0C";
        var top = el("div", "fw-wtop");
        top.appendChild(el("div", "fw-wicon", info[1]));
        var main = el("div");
        main.appendChild(el("div", "fw-wtemp", Math.round(d.temp) + deg));
        main.appendChild(el("div", "fw-small", info[0]));
        top.appendChild(main);
        out.appendChild(top);
        out.appendChild(el("div", "fw-wplace", d.place + (d.country ? ", " + d.country : "")));
        out.appendChild(el("div", "fw-small",
          "Feels like " + Math.round(d.feels) + deg + "  \u00B7  Humidity " + d.humidity + "%  \u00B7  Wind " +
          Math.round(d.wind) + (d.unit === "f" ? " mph" : " km/h")));
        var days = el("div", "fw-days");
        d.days.slice(1).forEach(function (day) {
          var box = el("div", "fw-day");
          var name = new Date(day.date + "T12:00:00").toLocaleDateString([], {weekday: "short"});
          box.appendChild(el("div", "fw-small", name));
          box.appendChild(el("div", "fw-dayicon", weatherInfo(day.code)[1]));
          box.appendChild(el("div", "fw-small", Math.round(day.max) + "\u00B0 / " + Math.round(day.min) + "\u00B0"));
          days.appendChild(box);
        });
        out.appendChild(days);
      }
    };
  }

  function buildNews(body, ctx) {
    var cfg = ctx.cfg;
    if (!cfg.source) cfg.source = "bbc";
    if (!cfg.custom) cfg.custom = "";
    var select = el("select", "fw-input");
    BOOT.newsSources.forEach(function (source) {
      var option = el("option", "", source.name);
      option.value = source.id;
      select.appendChild(option);
    });
    var own = el("option", "", "My own RSS feed\u2026");
    own.value = "custom";
    select.appendChild(own);
    select.value = cfg.source;
    var customInput = el("input", "fw-input");
    customInput.placeholder = "https://example.com/feed.xml";
    customInput.value = cfg.custom;
    var list = el("div", "fw-news");
    body.appendChild(select);
    body.appendChild(customInput);
    body.appendChild(list);

    function syncCustom() { customInput.style.display = select.value === "custom" ? "" : "none"; }
    function canLoad() { return cfg.source !== "custom" || !!cfg.custom; }
    function load() {
      if (!canLoad()) { list.textContent = "Paste a feed address above."; return; }
      list.textContent = "Loading\u2026";
      send("fetch", {kind: "news", source: cfg.source, custom: cfg.custom});
    }
    select.addEventListener("change", function () {
      cfg.source = select.value;
      ctx.save();
      syncCustom();
      load();
    });
    customInput.addEventListener("change", function () {
      cfg.custom = customInput.value.trim();
      ctx.save();
      load();
    });
    var timer = setInterval(load, 15 * 60 * 1000);
    syncCustom();
    load();

    return {
      kind: "news",
      destroy: function () { clearInterval(timer); },
      onData: function (payload) {
        list.textContent = "";
        if (!payload.ok) { list.appendChild(el("div", "fw-error", payload.error)); return; }
        payload.data.items.forEach(function (item) {
          var link = el("a", "fw-news-item");
          link.href = item.link;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.appendChild(el("span", "fw-news-title", item.title));
          var when = ago(item.time);
          if (when) link.appendChild(el("span", "fw-small", when));
          list.appendChild(link);
        });
      }
    };
  }

  function buildProfiles(body) {
    var list = el("div", "fw-list");
    BOOT.profiles.all.forEach(function (name) {
      if (name === BOOT.profiles.current) {
        list.appendChild(el("div", "fw-item fw-current", "\u25CF  " + name + "  (this window)"));
      } else {
        var link = el("a", "fw-item", "\u25CB  " + name);
        link.href = "browser://openprofile?name=" + encodeURIComponent(name);
        list.appendChild(link);
      }
    });
    var add = el("a", "fw-item", "\uFF0B  New profile");
    add.href = "browser://newprofile";
    list.appendChild(add);
    body.appendChild(list);
    return {};
  }

  function buildNotes(body, ctx) {
    var area = el("textarea", "fw-notes");
    area.placeholder = "Write a note\u2026";
    area.maxLength = 5000;
    area.value = ctx.cfg.text || "";
    area.addEventListener("input", function () {
      ctx.cfg.text = area.value;
      ctx.save();
    });
    body.appendChild(area);
    return {};
  }

  function buildTodo(body, ctx) {
    var cfg = ctx.cfg;
    if (!Array.isArray(cfg.items)) cfg.items = [];
    var form = el("form", "fw-form");
    var input = el("input", "fw-input");
    input.placeholder = "Add a task";
    input.maxLength = 200;
    var add = el("button", "fw-btn", "+");
    add.type = "submit";
    form.appendChild(input);
    form.appendChild(add);
    var list = el("div", "fw-list");
    body.appendChild(form);
    body.appendChild(list);

    function render() {
      list.textContent = "";
      cfg.items.forEach(function (item, index) {
        var row = el("label", "fw-todo" + (item.d ? " fw-done" : ""));
        var box = document.createElement("input");
        box.type = "checkbox";
        box.checked = !!item.d;
        box.addEventListener("change", function () { item.d = box.checked; ctx.save(); render(); });
        var del = el("button", "fw-x", "\u2715");
        del.type = "button";
        del.title = "Delete";
        del.addEventListener("click", function (e) {
          e.preventDefault();
          cfg.items.splice(index, 1);
          ctx.save();
          render();
        });
        row.appendChild(box);
        row.appendChild(el("span", "fw-todo-text", item.t));
        row.appendChild(del);
        list.appendChild(row);
      });
      if (!cfg.items.length) list.appendChild(el("div", "fw-small", "Nothing to do. Enjoy!"));
    }
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var text = input.value.trim();
      if (!text || cfg.items.length >= 50) return;
      cfg.items.push({t: text.slice(0, 200), d: false});
      input.value = "";
      ctx.save();
      render();
    });
    render();
    return {};
  }

  function linkList(items, emptyText) {
    var list = el("div", "fw-list");
    if (!items.length) list.appendChild(el("div", "fw-small", emptyText));
    items.forEach(function (item) {
      var link = el("a", "fw-item", item.title || item.url);
      link.href = item.url;
      link.title = item.url;
      list.appendChild(link);
    });
    return list;
  }
  function buildBookmarks(body) {
    body.appendChild(linkList(BOOT.bookmarks, "No bookmarks yet. Press Ctrl+D on a page."));
    return {};
  }
  function buildHistory(body) {
    body.appendChild(linkList(BOOT.history, "Pages you visit will show up here."));
    return {};
  }

  function buildCalculator(body) {
    var screen = el("div", "fw-calc-screen", "0");
    var grid = el("div", "fw-calc-grid");
    var acc = null, op = null, cur = "0", fresh = true;
    function compute() {
      var value = parseFloat(cur);
      if (acc === null || op === null) { acc = value; return; }
      if (op === "+") acc += value;
      else if (op === "\u2212") acc -= value;
      else if (op === "\u00D7") acc *= value;
      else if (op === "\u00F7") acc = value === 0 ? NaN : acc / value;
      cur = isFinite(acc) ? String(parseFloat(acc.toPrecision(12))) : "Error";
    }
    function press(key) {
      if (cur === "Error") { acc = null; op = null; cur = "0"; fresh = true; }
      if (/^[0-9]$/.test(key)) {
        cur = (fresh || cur === "0") ? key : cur + key;
        fresh = false;
      } else if (key === ".") {
        if (fresh) { cur = "0."; fresh = false; } else if (cur.indexOf(".") < 0) { cur += "."; }
      } else if (key === "C") {
        acc = null; op = null; cur = "0"; fresh = true;
      } else if (key === "\u232B") {
        if (!fresh) cur = cur.length > 1 ? cur.slice(0, -1) : "0";
      } else if (key === "=") {
        compute(); op = null; fresh = true;
      } else {
        compute(); op = key; fresh = true;
      }
      screen.textContent = cur;
    }
    ["C", "\u232B", "\u00F7", "\u00D7", "7", "8", "9", "\u2212", "4", "5", "6", "+", "1", "2", "3", "=", "0", "."]
      .forEach(function (key) {
        var button = el("button", "fw-key" + (key === "0" ? " fw-wide" : ""), key);
        button.type = "button";
        button.addEventListener("click", function () { press(key); });
        grid.appendChild(button);
      });
    body.appendChild(screen);
    body.appendChild(grid);
    return {};
  }

  function buildTimer(body, ctx) {
    var cfg = ctx.cfg;
    if (!cfg.minutes) cfg.minutes = 25;
    var display = el("div", "fw-time");
    var row = el("div", "fw-form");
    var minutes = el("input", "fw-input");
    minutes.type = "number";
    minutes.min = "1";
    minutes.max = "180";
    minutes.value = cfg.minutes;
    var start = el("button", "fw-btn", "Start");
    start.type = "button";
    var reset = el("button", "fw-btn", "Reset");
    reset.type = "button";
    row.appendChild(minutes);
    row.appendChild(start);
    row.appendChild(reset);
    body.appendChild(display);
    body.appendChild(el("div", "fw-small", "Minutes:"));
    body.appendChild(row);

    var remaining = cfg.minutes * 60;
    var ticking = null;
    function show() {
      var m = Math.floor(remaining / 60), s = remaining % 60;
      display.textContent = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    }
    function stop() {
      if (ticking) { clearInterval(ticking); ticking = null; }
      start.textContent = "Start";
    }
    function beep() {
      try {
        var audio = new (window.AudioContext || window.webkitAudioContext)();
        var tone = audio.createOscillator();
        tone.connect(audio.destination);
        tone.frequency.value = 880;
        tone.start();
        setTimeout(function () { tone.stop(); audio.close(); }, 500);
      } catch (err) {}
    }
    start.addEventListener("click", function () {
      if (ticking) { stop(); return; }
      if (remaining <= 0) remaining = cfg.minutes * 60;
      start.textContent = "Pause";
      ticking = setInterval(function () {
        remaining -= 1;
        show();
        if (remaining <= 0) { stop(); display.textContent = "Time's up!"; beep(); }
      }, 1000);
    });
    reset.addEventListener("click", function () { stop(); remaining = cfg.minutes * 60; show(); });
    minutes.addEventListener("change", function () {
      var value = Math.min(180, Math.max(1, parseInt(minutes.value, 10) || 25));
      cfg.minutes = value;
      minutes.value = value;
      ctx.save();
      stop();
      remaining = value * 60;
      show();
    });
    show();
    return {destroy: function () { if (ticking) clearInterval(ticking); }};
  }

  function buildQuote(body, ctx) {
    var cfg = ctx.cfg;
    var text = el("div", "fw-quote");
    var by = el("div", "fw-small fw-quote-by");
    var another = el("button", "fw-link", "Another one");
    another.type = "button";
    body.appendChild(text);
    body.appendChild(by);
    body.appendChild(another);
    function show() {
      var day = Math.floor(Date.now() / 86400000);
      var quote = QUOTES[(day + (cfg.shift || 0)) % QUOTES.length];
      text.textContent = "\u201C" + quote[0] + "\u201D";
      by.textContent = "\u2014 " + quote[1];
    }
    another.addEventListener("click", function () {
      cfg.shift = ((cfg.shift || 0) + 1) % 1000;
      ctx.save();
      show();
    });
    show();
    return {};
  }

  var WIDGETS = [
    {id: "clock", name: "Clock", icon: "\uD83D\uDD52", w: 250, pos: {x: 0.03, y: 0.07}, build: buildClock},
    {id: "weather", name: "Weather", icon: "\u26C5", w: 290, pos: {x: 0.03, y: 0.26}, build: buildWeather},
    {id: "news", name: "News", icon: "\uD83D\uDCF0", w: 340, pos: {x: 0.69, y: 0.07}, build: buildNews},
    {id: "profiles", name: "Profiles", icon: "\uD83D\uDC64", w: 230, pos: {x: 0.03, y: 0.68}, build: buildProfiles},
    {id: "notes", name: "Notes", icon: "\uD83D\uDCDD", w: 260, pos: {x: 0.72, y: 0.62}, build: buildNotes},
    {id: "todo", name: "To-do list", icon: "\u2705", w: 270, pos: {x: 0.72, y: 0.38}, build: buildTodo},
    {id: "bookmarks", name: "Bookmarks", icon: "\u2B50", w: 250, pos: {x: 0.23, y: 0.68}, build: buildBookmarks},
    {id: "history", name: "Recently visited", icon: "\uD83D\uDD58", w: 250, pos: {x: 0.43, y: 0.68}, build: buildHistory},
    {id: "calculator", name: "Calculator", icon: "\uD83E\uDDEE", w: 220, pos: {x: 0.23, y: 0.07}, build: buildCalculator},
    {id: "timer", name: "Timer", icon: "\u23F1\uFE0F", w: 240, pos: {x: 0.45, y: 0.07}, build: buildTimer},
    {id: "quote", name: "Daily quote", icon: "\uD83D\uDCAC", w: 280, pos: {x: 0.45, y: 0.3}, build: buildQuote}
  ];
  var byId = {};
  WIDGETS.forEach(function (def) { byId[def.id] = def; });

  // ---------- layer, placing and dragging ----------
  var layer = el("div");
  layer.id = "fw-layer";
  document.body.appendChild(layer);
  var live = {};
  var topZ = 10;

  function defaultPos(id) {
    var x = byId[id].pos.x, y = byId[id].pos.y, tries = 0;
    function clash() {
      return Object.keys(live).some(function (other) {
        if (other === id) return false;
        var p = state.pos[other] || byId[other].pos;
        return Math.abs(p.x - x) < 0.02 && Math.abs(p.y - y) < 0.03;
      });
    }
    while (clash() && tries < 12) { x = Math.min(0.9, x + 0.03); y = Math.min(0.9, y + 0.05); tries++; }
    return {x: x, y: y};
  }

  function place(id) {
    var item = live[id];
    if (!item) return;
    var pos = state.pos[id];
    if (!pos) { pos = defaultPos(id); state.pos[id] = pos; save(); }
    var node = item.el;
    var maxX = Math.max(0, window.innerWidth - node.offsetWidth);
    var maxY = Math.max(0, window.innerHeight - node.offsetHeight);
    node.style.left = Math.min(maxX, Math.max(0, pos.x * window.innerWidth)) + "px";
    node.style.top = Math.min(maxY, Math.max(0, pos.y * window.innerHeight)) + "px";
  }

  function makeDraggable(node, handle, id) {
    handle.addEventListener("pointerdown", function (event) {
      if (event.button !== 0 || (event.target.closest && event.target.closest("button"))) return;
      var rect = node.getBoundingClientRect();
      var dx = event.clientX - rect.left, dy = event.clientY - rect.top;
      node.style.zIndex = ++topZ;
      node.classList.add("fw-dragging");
      handle.setPointerCapture(event.pointerId);
      function move(e) {
        var x = Math.min(Math.max(0, e.clientX - dx), Math.max(0, window.innerWidth - node.offsetWidth));
        var y = Math.min(Math.max(0, e.clientY - dy), Math.max(0, window.innerHeight - node.offsetHeight));
        node.style.left = x + "px";
        node.style.top = y + "px";
      }
      function up(e) {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", up);
        handle.removeEventListener("pointercancel", up);
        try { handle.releasePointerCapture(e.pointerId); } catch (err) {}
        node.classList.remove("fw-dragging");
        state.pos[id] = {x: node.offsetLeft / window.innerWidth, y: node.offsetTop / window.innerHeight};
        save();
      }
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up);
      handle.addEventListener("pointercancel", up);
      event.preventDefault();
    });
  }

  function createWidget(def) {
    var root = el("div", "fw-card fw-in");
    root.style.width = def.w + "px";
    var head = el("div", "fw-head");
    head.appendChild(el("span", "fw-title", def.icon + "  " + def.name));
    var close = el("button", "fw-x", "\u2715");
    close.type = "button";
    close.title = "Remove this widget";
    head.appendChild(close);
    var body = el("div", "fw-body");
    root.appendChild(head);
    root.appendChild(body);
    layer.appendChild(root);
    var api = def.build(body, {cfg: cfgFor(def.id), save: save}) || {};
    live[def.id] = {el: root, api: api};
    place(def.id);
    makeDraggable(root, head, def.id);
    root.addEventListener("pointerdown", function () { root.style.zIndex = ++topZ; });
    close.addEventListener("click", function () { setEnabled(def.id, false); });
  }

  function setEnabled(id, on) {
    var index = state.enabled.indexOf(id);
    if (on && index < 0) {
      state.enabled.push(id);
      createWidget(byId[id]);
    }
    if (!on && index >= 0) {
      state.enabled.splice(index, 1);
      var item = live[id];
      if (item) {
        if (item.api.destroy) item.api.destroy();
        item.el.remove();
        delete live[id];
      }
    }
    renderPanel();
    save();
  }

  // ---------- the "Widgets" button and its list ----------
  var toggle = el("button", "fw-toggle", "\u229E  Widgets");
  toggle.type = "button";
  var panel = el("div", "fw-panel");
  panel.hidden = true;
  document.body.appendChild(toggle);
  document.body.appendChild(panel);
  toggle.addEventListener("click", function () { panel.hidden = !panel.hidden; });

  function renderPanel() {
    panel.textContent = "";
    panel.appendChild(el("div", "fw-panel-title", "Widgets"));
    WIDGETS.forEach(function (def) {
      var row = el("label", "fw-panel-row");
      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = state.enabled.indexOf(def.id) >= 0;
      box.addEventListener("change", function () { setEnabled(def.id, box.checked); });
      row.appendChild(box);
      row.appendChild(el("span", "", def.icon + "  " + def.name));
      panel.appendChild(row);
    });
    var reset = el("button", "fw-btn", "Reset positions");
    reset.type = "button";
    reset.addEventListener("click", function () {
      state.pos = {};
      Object.keys(live).forEach(function (id) { place(id); });
      save();
    });
    panel.appendChild(reset);
    panel.appendChild(el("div", "fw-small", "Drag a widget by its title bar to move it."));
  }

  // data that Python fetched for us (weather, news)
  window.filipsData = function (kind, payload) {
    Object.keys(live).forEach(function (id) {
      var api = live[id].api;
      if (api.kind === kind && api.onData) api.onData(payload);
    });
  };

  window.addEventListener("resize", function () {
    Object.keys(live).forEach(function (id) { place(id); });
  });

  state.enabled.slice().forEach(function (id) {
    if (byId[id]) createWidget(byId[id]);
  });
  renderPanel();
})();
"""


class BrowserPage(QWebEnginePage):
    """The web page inside a tab. Handles two special cases:
    - links that want a new window open in a new tab
    - the home screen's "browser://add" and "browser://remove" links
    """

    def __init__(self, profile, view, main_window):
        super().__init__(profile, view)
        self.main_window = main_window
        self.view_ref = view
        self.permissionRequested.connect(main_window.handle_permission)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "browser":
            # Do the work after this call returns, so the page isn't changed mid-navigation.
            QTimer.singleShot(
                0, lambda: self.main_window.handle_home_action(url, self.view_ref)
            )
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def createWindow(self, _window_type):
        return self.main_window.add_tab(home=False).page()

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        if message.startswith(HOME_PREFIX):
            self.main_window.on_home_message(self.view_ref, message[len(HOME_PREFIX):])
            return
        if message.startswith(PASSWORD_PREFIX):
            # A login was typed in (see PASSWORD_SCRIPT). Never print it anywhere.
            self.main_window.on_password_message(self, message[len(PASSWORD_PREFIX):])
            return
        super().javaScriptConsoleMessage(level, message, line_number, source_id)


class BrowserView(QWebEngineView):
    """One web page with its own tab."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.showing_home = False
        self.loading = False
        self.progress = 0
        self.setPage(BrowserPage(main_window.profile, self, main_window))


class GeminiWorker(QThread):
    """Sends the conversation to Google's Gemini API without freezing the browser."""

    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, api_key, model, history):
        super().__init__()
        self.api_key = api_key
        self.model = model.removeprefix("models/")
        self.history = history

    def run(self):
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(self.model, safe='-._')}:generateContent"
        )
        body = json.dumps(
            {
                "system_instruction": {"parts": [{"text": ASSISTANT_PROMPT}]},
                "contents": self.history,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts).strip()
            if not text:
                raise ValueError("empty answer")
            self.succeeded.emit(text)
        except urllib.error.HTTPError as error:
            try:
                message = json.loads(error.read().decode("utf-8"))["error"]["message"]
            except Exception:
                message = str(error.reason)
            self.failed.emit(f"Gemini error ({error.code}): {message}")
        except (KeyError, IndexError, ValueError):
            self.failed.emit(
                "Gemini did not return an answer (it may have been blocked by its safety filters)."
            )
        except Exception as error:
            self.failed.emit(f"Could not reach Gemini: {error}")


class ChatWindow(QWidget):
    """The Jonathan AI Assistant chat window."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.history = []  # what gets sent to Gemini
        self.markdown = ""  # what is shown on screen
        self.worker = None

        self.setWindowTitle(ASSISTANT_NAME)
        self.resize(520, 660)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText(f"Message {ASSISTANT_NAME}…")
        self.input.returnPressed.connect(self.send)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send)
        self.new_chat_button = QPushButton("New chat")
        self.new_chat_button.clicked.connect(self.reset)

        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(self.send_button)
        row.addWidget(self.new_chat_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.transcript)
        layout.addLayout(row)

        self.reset()

    def reset(self):
        if self.worker is not None:
            return  # wait for the current answer first
        self.history = []
        self.markdown = (
            f"**{ASSISTANT_NAME}**\n\n"
            f"Hi! I'm Jonathan, your assistant in {APP_NAME}. Ask me anything.\n\n---\n\n"
        )
        self.render()

    def render(self, thinking=False):
        text = self.markdown + ("*Jonathan is thinking…*" if thinking else "")
        self.transcript.setMarkdown(text)
        bar = self.transcript.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_busy(self, busy):
        self.input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.new_chat_button.setEnabled(not busy)

    def send(self):
        if self.worker is not None:
            return
        text = self.input.text().strip()
        if not text:
            return
        settings = self.browser.settings
        api_key = settings.get("gemini_api_key", "").strip()
        if not api_key:
            self.markdown += (
                f"**{ASSISTANT_NAME}**\n\n"
                "I need a Gemini API key first. Get a free key from Google AI Studio "
                "(aistudio.google.com), then open the ⚙ Settings window and paste it "
                "into the \"Gemini API key\" box.\n\n---\n\n"
            )
            self.render()
            return

        self.input.clear()
        self.history.append({"role": "user", "parts": [{"text": text}]})
        self.markdown += f"**You**\n\n{text}\n\n"
        self.set_busy(True)
        self.render(thinking=True)

        model = settings.get("gemini_model", GEMINI_MODEL).strip() or GEMINI_MODEL
        # Send the last 19 messages (ends with the new question, starts with a user message).
        self.worker = GeminiWorker(api_key, model, self.history[-19:])
        self.worker.succeeded.connect(self.on_reply)
        self.worker.failed.connect(self.on_error)
        self.worker.start()

    def on_reply(self, text):
        self.history.append({"role": "model", "parts": [{"text": text}]})
        self.markdown += f"**{ASSISTANT_NAME}**\n\n{text}\n\n---\n\n"
        self.finish()

    def on_error(self, message):
        self.history.pop()  # forget the question that failed, so you can ask again
        self.markdown += f"**{ASSISTANT_NAME}**\n\n⚠ {message}\n\n---\n\n"
        self.finish()

    def finish(self):
        self.worker.wait()
        self.worker = None
        self.set_busy(False)
        self.render()
        self.input.setFocus()


class DownloadRow(QFrame):
    """One download in the downloads window."""

    def __init__(self, download):
        super().__init__()
        self.download = download
        self.path = os.path.join(download.downloadDirectory(), download.downloadFileName())
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self.name_label = QLabel(download.downloadFileName())
        self.name_label.setStyleSheet("font-weight: bold;")
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.status_label = QLabel()

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self.open_file)
        self.folder_button = QPushButton("Show in folder")
        self.folder_button.clicked.connect(self.show_in_folder)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(lambda: self.download.cancel())

        buttons = QHBoxLayout()
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.folder_button)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.name_label)
        layout.addWidget(self.bar)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)

        download.receivedBytesChanged.connect(self.update_progress)
        download.totalBytesChanged.connect(self.update_progress)
        download.stateChanged.connect(self.update_state)
        self.update_progress()
        self.update_state()

    def is_running(self):
        states = QWebEngineDownloadRequest.DownloadState
        return self.download.state() in (states.DownloadRequested, states.DownloadInProgress)

    def update_progress(self):
        if not self.is_running():
            return
        received = self.download.receivedBytes()
        total = self.download.totalBytes()
        if total > 0:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(received * 100 / total))
            self.status_label.setText(f"{human_size(received)} of {human_size(total)}")
        else:
            self.bar.setRange(0, 0)  # size unknown: show a busy bar
            self.status_label.setText(human_size(received))

    def update_state(self, _state=None):
        states = QWebEngineDownloadRequest.DownloadState
        state = self.download.state()
        done = state == states.DownloadCompleted
        self.cancel_button.setVisible(self.is_running())
        self.open_button.setVisible(done)
        self.folder_button.setVisible(done)
        if self.is_running():
            return
        self.bar.setRange(0, 100)
        if done:
            self.bar.setValue(100)
            self.status_label.setText(f"Finished \u2013 {human_size(self.download.receivedBytes())}")
        elif state == states.DownloadCancelled:
            self.bar.setValue(0)
            self.status_label.setText("Cancelled")
        else:
            self.bar.setValue(0)
            self.status_label.setText("Failed: " + self.download.interruptReasonString())

    def open_file(self):
        if os.path.splitext(self.path)[1].lower() in RISKY_EXTENSIONS:
            answer = QMessageBox.warning(
                self,
                "Open file?",
                f"{os.path.basename(self.path)} is a program or script.\n"
                "Only open it if you trust where it came from.\n\nOpen it anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))

    def show_in_folder(self):
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(self.path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.path)))


class DownloadsWindow(QWidget):
    """The downloads list."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.setWindowTitle("Downloads")
        self.resize(560, 460)

        self.empty_label = QLabel("No downloads yet.")
        self.rows_layout = QVBoxLayout()
        self.rows_layout.addWidget(self.empty_label)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addLayout(self.rows_layout)
        container_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        clear = QPushButton("Clear finished")
        clear.clicked.connect(self.clear_finished)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(clear)

    def add_download(self, download):
        row = DownloadRow(download)
        self.rows.append(row)
        self.rows_layout.insertWidget(0, row)  # newest on top
        self.empty_label.hide()

    def clear_finished(self):
        for row in list(self.rows):
            if not row.is_running():
                self.rows.remove(row)
                row.setParent(None)
                row.deleteLater()
        self.empty_label.setVisible(not self.rows)


class HistoryWindow(QWidget):
    """The list of pages you visited."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.store = browser.history
        self.setWindowTitle("History")
        self.resize(640, 520)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search history")
        self.search.textChanged.connect(self.refresh)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.itemDoubleClicked.connect(self.open_item)

        delete_button = QPushButton("Delete selected")
        delete_button.clicked.connect(self.delete_selected)
        clear_button = QPushButton("Clear all history…")
        clear_button.clicked.connect(self.clear_all)
        buttons = QHBoxLayout()
        buttons.addWidget(delete_button)
        buttons.addWidget(clear_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        layout.addLayout(buttons)

        self.store.changed.connect(self.on_changed)

    def on_changed(self):
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def refresh(self, *_):
        query = self.search.text().strip().lower()
        self.list.clear()
        shown = 0
        for index in range(len(self.store.entries) - 1, -1, -1):  # newest first
            entry = self.store.entries[index]
            if query and query not in entry["url"].lower() and query not in entry["title"].lower():
                continue
            when = datetime.fromtimestamp(entry["time"]).strftime("%d %b %Y, %H:%M")
            item = QListWidgetItem(f"{entry['title'] or entry['url']}\n{entry['url']}  ·  {when}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(item)
            shown += 1
            if shown >= 1000:
                break

    def open_item(self, item):
        index = item.data(Qt.ItemDataRole.UserRole)
        if 0 <= index < len(self.store.entries):
            self.browser.add_tab(url=self.store.entries[index]["url"])

    def delete_selected(self):
        indices = [item.data(Qt.ItemDataRole.UserRole) for item in self.list.selectedItems()]
        if indices:
            self.store.remove_indices(indices)

    def clear_all(self):
        answer = QMessageBox.question(
            self,
            "Clear history",
            "Delete all of your browsing history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.store.clear()


class SideBar(QFrame):
    """The strip of app icons on the left (like Opera GX)."""

    service_clicked = Signal(object)
    customize_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.setStyleSheet(SIDEBAR_STYLE)
        self.setFixedWidth(58)
        self.buttons = {}
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(8, 10, 8, 10)
        self.column.setSpacing(6)

    def set_services(self, services, active_id):
        while self.column.count():
            item = self.column.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.buttons = {}
        for service in services:
            button = AnimatedToolButton()
            button.setIcon(make_icon(service))
            button.setToolTip(service["name"])
            button.setCheckable(True)
            button.setChecked(service["id"] == active_id)
            button.setFixedSize(42, 42)
            button.clicked.connect(lambda _c=False, sv=service: self.service_clicked.emit(sv))
            self.column.addWidget(button)
            self.buttons[service["id"]] = button
        self.column.addStretch()
        gear = QToolButton()
        gear.setText("⚙")
        gear.setToolTip("Customize sidebar")
        gear.setFixedSize(42, 42)
        gear.clicked.connect(lambda: self.customize_clicked.emit())
        self.column.addWidget(gear)

    def set_active(self, service_id):
        for sid, button in self.buttons.items():
            button.setChecked(sid == service_id)


class SidePanel(QWidget):
    """The panel that opens next to the sidebar and shows one site (WhatsApp, TikTok...)."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.current_id = None
        self.views = {}
        self.setMinimumWidth(320)

        self.title = QLabel()
        self.title.setStyleSheet("font-weight: bold; font-size: 14px;")

        reload_button = QToolButton()
        reload_button.setText("⟳")
        reload_button.setToolTip("Reload")
        reload_button.clicked.connect(lambda: self.reload())
        open_button = QToolButton()
        open_button.setText("↗")
        open_button.setToolTip("Open in a tab")
        open_button.clicked.connect(lambda: self.open_in_tab())
        close_button = QToolButton()
        close_button.setText("✕")
        close_button.setToolTip("Close panel")
        close_button.clicked.connect(lambda: browser.close_panel())

        header = QHBoxLayout()
        header.setContentsMargins(10, 6, 8, 6)
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(reload_button)
        header.addWidget(open_button)
        header.addWidget(close_button)

        self.stack = QStackedWidget()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.stack)

    def show_service(self, service):
        view = self.views.get(service["id"])
        if view is None:
            view = BrowserView(self.browser)
            view.load(QUrl(service["url"]))
            self.stack.addWidget(view)
            self.views[service["id"]] = view
        self.stack.setCurrentWidget(view)
        self.current_id = service["id"]
        self.title.setText(service["name"])
        self.show()

    def reload(self):
        view = self.views.get(self.current_id)
        if view is not None:
            view.reload()

    def open_in_tab(self):
        view = self.views.get(self.current_id)
        if view is not None:
            self.browser.add_tab(url=view.url().toString())

    def forget(self, service_id):
        view = self.views.pop(service_id, None)
        if view is not None:
            self.stack.removeWidget(view)
            view.deleteLater()
        if self.current_id == service_id:
            self.current_id = None


class SidebarDialog(QDialog):
    """Choose which apps appear in the sidebar."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setWindowTitle("Customize sidebar")
        self.setMinimumSize(380, 500)

        self.show_box = QCheckBox("Show the sidebar")
        self.show_box.setChecked(browser.settings.get("sidebar_visible", True))
        self.show_box.toggled.connect(lambda on: browser.set_setting("sidebar_visible", on))

        hint = QLabel("Tick the apps you want in the sidebar.")
        self.list = QListWidget()
        self.list.itemChanged.connect(self.on_item_changed)

        add_button = QPushButton("Add your own site…")
        add_button.clicked.connect(self.add_site)
        remove_button = QPushButton("Remove selected custom site")
        remove_button.clicked.connect(self.remove_site)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.show_box)
        layout.addWidget(hint)
        layout.addWidget(self.list)
        layout.addWidget(add_button)
        layout.addWidget(remove_button)
        layout.addWidget(close_button)

        self.populate()

    def populate(self):
        self.show_box.setChecked(self.browser.settings.get("sidebar_visible", True))
        enabled = set(self.browser.enabled_service_ids())
        self.list.blockSignals(True)
        self.list.clear()
        for service in self.browser.all_services():
            item = QListWidgetItem(make_icon(service), service["name"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = service["id"] in enabled
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, service["id"])
            self.list.addItem(item)
        self.list.blockSignals(False)

    def on_item_changed(self, _item):
        ids = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        self.browser.set_setting("sidebar_enabled", json.dumps(ids))

    def add_site(self):
        dialog = AddShortcutDialog(self, "Add a site to the sidebar")
        if not dialog.exec():
            return
        site = dialog.shortcut()
        if site is None:
            QMessageBox.warning(self, "Invalid address", "Please enter a valid web address.")
            return
        customs = self.browser.load_json_list("sidebar_custom", [])
        customs.append(site)
        enabled = self.browser.enabled_service_ids()
        enabled.append("custom:" + site["url"])
        self.browser.settings.set("sidebar_custom", json.dumps(customs))
        self.browser.set_setting("sidebar_enabled", json.dumps(enabled))
        self.populate()

    def remove_site(self):
        item = self.list.currentItem()
        if item is None:
            return
        service_id = item.data(Qt.ItemDataRole.UserRole)
        if not service_id.startswith("custom:"):
            QMessageBox.information(
                self, "Built-in app", "Only sites you added yourself can be removed. Untick this one to hide it."
            )
            return
        url = service_id[len("custom:"):]
        customs = [c for c in self.browser.load_json_list("sidebar_custom", []) if c.get("url") != url]
        enabled = [i for i in self.browser.enabled_service_ids() if i != service_id]
        self.browser.settings.set("sidebar_custom", json.dumps(customs))
        self.browser.set_setting("sidebar_enabled", json.dumps(enabled))
        self.populate()


class PermissionsDialog(QDialog):
    """Sites you have allowed or blocked (notifications, location...)."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.permissions = []
        self.setWindowTitle("Site permissions")
        self.setMinimumSize(460, 360)

        note = QLabel(
            "Camera, microphone and mouse lock are asked about every time. "
            "Your saved answers for notifications, location and clipboard are listed here."
        )
        note.setWordWrap(True)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        reset_button = QPushButton("Reset selected (ask again)")
        reset_button.clicked.connect(self.reset_selected)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addWidget(self.list)
        layout.addWidget(reset_button)
        layout.addWidget(close_button)

    def showEvent(self, event):
        self.populate()
        super().showEvent(event)

    def populate(self):
        self.list.clear()
        self.permissions = []
        states = QWebEnginePermission.State
        try:
            found = self.browser.profile.listAllPermissions()
        except AttributeError:
            found = []
        for permission in found:
            state = permission.state()
            if state not in (states.Granted, states.Denied):
                continue
            name = PERMISSION_NAMES.get(permission.permissionType(), "Other")
            origin = permission.origin()
            site = origin.host() or origin.toString()
            answer = "Allowed" if state == states.Granted else "Blocked"
            self.list.addItem(f"{site} – {name}: {answer}")
            self.permissions.append(permission)

    def reset_selected(self):
        for item in self.list.selectedItems():
            self.permissions[self.list.row(item)].reset()
        self.populate()


class AddShortcutDialog(QDialog):
    """Asks for a website to add to the home screen."""

    def __init__(self, parent, title="Add site to home screen"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Optional, e.g. YouTube")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("e.g. youtube.com")

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Address:", self.url_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def shortcut(self):
        """Return {"name", "url"} or None if the address isn't a valid web address."""
        url = self.url_edit.text().strip()
        if not url:
            return None
        if "://" not in url:
            url = "https://" + url
        parsed = QUrl(url)
        if parsed.scheme() not in ("http", "https") or not parsed.host():
            return None
        name = self.name_edit.text().strip() or parsed.host().removeprefix("www.")
        return {"name": name, "url": url}


class BookmarksWindow(QWidget):
    """The list of saved bookmarks."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.store = browser.bookmarks
        self.setWindowTitle("Bookmarks")
        self.resize(660, 540)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search bookmarks")
        self.search.textChanged.connect(self.refresh)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.itemDoubleClicked.connect(self.open_item)

        open_button = QPushButton("Open in new tab")
        open_button.clicked.connect(self.open_selected)
        delete_button = QPushButton("Delete selected")
        delete_button.clicked.connect(self.delete_selected)
        import_button = QPushButton("Import\u2026")
        import_button.clicked.connect(lambda: browser.import_bookmarks())
        export_button = QPushButton("Export\u2026")
        export_button.clicked.connect(lambda: browser.export_bookmarks())
        buttons = QHBoxLayout()
        for button in (open_button, delete_button, import_button, export_button):
            buttons.addWidget(button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        layout.addLayout(buttons)

        self.store.changed.connect(self.on_changed)

    def on_changed(self):
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def refresh(self, *_):
        query = self.search.text().strip().lower()
        self.list.clear()
        order = sorted(
            range(len(self.store.entries)),
            key=lambda i: (self.store.entries[i]["folder"].lower(), self.store.entries[i]["title"].lower()),
        )
        for index in order:
            entry = self.store.entries[index]
            if query and query not in entry["url"].lower() and query not in entry["title"].lower():
                continue
            where = f"  \u00b7  {entry['folder']}" if entry["folder"] else ""
            item = QListWidgetItem(f"{entry['title']}\n{entry['url']}{where}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(item)

    def open_item(self, item):
        index = item.data(Qt.ItemDataRole.UserRole)
        if 0 <= index < len(self.store.entries):
            self.browser.add_tab(url=self.store.entries[index]["url"])

    def open_selected(self):
        for item in self.list.selectedItems():
            self.open_item(item)

    def delete_selected(self):
        indices = [item.data(Qt.ItemDataRole.UserRole) for item in self.list.selectedItems()]
        if indices:
            self.store.remove_indices(indices)


class PasswordEntryDialog(QDialog):
    """Add or edit one saved login."""

    def __init__(self, parent, site="", username="", password=""):
        super().__init__(parent)
        self.setWindowTitle("Saved password")
        self.setMinimumWidth(380)

        self.site_edit = QLineEdit(site)
        self.site_edit.setPlaceholderText("e.g. example.com")
        self.user_edit = QLineEdit(username)
        self.pass_edit = QLineEdit(password)
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        show_box = QCheckBox("Show password")
        show_box.toggled.connect(
            lambda on: self.pass_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )

        form = QFormLayout()
        form.addRow("Website:", self.site_edit)
        form.addRow("Username:", self.user_edit)
        form.addRow("Password:", self.pass_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(show_box)
        layout.addWidget(buttons)

    def values(self):
        """(origin, username, password), or None if the website or password is missing."""
        origin = origin_of(self.site_edit.text())
        if not origin or not self.pass_edit.text():
            return None
        return origin, self.user_edit.text().strip(), self.pass_edit.text()


MASK = "\u2022" * 8


class PasswordsWindow(QWidget):
    """The saved passwords. Only opened after the browser password has been typed in."""

    def __init__(self, browser):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.browser = browser
        self.vault = browser.vault
        self.setWindowTitle("Saved passwords")
        self.resize(780, 540)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search saved passwords")
        self.search.textChanged.connect(self.refresh)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Website", "Username", "Password"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)

        self.status = QLabel(
            "Passwords are encrypted with your browser password. Exported files are NOT encrypted."
        )
        self.status.setWordWrap(True)

        def make_button(text, handler):
            button = QPushButton(text)
            button.clicked.connect(lambda: handler())
            return button

        first_row = QHBoxLayout()
        for text, handler in [
            ("Show / hide", self.toggle_show),
            ("Copy password", self.copy_password),
            ("Copy username", self.copy_username),
            ("Add\u2026", self.add_entry),
            ("Edit\u2026", self.edit_entry),
            ("Delete", self.delete_selected),
        ]:
            first_row.addWidget(make_button(text, handler))
        second_row = QHBoxLayout()
        for text, handler in [
            ("Import from CSV\u2026", self.import_csv),
            ("Export to CSV\u2026", self.export_csv),
            ("Change browser password\u2026", self.change_password),
            ("Close", self.close),
        ]:
            second_row.addWidget(make_button(text, handler))

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.table)
        layout.addWidget(self.status)
        layout.addLayout(first_row)
        layout.addLayout(second_row)

        self.refresh()

    def refresh(self, *_):
        query = self.search.text().strip().lower()
        self.table.setRowCount(0)
        order = sorted(
            range(len(self.vault.entries)),
            key=lambda i: (self.vault.entries[i]["origin"], self.vault.entries[i]["username"].lower()),
        )
        for index in order:
            entry = self.vault.entries[index]
            if query and query not in entry["origin"].lower() and query not in entry["username"].lower():
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            site_item = QTableWidgetItem(entry["origin"])
            site_item.setData(Qt.ItemDataRole.UserRole, index)
            self.table.setItem(row, 0, site_item)
            self.table.setItem(row, 1, QTableWidgetItem(entry["username"]))
            self.table.setItem(row, 2, QTableWidgetItem(MASK))

    def selected_rows(self):
        return sorted({item.row() for item in self.table.selectedItems()})

    def entry_index(self, row):
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def toggle_show(self):
        for row in self.selected_rows():
            item = self.table.item(row, 2)
            entry = self.vault.entries[self.entry_index(row)]
            item.setText(entry["password"] if item.text() == MASK else MASK)

    def copy_to_clipboard(self, text, what):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.status.setText(f"{what} copied.")
        if what == "Password":
            self.status.setText("Password copied. It will be removed from the clipboard in 30 seconds.")
            QTimer.singleShot(
                30000, lambda: clipboard.clear() if clipboard.text() == text else None
            )

    def copy_password(self):
        rows = self.selected_rows()
        if rows:
            self.copy_to_clipboard(self.vault.entries[self.entry_index(rows[0])]["password"], "Password")

    def copy_username(self):
        rows = self.selected_rows()
        if rows:
            self.copy_to_clipboard(self.vault.entries[self.entry_index(rows[0])]["username"], "Username")

    def add_entry(self):
        dialog = PasswordEntryDialog(self)
        if not dialog.exec():
            return
        values = dialog.values()
        if values is None:
            QMessageBox.warning(self, "Missing details", "Please enter a website address and a password.")
            return
        self.vault.add(*values)
        self.refresh()

    def edit_entry(self):
        rows = self.selected_rows()
        if not rows:
            return
        entry = self.vault.entries[self.entry_index(rows[0])]
        dialog = PasswordEntryDialog(self, entry["origin"], entry["username"], entry["password"])
        if not dialog.exec():
            return
        values = dialog.values()
        if values is None:
            QMessageBox.warning(self, "Missing details", "Please enter a website address and a password.")
            return
        entry["origin"], entry["username"], entry["password"] = values
        entry["time"] = time.time()
        self.vault.save()
        self.refresh()

    def delete_selected(self):
        rows = self.selected_rows()
        if not rows:
            return
        answer = QMessageBox.question(
            self,
            "Delete passwords",
            f"Delete {len(rows)} saved password(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for index in sorted({self.entry_index(r) for r in rows}, reverse=True):
            del self.vault.entries[index]
        self.vault.save()
        self.refresh()

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import passwords", "", "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        try:
            rows = parse_password_csv(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Import failed", str(error))
            return
        added, updated = self.vault.add_many(rows)
        self.refresh()
        QMessageBox.information(
            self,
            "Import finished",
            f"{added} new and {updated} updated passwords were imported.\n\n"
            "The CSV file you imported contains your passwords as plain text, "
            "so delete it now.",
        )

    def export_csv(self):
        answer = QMessageBox.warning(
            self,
            "Export passwords",
            "The exported file will contain all your passwords as plain text, "
            "readable by anyone who can open it.\n\nExport anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export passwords", "passwords.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["name", "url", "username", "password"])
                for entry in self.vault.entries:
                    host = urlsplit(entry["origin"]).hostname or entry["origin"]
                    writer.writerow([host, entry["origin"], entry["username"], entry["password"]])
        except OSError as error:
            QMessageBox.warning(self, "Export failed", str(error))
            return
        self.status.setText("Exported. Delete the file as soon as you have used it.")

    def change_password(self):
        new_password = ask_new_password(self, "Change browser password")
        if new_password:
            self.vault.change_password(new_password)
            QMessageBox.information(self, "Browser password", "Your browser password was changed.")

    def closeEvent(self, event):
        self.table.setRowCount(0)  # don't leave passwords sitting in the window
        super().closeEvent(event)


class AppearanceDialog(QDialog):
    """Interface font and home screen background."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setWindowTitle("Appearance")
        self.setMinimumWidth(400)
        settings = browser.settings

        # --- font ---
        family = settings.get("ui_font_family", "")
        size = settings.get("ui_font_size", 0)
        self.default_font_box = QCheckBox("Use the default font")
        self.default_font_box.setChecked(not family)
        self.font_box = QFontComboBox()
        if family:
            self.font_box.setCurrentFont(QFont(family))
        self.size_box = QSpinBox()
        self.size_box.setRange(8, 24)
        self.size_box.setValue(size or QApplication.font().pointSize() or 10)
        self.default_font_box.toggled.connect(self.apply_font)
        self.font_box.currentFontChanged.connect(self.apply_font)
        self.size_box.valueChanged.connect(self.apply_font)

        font_form = QFormLayout()
        font_form.addRow("Font:", self.font_box)
        font_form.addRow("Size:", self.size_box)

        # --- background ---
        self.preset_box = QComboBox()
        self.preset_box.addItems(list(PRESET_BACKGROUNDS.keys()))
        if settings.get("home_bg_mode", "preset") == "preset":
            self.preset_box.setCurrentText(settings.get("home_bg_value", "Midnight"))
        self.preset_box.textActivated.connect(lambda name: self.set_background("preset", name))
        color_button = QPushButton("Pick a color\u2026")
        color_button.clicked.connect(self.choose_color)
        image_button = QPushButton("Choose an image\u2026")
        image_button.clicked.connect(self.choose_image)
        reset_button = QPushButton("Reset background")
        reset_button.clicked.connect(lambda: self.reset_background())

        note = QLabel(
            "The font applies to the browser's windows and to the home screen. "
            "The background is shown on the home screen (incognito windows are always black)."
        )
        note.setWordWrap(True)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        layout = QVBoxLayout(self)
        animations_box = QCheckBox("Use animations")
        animations_box.setChecked(self.browser.settings.get("animations", True))
        animations_box.toggled.connect(lambda on: self.browser.set_setting("animations", on))
        layout.addWidget(animations_box)
        layout.addWidget(QLabel("<b>Font</b>"))
        layout.addWidget(self.default_font_box)
        layout.addLayout(font_form)
        layout.addWidget(QLabel("<b>Home screen background</b>"))
        layout.addWidget(self.preset_box)
        layout.addWidget(color_button)
        layout.addWidget(image_button)
        layout.addWidget(reset_button)
        layout.addWidget(note)
        layout.addWidget(close_button)

    def apply_font(self, *_):
        if self.default_font_box.isChecked():
            self.browser.set_setting("ui_font_family", "")
            self.browser.set_setting("ui_font_size", 0)
        else:
            self.browser.set_setting("ui_font_family", self.font_box.currentFont().family())
            self.browser.set_setting("ui_font_size", self.size_box.value())

    def set_background(self, mode, value):
        self.browser.set_setting("home_bg_mode", mode)
        self.browser.set_setting("home_bg_value", value)

    def choose_color(self):
        current = QColor("#1f2a44")
        color = QColorDialog.getColor(current, self, "Pick a background color")
        if color.isValid():
            self.set_background("color", color.name())

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a background image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        destination = os.path.join(self.browser.data.dir, "background.jpg")
        if not save_background_image(path, destination):
            QMessageBox.warning(self, "Image problem", "That image couldn't be used. Try a different one.")
            return
        self.set_background("image", destination)

    def reset_background(self):
        self.preset_box.setCurrentText("Midnight")
        self.set_background("preset", "Midnight")


class SettingsDialog(QDialog):
    """The settings window: blocker switches and the search engine picker."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        settings = browser.settings

        self.ads_box = QCheckBox("Block ads")
        self.ads_box.setChecked(settings.get("block_ads", True))
        self.ads_box.toggled.connect(lambda on: browser.set_setting("block_ads", on))

        self.trackers_box = QCheckBox("Block trackers")
        self.trackers_box.setChecked(settings.get("block_trackers", True))
        self.trackers_box.toggled.connect(
            lambda on: browser.set_setting("block_trackers", on)
        )

        self.engine_box = QComboBox()
        self.engine_box.addItems(list(ENGINES.keys()))
        self.engine_box.setCurrentText(browser.engine_name())
        self.engine_box.currentTextChanged.connect(
            lambda name: browser.set_setting("search_engine", name)
        )

        self.key_edit = QLineEdit(settings.get("gemini_api_key", ""))
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("Paste your key from Google AI Studio")
        self.key_edit.editingFinished.connect(
            lambda: browser.set_setting("gemini_api_key", self.key_edit.text().strip())
        )

        self.model_edit = QLineEdit(settings.get("gemini_model", GEMINI_MODEL))
        self.model_edit.editingFinished.connect(
            lambda: browser.set_setting(
                "gemini_model", self.model_edit.text().strip() or GEMINI_MODEL
            )
        )

        self.download_edit = QLineEdit(browser.download_dir())
        self.download_edit.setReadOnly(True)
        browse = QPushButton("Browse\u2026")
        browse.clicked.connect(self.choose_download_dir)
        download_row = QHBoxLayout()
        download_row.addWidget(self.download_edit)
        download_row.addWidget(browse)

        self.stats = QLabel()
        hint = QLabel("Reload a page after changing the blockers to see the effect.")
        hint.setWordWrap(True)

        close = QPushButton("Close")
        close.clicked.connect(self.close)

        form = QFormLayout()
        form.addRow("Search engine:", self.engine_box)
        form.addRow("Gemini API key:", self.key_edit)
        form.addRow("Gemini model:", self.model_edit)
        form.addRow("Download folder:", download_row)

        layout = QVBoxLayout(self)
        layout.addWidget(self.ads_box)
        layout.addWidget(self.trackers_box)
        layout.addLayout(form)
        appearance_button = QPushButton("Appearance…")
        appearance_button.clicked.connect(browser.open_appearance)
        sidebar_button = QPushButton("Customize sidebar…")
        sidebar_button.clicked.connect(browser.open_sidebar_settings)
        permissions_button = QPushButton("Site permissions…")
        permissions_button.clicked.connect(browser.open_permissions)

        layout.addWidget(self.stats)
        layout.addWidget(hint)
        layout.addWidget(appearance_button)
        layout.addWidget(sidebar_button)
        layout.addWidget(permissions_button)
        layout.addWidget(close)

    def choose_download_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Choose download folder", self.browser.download_dir()
        )
        if path:
            self.download_edit.setText(path)
            self.browser.set_setting("download_dir", path)

    def showEvent(self, event):
        self.stats.setText(f"Blocked so far this session: {self.browser.blocker.count}")
        super().showEvent(event)


class Browser(QMainWindow):
    def __init__(self, data, incognito=False):
        super().__init__()
        self.incognito = incognito
        self.data = data  # the profile this window belongs to
        self.profile_name = data.name
        self.history = None if incognito else data.history
        self.bookmarks = data.bookmarks
        self.vault = None if incognito else data.vault
        self.blocker = data.blocker
        self.settings = data.settings
        if incognito:
            # A private profile: nothing is written to disk, and its cookies
            # and cache disappear when the window is closed.
            profile = QWebEngineProfile()
            setup_profile(profile, self.blocker)
        else:
            profile = data.web_profile
        self.profile = profile
        self.incognito_children = []
        self.password_prompts_seen = set()
        self._font_css = None
        self._bg_cache = None
        self.chat_window = None
        self.sidebar_dialog = None
        self.permissions_dialog = None
        self.bookmarks_window = None
        self.passwords_window = None
        self.appearance_dialog = None
        self.ext_manager = None
        self.ext_worker = None
        self.home_workers = {}
        self.home_job = 0
        if incognito:
            self.setWindowTitle(f"{APP_NAME} Incognito")
            self.setStyleSheet(INCOGNITO_STYLE)
        else:
            suffix = "" if self.profile_name == DEFAULT_PROFILE else f" – {self.profile_name}"
            self.setWindowTitle(f"{APP_NAME} {APP_VERSION}{suffix}")
        self.resize(1200, 800)

        self.tabs = BrowserTabs()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(False)  # every tab gets its own, bigger close button instead
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        new_tab_button = QToolButton()
        new_tab_button.setText("+")
        new_tab_button.setToolTip("New tab (Ctrl+T)")
        new_tab_button.setFixedSize(40, 40)
        new_tab_button.setCursor(Qt.CursorShape.PointingHandCursor)
        new_tab_button.setStyleSheet(NEW_TAB_BUTTON_STYLE)
        new_tab_button.clicked.connect(lambda: self.add_tab())
        self.tabs.setCornerWidget(new_tab_button, Qt.Corner.TopRightCorner)

        # Sidebar (left), site panel (opens next to it), and the tabs
        self.sidebar = SideBar()
        self.sidebar.service_clicked.connect(self.toggle_service)
        self.sidebar.customize_clicked.connect(self.open_sidebar_settings)
        self.panel = SidePanel(self)
        self.panel.hide()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.panel)
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setChildrenCollapsible(False)
        body = QWidget()
        row = QHBoxLayout(body)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.sidebar)
        row.addWidget(self.splitter)

        # A thin bar that fills while a page loads
        self.load_bar = QProgressBar()
        self.load_bar.setRange(0, 100)
        self.load_bar.setTextVisible(False)
        self.load_bar.setFixedHeight(3)
        self.load_bar.setStyleSheet(LOAD_BAR_STYLE)
        self.load_bar.hide()
        self.bar_animation = None
        self.panel_animation = None
        self.panel_closing = False
        outer = QWidget()
        column = QVBoxLayout(outer)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self.load_bar)
        column.addWidget(body)
        self.setCentralWidget(outer)

        # Toolbar: back, forward, reload, home, address bar, new tab, settings
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet(TOOLBAR_STYLE)
        self.addToolBar(toolbar)

        back = QAction("←", self)
        back.triggered.connect(lambda: self.current_view().back())
        toolbar.addAction(back)

        forward = QAction("→", self)
        forward.triggered.connect(lambda: self.current_view().forward())
        toolbar.addAction(forward)

        reload_action = QAction("⟳", self)
        reload_action.triggered.connect(lambda: self.current_view().reload())
        toolbar.addAction(reload_action)

        home = QAction("⌂", self)
        home.triggered.connect(lambda: self.show_home(self.current_view()))
        toolbar.addAction(home)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or enter address")
        self.url_bar.returnPressed.connect(self.navigate)
        toolbar.addWidget(self.url_bar)

        self.star_action = QAction("☆", self)
        self.star_action.setToolTip("Bookmark this page (Ctrl+D)")
        self.star_action.triggered.connect(lambda: self.toggle_bookmark())
        toolbar.addAction(self.star_action)

        new_tab = QAction("+", self)
        new_tab.triggered.connect(lambda: self.add_tab())
        toolbar.addAction(new_tab)

        downloads_action = QAction("⬇", self)
        downloads_action.setToolTip("Downloads (Ctrl+J)")
        downloads_action.triggered.connect(self.show_downloads)
        toolbar.addAction(downloads_action)

        settings_action = QAction("⚙", self)
        settings_action.setToolTip("Settings")
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        # Status bar shows how many requests were blocked
        self.blocked_label = QLabel("Blocked: 0")
        self.statusBar().addPermanentWidget(self.blocked_label)
        self.blocker.counter.changed.connect(
            lambda n: self.blocked_label.setText(f"Blocked: {n}")
        )

        # Keyboard shortcuts
        for key, func in [
            ("Ctrl+T", lambda: self.add_tab()),
            ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+L", self.focus_url_bar),
            ("Ctrl+J", self.show_downloads),
            ("Ctrl+H", self.show_history),
            ("Ctrl+Shift+N", self.open_incognito_window),
            ("Ctrl+D", self.toggle_bookmark),
            ("Ctrl+Shift+O", self.show_bookmarks),
            ("Ctrl+Shift+L", self.fill_saved_password),
        ]:
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(func)
            self.addAction(action)

        self.settings_dialog = SettingsDialog(self)
        self.downloads_window = DownloadsWindow()
        self.profile.downloadRequested.connect(self.on_download_requested)
        self.history_window = HistoryWindow(self) if self.history is not None else None
        self.bookmarks.changed.connect(self.update_star)
        self.setup_menus()
        self.apply_settings()
        if not incognito:
            self.setup_extensions()
        self.add_tab()

    # ---------- Settings ----------

    def engine_name(self):
        name = self.settings.get("search_engine", DEFAULT_ENGINE)
        return name if name in ENGINES else DEFAULT_ENGINE

    def set_setting(self, key, value):
        self.settings.set(key, value)
        self.apply_settings()

    def apply_settings(self):
        set_animations(self.settings.get("animations", True))
        self.apply_appearance()
        self.blocker.block_ads = self.settings.get("block_ads", True)
        self.blocker.block_trackers = self.settings.get("block_trackers", True)
        # Home pages that are open should show the newly chosen search engine.
        self.refresh_home_tabs()
        self.rebuild_sidebar()

    def apply_appearance(self):
        font = QFont(QApplication.font())
        family = self.settings.get("ui_font_family", "")
        size = self.settings.get("ui_font_size", 0)
        if family:
            font.setFamily(family)
        if size > 0:
            font.setPointSize(size)
        self.setFont(font)

    def body_font_css(self):
        family = self.settings.get("ui_font_family", "").replace('"', "").replace("\\", "")
        base = '"Segoe UI", system-ui, sans-serif'
        return f'"{family}", {base}' if family else base

    def home_background_css(self):
        mode = self.settings.get("home_bg_mode", "preset")
        value = self.settings.get("home_bg_value", "Midnight")
        if mode == "color" and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            return value
        if mode == "image":
            uri = self.background_image_data(value)
            if uri:
                return (
                    "linear-gradient(rgba(0, 0, 0, 0.35), rgba(0, 0, 0, 0.35)), "
                    f'url("{uri}") center / cover no-repeat'
                )
        if mode == "preset" and value in PRESET_BACKGROUNDS:
            return PRESET_BACKGROUNDS[value]
        return NORMAL_BACKGROUND

    def background_image_data(self, path):
        if not os.path.isfile(path):
            return ""
        key = (path, os.path.getmtime(path))
        if self._bg_cache is None or self._bg_cache[0] != key:
            with open(path, "rb") as f:
                uri = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")
            self._bg_cache = (key, uri)
        return self._bg_cache[1]

    def open_appearance(self):
        if self.appearance_dialog is None:
            self.appearance_dialog = AppearanceDialog(self)
        self.appearance_dialog.show()
        self.appearance_dialog.raise_()
        self.appearance_dialog.activateWindow()

    def open_settings(self):
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    # ---------- Home page ----------

    def display_name(self):
        return f"{APP_NAME} Incognito" if self.incognito else APP_NAME

    def home_html(self):
        path = os.path.join(BASE_DIR, "home.html")
        template = DEFAULT_HOME_HTML
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                template = f.read()
        name = self.engine_name()
        action, param = ENGINES[name]
        return (
            template.replace("{{ENGINE}}", name)
            .replace("{{ACTION}}", action)
            .replace("{{PARAM}}", param)
            .replace("{{SHORTCUTS}}", self.shortcuts_html())
            .replace("{{APP_NAME}}", escape(self.display_name()))
            .replace("{{BACKGROUND}}", INCOGNITO_BACKGROUND if self.incognito else self.home_background_css())
            .replace("{{BODY_FONT}}", self.body_font_css())
            .replace("{{BODY_CLASS}}", "" if self.settings.get("animations", True) else "noanim")
            .replace("{{MARK_BACKGROUND}}", INCOGNITO_MARK if self.incognito else NORMAL_MARK)
            .replace("{{NOTE}}", escape(INCOGNITO_NOTE) if self.incognito else "")
            .replace("{{ASSISTANT_NAME}}", escape(ASSISTANT_NAME))
            .replace("{{FONT_FACE}}", self.font_face_css())
            .replace("{{WIDGET_LAYER}}", self.widget_layer_html())  # keep this one last
        )

    def load_widget_state(self):
        raw = self.settings.get("home_widgets", "")
        try:
            return sanitize_widget_state(json.loads(raw) if raw else {})
        except ValueError:
            return sanitize_widget_state({})

    def widget_layer_html(self):
        """The movable widgets for the home screen (not shown in incognito windows)."""
        if self.incognito:
            return ""
        bookmarks = sorted(self.bookmarks.entries, key=lambda e: e["time"], reverse=True)[:12]
        recent, seen = [], set()
        if self.history is not None:
            for entry in reversed(self.history.entries):
                if entry["url"] not in seen and entry["url"].startswith(("http://", "https://")):
                    seen.add(entry["url"])
                    recent.append({"title": entry["title"][:80], "url": entry["url"]})
                if len(recent) >= 10:
                    break
        payload = {
            "token": HOME_TOKEN,
            "state": self.load_widget_state(),
            "profiles": {
                "current": self.profile_name,
                "all": [p["name"] for p in load_profiles()["profiles"]],
            },
            "bookmarks": [{"title": b["title"][:80], "url": b["url"]} for b in bookmarks],
            "history": recent,
            "newsSources": [{"id": key, "name": value[0]} for key, value in NEWS_SOURCES.items()],
        }
        data = json.dumps(payload).replace("<", "\\u003c")  # so a note can never close the script
        return (
            f"<style>{WIDGET_CSS}</style>\n"
            f"<script>window.FILIPS_HOME = {data};</script>\n"
            f"<script>{WIDGET_JS}</script>\n"
        )

    def on_home_message(self, view, payload):
        """The home page saved its widget layout, or asked for weather or news."""
        if self.incognito or not getattr(view, "showing_home", False):
            return
        try:
            message = json.loads(payload)
        except ValueError:
            return
        if not isinstance(message, dict) or message.get("t") != HOME_TOKEN:
            return  # not from our own home page
        action, data = message.get("a"), message.get("d")
        if action == "state":
            self.settings.set("home_widgets", json.dumps(sanitize_widget_state(data)))
        elif action == "fetch" and isinstance(data, dict):
            self.start_home_fetch(view, data)

    def start_home_fetch(self, view, data):
        kind = data.get("kind")
        if kind == "weather":
            params = {
                "city": str(data.get("city", ""))[:80],
                "unit": "f" if data.get("unit") == "f" else "c",
            }
        elif kind == "news":
            params = {"source": str(data.get("source", "bbc"))[:30], "custom": str(data.get("custom", ""))[:300]}
        else:
            return
        self.home_job += 1
        worker = HomeDataWorker(self.home_job, id(view), kind, params)
        worker.done.connect(self.on_home_data)
        self.home_workers[self.home_job] = worker
        worker.start()

    def on_home_data(self, result):
        worker = self.home_workers.pop(result["job"], None)
        if worker is not None:
            worker.wait()
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if id(view) == result["view_id"] and getattr(view, "showing_home", False):
                payload = {
                    "ok": result["ok"],
                    "data": result.get("data"),
                    "error": result.get("error", ""),
                }
                script = (
                    "window.filipsData && window.filipsData("
                    f"{json.dumps(result['kind'])}, {json.dumps(payload)});"
                )
                view.page().runJavaScript(script)

    def font_face_css(self):
        """CSS that embeds the Oswald font from the fonts folder (empty if not found)."""
        if self._font_css is None:
            self._font_css = ""
            found = sorted(glob.glob(os.path.join(BASE_DIR, "fonts", "Oswald*.[to]tf")))
            if found:
                is_otf = found[0].lower().endswith(".otf")
                with open(found[0], "rb") as f:
                    data = base64.b64encode(f.read()).decode("ascii")
                self._font_css = (
                    '@font-face { font-family: "Oswald"; '
                    f'src: url(data:font/{"otf" if is_otf else "ttf"};base64,{data}) '
                    f'format("{"opentype" if is_otf else "truetype"}"); '
                    "font-weight: 200 700; }"
                )
        return self._font_css

    def load_shortcuts(self):
        raw = self.settings.get("shortcuts", json.dumps(DEFAULT_SHORTCUTS))
        try:
            return [{"name": str(i["name"]), "url": str(i["url"])} for i in json.loads(raw)]
        except (ValueError, KeyError, TypeError):
            return [dict(item) for item in DEFAULT_SHORTCUTS]

    def save_shortcuts(self, items):
        self.settings.set("shortcuts", json.dumps(items))

    def shortcuts_html(self):
        parts = []
        for i, item in enumerate(self.load_shortcuts()):
            parts.append(
                f'<div class="tile" style="--i:{i}">'
                f'<a class="site" href="{escape(item["url"])}">{escape(item["name"])}</a>'
                f'<a class="x" href="browser://remove?i={i}" title="Remove">×</a>'
                "</div>"
            )
        parts.append(f'<a class="add" style="--i:{len(parts)}" href="browser://add">+ Add site</a>')
        return "\n    ".join(parts)

    def refresh_home_tabs(self):
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if getattr(view, "showing_home", False):
                self.show_home(view)

    # ---------- Sidebar and permissions ----------

    def load_json_list(self, key, default):
        raw = self.settings.get(key, json.dumps(default))
        try:
            value = json.loads(raw)
        except ValueError:
            return list(default)
        return value if isinstance(value, list) else list(default)

    def custom_services(self):
        services = []
        for item in self.load_json_list("sidebar_custom", []):
            try:
                name, url = str(item["name"]), str(item["url"])
            except (KeyError, TypeError):
                continue
            services.append(service_entry("custom:" + url, name, url, "#555555", name[:1].upper() or "?"))
        return services

    def all_services(self):
        return SERVICES + self.custom_services()

    def enabled_service_ids(self):
        return self.load_json_list("sidebar_enabled", DEFAULT_SIDEBAR)

    def rebuild_sidebar(self):
        enabled = set(self.enabled_service_ids())
        services = [s for s in self.all_services() if s["id"] in enabled]
        ids = {s["id"] for s in services}
        for service_id in list(self.panel.views):
            if service_id not in ids:
                self.panel.forget(service_id)
        if self.panel.current_id is None and not self.panel.isHidden():
            self.panel.hide()
        active = None if self.panel.isHidden() else self.panel.current_id
        self.sidebar.set_services(services, active)
        self.sidebar.setVisible(self.settings.get("sidebar_visible", True))

    def toggle_service(self, service):
        if not self.panel.isHidden() and self.panel.current_id == service["id"]:
            self.close_panel()
            return
        was_hidden = self.panel.isHidden()
        if was_hidden:
            self.panel.setMinimumWidth(0)  # it starts closed and slides open
            self.splitter.setSizes([0, max(1, self.splitter.width())])
        self.panel.show_service(service)
        self.sidebar.set_active(service["id"])
        if was_hidden or self.panel_closing:
            self.animate_panel(opening=True, start=0 if was_hidden else None)

    def close_panel(self):
        self.sidebar.set_active(None)
        if not self.panel.isHidden():
            self.animate_panel(opening=False)

    def animate_panel(self, opening, start=None):
        """Slide the site panel open or closed."""
        if self.panel_animation is not None:
            self.panel_animation.stop()
        total = max(1, self.splitter.width())
        target = min(440, max(300, total // 2))
        begin = self.panel.width() if start is None else start
        end = target if opening else 0
        self.panel_closing = not opening

        def set_width(value):
            width = int(value)
            self.splitter.setSizes([width, max(1, total - width)])

        def finished():
            self.panel_closing = False
            if not opening:
                self.panel.hide()
            self.panel.setMinimumWidth(320)

        self.panel.setMinimumWidth(0)
        if not ANIMATIONS_ENABLED:
            set_width(end)
            finished()
            return
        animation = QVariantAnimation(self)
        animation.setDuration(230)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(begin)
        animation.setEndValue(end)
        animation.valueChanged.connect(set_width)
        animation.finished.connect(finished)
        self.panel_animation = animation
        animation.start()

    def open_sidebar_settings(self):
        if self.sidebar_dialog is None:
            self.sidebar_dialog = SidebarDialog(self)
        self.sidebar_dialog.populate()
        self.sidebar_dialog.show()
        self.sidebar_dialog.raise_()
        self.sidebar_dialog.activateWindow()

    def open_permissions(self):
        if self.permissions_dialog is None:
            self.permissions_dialog = PermissionsDialog(self)
        self.permissions_dialog.show()
        self.permissions_dialog.raise_()
        self.permissions_dialog.activateWindow()

    def handle_permission(self, permission):
        """A website asked for camera, microphone, notifications, location..."""
        phrase = PERMISSION_PHRASES.get(permission.permissionType())
        if phrase is None:
            permission.deny()  # for example screen sharing, which isn't supported yet
            return
        origin = permission.origin()
        site = origin.host() or origin.toString()
        box = QMessageBox(self)
        box.setWindowTitle("Permission request")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"{site} wants to {phrase}.")
        box.setInformativeText("Do you want to allow this?")
        allow = box.addButton("Allow", QMessageBox.ButtonRole.AcceptRole)
        block = box.addButton("Block", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(block)
        box.exec()
        if box.clickedButton() is allow:
            permission.grant()
        else:
            permission.deny()

    # ---------- Bookmarks ----------

    def current_page_url(self):
        view = self.current_view()
        if view is None:
            return ""
        url = view.url()
        return url.toString() if url.scheme() in ("http", "https") else ""

    def toggle_bookmark(self):
        url = self.current_page_url()
        if not url:
            self.statusBar().showMessage("Only web pages can be bookmarked.", 3000)
            return
        if self.bookmarks.contains(url):
            self.bookmarks.remove_url(url)
            self.statusBar().showMessage("Bookmark removed.", 3000)
        else:
            self.bookmarks.add(self.current_view().title() or url, url)
            self.statusBar().showMessage("Bookmark added.", 3000)

    def update_star(self):
        url = self.current_page_url()
        saved = bool(url) and self.bookmarks.contains(url)
        self.star_action.setText("\u2605" if saved else "\u2606")
        self.star_action.setToolTip(
            "Remove bookmark (Ctrl+D)" if saved else "Bookmark this page (Ctrl+D)"
        )

    def show_bookmarks(self):
        if self.bookmarks_window is None:
            self.bookmarks_window = BookmarksWindow(self)
        self.bookmarks_window.show()
        self.bookmarks_window.raise_()
        self.bookmarks_window.activateWindow()

    def rebuild_bookmarks_menu(self, menu):
        menu.clear()
        menu.addAction("Bookmark this page", self.toggle_bookmark)
        menu.addAction("Show all bookmarks\u2026", self.show_bookmarks)
        menu.addAction("Import bookmarks\u2026", self.import_bookmarks)
        menu.addAction("Export bookmarks\u2026", self.export_bookmarks)
        menu.addSeparator()
        recent = sorted(self.bookmarks.entries, key=lambda e: e["time"], reverse=True)[:25]
        if not recent:
            menu.addAction("No bookmarks yet").setEnabled(False)
        for entry in recent:
            label = (entry["title"] or entry["url"])[:60].replace("&", "&&")
            menu.addAction(
                label, lambda _c=False, u=entry["url"]: self.current_view().load(QUrl(u))
            )

    def import_bookmarks(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import bookmarks",
            "",
            "Bookmark files (*.html *.htm *.json *.bookmarks);;All files (*)",
        )
        if not path:
            return
        try:
            entries = parse_bookmarks_file(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Import failed", f"This file couldn't be read: {error}")
            return
        if not entries:
            QMessageBox.information(self, "Import", "No bookmarks were found in that file.")
            return
        added = self.bookmarks.add_many(entries)
        QMessageBox.information(
            self,
            "Import finished",
            f"{added} new bookmarks were imported ({len(entries) - added} were already saved).",
        )

    def export_bookmarks(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export bookmarks", "bookmarks.html", "HTML files (*.html)"
        )
        if not path:
            return
        try:
            write_bookmarks_html(path, self.bookmarks.entries)
        except OSError as error:
            QMessageBox.warning(self, "Export failed", str(error))
            return
        self.statusBar().showMessage("Bookmarks exported.", 4000)

    # ---------- Passwords ----------

    def on_password_message(self, page, payload):
        """A page reported a login that was typed in."""
        if self.vault is None:
            return
        try:
            data = json.loads(payload)
        except ValueError:
            return
        if not isinstance(data, dict) or data.get("t") != PASSWORD_TOKEN:
            return  # not from our own script
        url = page.url()
        if url.scheme() not in ("http", "https"):
            return
        origin = origin_of(url.toString())
        username = str(data.get("u", ""))
        password = str(data.get("p", ""))
        if not origin or not password:
            return
        seen = hash((origin, username, password))
        if seen in self.password_prompts_seen:
            return  # already asked about this exact login
        self.password_prompts_seen.add(seen)
        QTimer.singleShot(0, lambda: self.offer_save_password(origin, username, password))

    def offer_save_password(self, origin, username, password):
        existing = None
        if self.vault.is_unlocked:
            for entry in self.vault.find(origin):
                if entry["username"] == username:
                    if entry["password"] == password:
                        return  # already saved
                    existing = entry
        host = urlsplit(origin).hostname or origin
        who = f" for {username}" if username else ""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        if existing is None:
            box.setWindowTitle("Save password?")
            box.setText(f"Save the password{who} on {host}?")
        else:
            box.setWindowTitle("Update password?")
            box.setText(f"Update the saved password{who} on {host}?")
        box.setInformativeText("It will be encrypted with your browser password.")
        save = box.addButton("Save" if existing is None else "Update", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not save:
            return
        if not self.ensure_vault_unlocked("save this password"):
            return
        result = self.vault.add(origin, username, password)
        self.statusBar().showMessage(
            "Password saved." if result == "added" else "Password updated.", 4000
        )

    def ensure_vault_unlocked(self, purpose):
        """Make sure the browser password has been typed in this session."""
        if self.vault.is_unlocked:
            return True
        if not self.vault.exists():
            return self.create_master_password()
        return self.prompt_unlock(purpose)

    def create_master_password(self):
        QMessageBox.information(
            self,
            "Create a browser password",
            "Your saved passwords are encrypted with a browser password that only you know.\n\n"
            "If you forget it, your saved passwords can't be recovered.",
        )
        password = ask_new_password(self)
        if password is None:
            return False
        self.vault.create(password)
        return True

    def prompt_unlock(self, purpose):
        for _attempt in range(3):
            text, ok = QInputDialog.getText(
                self,
                "Browser password",
                f"Enter your browser password to {purpose}:",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return False
            if self.vault.unlock(text):
                return True
            QMessageBox.warning(self, "Wrong password", "That isn't the right browser password.")
        return False

    def open_passwords(self):
        """Always asks for the browser password, even if it was typed in earlier."""
        if self.vault is None:
            return
        if not self.vault.exists():
            if not self.create_master_password():
                return
        elif not self.prompt_unlock("view your saved passwords"):
            return
        self.passwords_window = PasswordsWindow(self)
        self.passwords_window.show()

    def fill_saved_password(self):
        if self.vault is None:
            return
        url = self.current_page_url()
        if not url:
            self.statusBar().showMessage("Open a website's login page first.", 4000)
            return
        if not self.vault.exists():
            self.statusBar().showMessage("You haven't saved any passwords yet.", 4000)
            return
        if not self.ensure_vault_unlocked("fill in a saved password"):
            return
        matches = self.vault.find(origin_of(url))
        if not matches:
            self.statusBar().showMessage("No saved password for this website.", 4000)
            return
        entry = matches[0]
        if len(matches) > 1:
            labels = [m["username"] or "(no username)" for m in matches]
            choice, ok = QInputDialog.getItem(
                self, "Choose an account", "Fill in which account?", labels, 0, False
            )
            if not ok:
                return
            entry = matches[labels.index(choice)]
        script = f"{FILL_FUNCTION}({json.dumps(entry['username'])}, {json.dumps(entry['password'])});"
        self.current_view().page().runJavaScript(script, script_world_id())

    def reset_vault(self):
        answer = QMessageBox.warning(
            self,
            "Reset password vault",
            "This permanently deletes ALL saved passwords in this profile and removes your browser "
            "password, so you can set a new one.\n\nThis can't be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.vault.lock()
        try:
            os.remove(self.vault.path)
        except OSError:
            pass
        self.password_prompts_seen.clear()
        self.statusBar().showMessage("Password vault deleted.", 4000)

    # ---------- Profiles ----------

    def rebuild_profiles_menu(self):
        menu = self.profiles_menu
        menu.clear()
        for info in load_profiles()["profiles"]:
            name = info["name"]
            label = f"{name} (this window)" if name == self.profile_name else f"Open {name}"
            menu.addAction(label.replace("&", "&&"), lambda _c=False, n=name: self.open_profile_window(n))
        menu.addSeparator()
        menu.addAction("New profile\u2026", self.create_profile)
        menu.addAction("Delete a profile\u2026", self.delete_profile)

    def open_profile_window(self, name):
        window = Browser(get_profile(name))
        OPEN_WINDOWS.append(window)
        window.show()

    def create_profile(self):
        name, ok = QInputDialog.getText(self, "New profile", "Name for the new profile:")
        name = name.strip()
        if not ok or not name:
            return
        if len(name) > 30:
            QMessageBox.warning(self, "New profile", "Please use a name of 30 characters or fewer.")
            return
        if not add_profile(name):
            QMessageBox.warning(self, "New profile", "A profile with that name already exists.")
            return
        self.open_profile_window(name)

    def delete_profile(self):
        names = [p["name"] for p in load_profiles()["profiles"] if p["name"] != DEFAULT_PROFILE]
        if not names:
            QMessageBox.information(self, "Delete a profile", "There are no extra profiles to delete.")
            return
        name, ok = QInputDialog.getItem(
            self, "Delete a profile", "Which profile do you want to delete?", names, 0, False
        )
        if not ok:
            return
        if any(w.profile_name == name and w.isVisible() for w in OPEN_WINDOWS):
            QMessageBox.warning(
                self, "Delete a profile", f"Close all windows of the profile \"{name}\" first."
            )
            return
        answer = QMessageBox.warning(
            self,
            "Delete a profile",
            f"Delete the profile \"{name}\"?\n\nIts logins, history, bookmarks, saved passwords and "
            "settings will be erased. This can't be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        remove_profile(name)
        QMessageBox.information(
            self,
            "Delete a profile",
            "The profile was removed. Its files are erased the next time the browser starts.",
        )

    # ---------- Menus, history, incognito ----------

    def setup_menus(self):
        menu = self.menuBar().addMenu("Browser")
        menu.addAction("New tab", lambda: self.add_tab())
        menu.addAction("New incognito window", self.open_incognito_window)
        menu.addSeparator()
        if self.history_window is not None:
            menu.addAction("History", self.show_history)
        menu.addAction("Downloads", self.show_downloads)
        menu.addAction("Customize sidebar…", self.open_sidebar_settings)
        menu.addAction("Appearance…", self.open_appearance)
        self.profiles_menu = menu.addMenu("Profiles")
        self.profiles_menu.aboutToShow.connect(self.rebuild_profiles_menu)
        menu.addAction("Settings", self.open_settings)

        bookmarks_menu = self.menuBar().addMenu("Bookmarks")
        bookmarks_menu.aboutToShow.connect(lambda: self.rebuild_bookmarks_menu(bookmarks_menu))

        if self.incognito:
            return  # no saved passwords in incognito windows
        passwords_menu = self.menuBar().addMenu("Passwords")
        if self.vault is None:
            note = passwords_menu.addAction("Needs the cryptography package (pip install cryptography)")
            note.setEnabled(False)
        else:
            passwords_menu.addAction("Saved passwords…", self.open_passwords)
            passwords_menu.addAction("Fill saved password", self.fill_saved_password)
            passwords_menu.addSeparator()
            passwords_menu.addAction("Reset password vault…", self.reset_vault)

    def open_incognito_window(self):
        window = Browser(self.data, incognito=True)
        self.incognito_children.append(window)
        OPEN_WINDOWS.append(window)
        window.show()

    def show_history(self):
        if self.history_window is None:
            return  # incognito windows don't keep history
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    def on_load_finished(self, ok, view):
        if not ok or self.history is None:
            return
        url = view.url()
        if url.scheme() in ("http", "https"):
            self.history.add(url.toString(), view.title())

    def closeEvent(self, event):
        if self.incognito:
            for i in range(self.tabs.count()):
                self.tabs.widget(i).deleteLater()
            # Give the pages a moment to go away before the private profile is deleted.
            QTimer.singleShot(1000, self.finish_incognito_cleanup)
        else:
            for window in list(self.incognito_children):
                window.close()
            QTimer.singleShot(0, self.forget_window)
        super().closeEvent(event)

    def forget_window(self):
        if self in OPEN_WINDOWS:
            OPEN_WINDOWS.remove(self)

    def finish_incognito_cleanup(self):
        self.profile.deleteLater()
        if self in OPEN_WINDOWS:
            OPEN_WINDOWS.remove(self)

    # ---------- Downloads ----------

    def download_dir(self):
        return self.settings.get("download_dir", default_download_dir()) or default_download_dir()

    def show_downloads(self):
        self.downloads_window.show()
        self.downloads_window.raise_()
        self.downloads_window.activateWindow()

    def on_download_requested(self, download):
        directory = self.download_dir()
        os.makedirs(directory, exist_ok=True)
        name = unique_filename(directory, download.downloadFileName())
        download.setDownloadDirectory(directory)
        download.setDownloadFileName(name)
        download.accept()
        self.downloads_window.add_download(download)
        self.statusBar().showMessage(f"Downloading {name} (Ctrl+J shows downloads)", 5000)

    def open_assistant(self):
        if self.chat_window is None:
            self.chat_window = ChatWindow(self)
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()

    def handle_home_action(self, url, _view):
        """Called when the user clicks "+ Add site" or an x on the home screen."""
        action = url.host()
        if action == "assistant":
            self.open_assistant()
            return
        if action == "openprofile":
            name = QUrlQuery(url).queryItemValue("name")
            if any(p["name"] == name for p in load_profiles()["profiles"]):
                self.open_profile_window(name)
            return
        if action == "newprofile":
            self.create_profile()
            return
        items = self.load_shortcuts()
        if action == "add":
            dialog = AddShortcutDialog(self)
            if not dialog.exec():
                return
            shortcut = dialog.shortcut()
            if shortcut is None:
                QMessageBox.warning(self, "Invalid address", "Please enter a valid web address.")
                return
            items.append(shortcut)
        elif action == "remove":
            index = QUrlQuery(url).queryItemValue("i")
            if index.isdigit() and int(index) < len(items):
                items.pop(int(index))
        else:
            return
        self.save_shortcuts(items)
        self.refresh_home_tabs()

    def show_home(self, view):
        view.showing_home = True
        view.setHtml(self.home_html(), QUrl("about:home"))

    # ---------- Extensions (needs PySide6 6.10+, Manifest V3 only) ----------

    def setup_extensions(self):
        self.ext_menu = self.menuBar().addMenu("Extensions")
        self.ext_manager = None
        if not hasattr(self.profile, "extensionManager"):
            note = self.ext_menu.addAction("Needs PySide6 6.10 or newer")
            note.setEnabled(False)
            self.ext_menu.addAction("Why don't extensions work?", self.show_extension_status)
            return
        self.ext_manager = self.profile.extensionManager()
        # Extensions start out disabled, so switch them on once they are ready.
        self.ext_manager.loadFinished.connect(self.on_extension_ready)
        self.ext_manager.installFinished.connect(self.on_extension_ready)
        self.ext_menu.aboutToShow.connect(self.rebuild_extension_menu)

    def on_extension_ready(self, info):
        if info.isLoaded() or info.isInstalled():
            self.ext_manager.setExtensionEnabled(info, True)
        else:
            QMessageBox.warning(self, "Extension error", info.error() or "Unknown error")

    def rebuild_extension_menu(self):
        self.ext_menu.clear()
        store_id = store_extension_id(self.current_page_url())
        if store_id:
            self.ext_menu.addAction(
                "Add this page's extension to the browser",
                lambda _c=False, i=store_id: self.start_extension_download(i),
            )
            self.ext_menu.addSeparator()
        self.ext_menu.addAction("Add from Chrome Web Store…", self.add_from_web_store)
        self.ext_menu.addAction("Install from a .crx or .zip file…", self.install_from_zip)
        self.ext_menu.addAction("Install from a folder…", self.install_from_folder)
        self.ext_menu.addAction("Extension status…", self.show_extension_status)
        self.ext_menu.addSeparator()

        extensions = self.ext_manager.extensions()
        if not extensions:
            self.ext_menu.addAction("No extensions installed").setEnabled(False)
        for info in extensions:
            sub = self.ext_menu.addMenu(info.name() or info.path())
            enabled = sub.addAction("Enabled")
            enabled.setCheckable(True)
            enabled.setChecked(info.isEnabled())
            enabled.toggled.connect(
                lambda on, i=info: self.ext_manager.setExtensionEnabled(i, on)
            )
            sub.addAction("Open popup", lambda _c=False, i=info: self.open_popup(i))
            sub.addAction(
                "Remove", lambda _c=False, i=info: self.ext_manager.uninstallExtension(i)
            )

    def install_from_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose an unpacked extension folder")
        if path:
            self.ext_manager.installExtension(path)

    def install_from_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose an extension file", "", "Extension files (*.crx *.zip);;All files (*)"
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as error:
            QMessageBox.warning(self, "Extension", f"The file couldn't be read: {error}")
            return
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", os.path.splitext(os.path.basename(path))[0])
        self.install_extension_bytes(data, name or "extension")

    def add_from_web_store(self):
        if self.ext_manager is None:
            self.show_extension_status()
            return
        suggestion = self.current_page_url() if store_extension_id(self.current_page_url()) else ""
        text, ok = QInputDialog.getText(
            self,
            "Add from Chrome Web Store",
            "Paste the extension's Chrome Web Store link (or its 32-letter ID):",
            QLineEdit.EchoMode.Normal,
            suggestion,
        )
        if not ok:
            return
        extension_id = extension_id_from_text(text)
        if not extension_id:
            QMessageBox.warning(
                self,
                "Chrome Web Store",
                "That doesn't look like a Chrome Web Store link or extension ID.",
            )
            return
        self.start_extension_download(extension_id)

    def start_extension_download(self, extension_id):
        if self.ext_manager is None:
            self.show_extension_status()
            return
        if self.ext_worker is not None:
            self.statusBar().showMessage("An extension is already being downloaded.", 4000)
            return
        match = re.search(r"Chrome/([\d.]+)", self.profile.httpUserAgent())
        version = match.group(1) if match else "130.0.0.0"
        self.statusBar().showMessage("Downloading the extension\u2026")
        worker = ExtensionDownloader(extension_id, version)
        worker.succeeded.connect(self.on_extension_downloaded)
        worker.failed.connect(self.on_extension_download_failed)
        self.ext_worker = worker
        worker.start()

    def finish_ext_worker(self):
        if self.ext_worker is not None:
            self.ext_worker.wait()
            self.ext_worker = None

    def on_extension_download_failed(self, message):
        self.finish_ext_worker()
        self.statusBar().clearMessage()
        QMessageBox.warning(self, "Chrome Web Store", message)

    def on_extension_downloaded(self, data):
        extension_id = self.ext_worker.extension_id if self.ext_worker is not None else "extension"
        self.finish_ext_worker()
        self.install_extension_bytes(data, extension_id)

    def install_extension_bytes(self, data, name):
        """Unpack an extension file and hand it to Qt to install."""
        if self.ext_manager is None:
            self.show_extension_status()
            return
        folder = os.path.join(self.data.dir, "extension_files", name)
        try:
            manifest = unpack_extension(data, folder)
        except (ValueError, OSError, KeyError) as error:
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "Extension", f"This extension couldn't be unpacked: {error}")
            return
        if manifest.get("manifest_version") != 3:
            shutil.rmtree(folder, ignore_errors=True)
            self.statusBar().clearMessage()
            QMessageBox.warning(
                self,
                "Extension not supported",
                "This extension uses the older \"Manifest V2\" format, which this browser "
                "can't run. Only Manifest V3 extensions work.\n\n"
                "Many popular extensions have a separate V3 version (for example "
                "\"uBlock Origin Lite\" instead of \"uBlock Origin\").",
            )
            return
        self.statusBar().showMessage("Installing the extension\u2026", 5000)
        self.ext_manager.installExtension(folder)

    def show_extension_status(self):
        import PySide6

        lines = [f"PySide6 version: {PySide6.__version__}", f"Qt version: {qVersion()}", ""]
        if self.ext_manager is None:
            lines.append("This version of PySide6 has no extension support (it needs 6.10 or newer).")
            lines.append("Update it with:  py -3.12 -m pip install --upgrade PySide6")
        else:
            extensions = self.ext_manager.extensions()
            lines.append(f"Extensions installed: {len(extensions)}")
            for info in extensions:
                state = "on" if info.isEnabled() else "off"
                problem = info.error()
                lines.append(
                    f"  - {info.name() or info.path()} ({state})"
                    + (f" - problem: {problem}" if problem else "")
                )
            lines.append("")
            lines.append(
                "Only Manifest V3 extensions work. Many extensions in the store are still the "
                "older Manifest V2 format and can't be installed."
            )
        QMessageBox.information(self, "Extension status", "\n".join(lines))

    def open_popup(self, info):
        url = info.actionPopupUrl()
        if url.isEmpty():
            QMessageBox.information(self, "No popup", "This extension has no popup.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(info.name())
        dialog.resize(400, 500)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        view = QWebEngineView()
        view.load(url)
        layout.addWidget(view)
        dialog.show()

    # ---------- Tabs and navigation ----------

    def current_view(self):
        return self.tabs.currentWidget()

    def add_tab(self, url=None, home=True):
        view = BrowserView(self)
        index = self.tabs.addTab(view, "New Tab")
        self.tabs.setCurrentIndex(index)

        close_button = QToolButton()
        close_button.setText("\u2715")
        close_button.setToolTip("Close tab")
        close_button.setFixedSize(26, 26)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setStyleSheet(CLOSE_BUTTON_STYLE)
        close_button.clicked.connect(
            lambda _c=False, v=view: self.close_tab(self.tabs.indexOf(v))
        )
        self.tabs.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, close_button)

        view.titleChanged.connect(
            lambda title, v=view: self.tabs.setTabText(
                self.tabs.indexOf(v), title[:40] or "New Tab"
            )
        )
        view.loadStarted.connect(lambda v=view: self.on_load_started(v))
        view.loadProgress.connect(lambda p, v=view: self.on_load_progress(v, p))
        view.loadFinished.connect(lambda ok, v=view: self.on_load_done(v))
        view.urlChanged.connect(lambda u, v=view: self.on_url_changed(u, v))
        view.loadFinished.connect(lambda ok, v=view: self.on_load_finished(ok, v))

        if url:
            view.load(QUrl(url))
        elif home:
            self.show_home(view)
        return view

    def on_load_started(self, view):
        view.loading = True
        view.progress = 8
        if view is self.current_view():
            self.update_load_bar()

    def on_load_progress(self, view, percent):
        view.progress = percent
        if view is self.current_view():
            self.update_load_bar()

    def on_load_done(self, view):
        view.loading = False
        view.progress = 100
        if view is self.current_view():
            self.update_load_bar()

    def update_load_bar(self):
        view = self.current_view()
        if view is not None and view.loading:
            self.load_bar.show()
            self.animate_load_bar(max(view.progress, 8))
        elif self.load_bar.isVisible():
            self.animate_load_bar(100)
            QTimer.singleShot(260, self.hide_load_bar)

    def hide_load_bar(self):
        view = self.current_view()
        if view is None or not view.loading:
            self.load_bar.hide()
            self.load_bar.setValue(0)

    def animate_load_bar(self, value):
        if not ANIMATIONS_ENABLED:
            self.load_bar.setValue(value)
            return
        if self.bar_animation is not None:
            self.bar_animation.stop()
        animation = QPropertyAnimation(self.load_bar, b"value", self)
        animation.setDuration(180)
        animation.setStartValue(self.load_bar.value())
        animation.setEndValue(value)
        self.bar_animation = animation
        animation.start()

    def close_tab(self, index):
        if index < 0:
            return
        if self.tabs.count() < 2:
            self.close()
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()

    @staticmethod
    def url_text(url):
        # The home page and blank pages show an empty address bar.
        if url.isEmpty() or url.scheme() in ("about", "data"):
            return ""
        return url.toString()

    def on_tab_changed(self, _index):
        view = self.current_view()
        if view:
            self.url_bar.setText(self.url_text(view.url()))
        self.update_star()
        self.update_load_bar()

    def on_url_changed(self, url, view):
        if url.scheme() in ("http", "https", "file"):
            view.showing_home = False
        if view is self.current_view():
            self.url_bar.setText(self.url_text(url))
            self.update_star()
            if self.ext_manager is not None and store_extension_id(url.toString()):
                self.statusBar().showMessage(
                    "This is a Chrome Web Store page. Use the Extensions menu to add it to this browser.",
                    8000,
                )

    def focus_url_bar(self):
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    def navigate(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        if "://" in text:
            url = text
        elif " " not in text and "." in text:
            url = "https://" + text
        else:
            base, param = ENGINES[self.engine_name()]
            url = f"{base}?{param}={quote_plus(text)}"
        self.current_view().load(QUrl(url))


def main():
    global NOTIFICATIONS
    app = QApplication(sys.argv)
    app_icon = make_icon({"id": "app", "color": "#6ea8ff", "letter": "F"})
    app.setWindowIcon(app_icon)
    NOTIFICATIONS = NotificationCenter(app_icon)
    fade_filter = FadeInFilter()
    app.installEventFilter(fade_filter)

    AD_DOMAINS.update(load_custom_blocklist(os.path.join(BASE_DIR, "blocklist.txt")))
    cleanup_pending_profiles()

    window = Browser(get_profile(DEFAULT_PROFILE))
    OPEN_WINDOWS.append(window)
    app.aboutToQuit.connect(save_all_profiles)
    NOTIFICATIONS.window = window
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
