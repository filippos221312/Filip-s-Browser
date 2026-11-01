import base64
import csv
import glob
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
import urllib.error
import urllib.request
from urllib.parse import quote, quote_plus, urlsplit

from PySide6.QtCore import (
    QObject,
    QRectF,
    QSettings,
    QSize,
    QStandardPaths,
    QThread,
    QTimer,
    QUrl,
    QUrlQuery,
    Qt,
    Signal,
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
</style>
</head>
<body>
  <div class="logo"><div class="mark">F</div><div class="word">{{APP_NAME}}</div></div>
  <div class="note">{{NOTE}}</div>
  <form action="{{ACTION}}" method="get">
    <input type="text" name="{{PARAM}}" placeholder="Search with {{ENGINE}}" autofocus autocomplete="off">
  </form>
  <a class="ai" href="browser://assistant">✦ {{ASSISTANT_NAME}}</a>
  <div class="links">
    {{SHORTCUTS}}
  </div>
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
            button = QToolButton()
            button.setIcon(make_icon(service))
            button.setIconSize(QSize(30, 30))
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
        if incognito:
            self.setWindowTitle(f"{APP_NAME} Incognito")
            self.setStyleSheet(INCOGNITO_STYLE)
        else:
            suffix = "" if self.profile_name == DEFAULT_PROFILE else f" – {self.profile_name}"
            self.setWindowTitle(f"{APP_NAME} {APP_VERSION}{suffix}")
        self.resize(1200, 800)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)

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
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.sidebar)
        row.addWidget(self.splitter)
        self.setCentralWidget(container)

        # Toolbar: back, forward, reload, home, address bar, new tab, settings
        toolbar = QToolBar()
        toolbar.setMovable(False)
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
        blocker.counter.changed.connect(
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
            .replace("{{MARK_BACKGROUND}}", INCOGNITO_MARK if self.incognito else NORMAL_MARK)
            .replace("{{NOTE}}", escape(INCOGNITO_NOTE) if self.incognito else "")
            .replace("{{ASSISTANT_NAME}}", escape(ASSISTANT_NAME))
            .replace("{{FONT_FACE}}", self.font_face_css())
        )

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
                '<div class="tile">'
                f'<a class="site" href="{escape(item["url"])}">{escape(item["name"])}</a>'
                f'<a class="x" href="browser://remove?i={i}" title="Remove">×</a>'
                "</div>"
            )
        parts.append('<a class="add" href="browser://add">+ Add site</a>')
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
        self.panel.show_service(service)
        self.sidebar.set_active(service["id"])
        if was_hidden:
            self.splitter.setSizes([440, max(300, self.splitter.width() - 440)])

    def close_panel(self):
        self.panel.hide()
        self.sidebar.set_active(None)

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
        self.ext_menu.addAction("Install from folder…", self.install_from_folder)
        self.ext_menu.addAction("Install from .zip…", self.install_from_zip)
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
            self, "Choose an extension .zip", "", "Zip files (*.zip)"
        )
        if path:
            self.ext_manager.installExtension(path)

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

        view.titleChanged.connect(
            lambda title, v=view: self.tabs.setTabText(
                self.tabs.indexOf(v), title[:20] or "New Tab"
            )
        )
        view.urlChanged.connect(lambda u, v=view: self.on_url_changed(u, v))
        view.loadFinished.connect(lambda ok, v=view: self.on_load_finished(ok, v))

        if url:
            view.load(QUrl(url))
        elif home:
            self.show_home(view)
        return view

    def close_tab(self, index):
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

    def on_url_changed(self, url, view):
        if url.scheme() in ("http", "https", "file"):
            view.showing_home = False
        if view is self.current_view():
            self.url_bar.setText(self.url_text(url))
            self.update_star()

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
