#!/usr/bin/env python3
"""solaris-monitor : tableau de bord Tor en terminal (alternative visuelle à Nyx).

Il se connecte au ControlPort de Tor comme Nyx (via la bibliothèque `stem`, déjà
installée si Nyx l'est) et affiche : graphiques de bande passante, état du Pi,
circuits et journal Tor. AUCUNE adresse IP de client n'est affichée.

    python3 solaris-monitor.py                 # relais réel (ControlPort 9051)
    python3 solaris-monitor.py --demo          # fausses données, pour voir le rendu
    python3 solaris-monitor.py --socket /run/tor/control
    sudo -u debian-tor python3 solaris-monitor.py   # si l'accès est refusé

Touches : q = quitter, t = thème, m = changer de vue (graphes / relais connectés), g = graphes,
         c = relais connectés, f = drapeaux emoji (si ton terminal les gère), i = mascotte,
         p = cache-œil de pirate, b = clignement des yeux on/off.
Vue « relais connectés » : les relais du réseau Tor reliés au tien (adresses publiques du consensus),
avec pays, nom, rôle et ancienneté. Les connexions de clients/bridges ne sont JAMAIS affichées.
(La mascotte demande un terminal de 115x40 ou plus.)
Taille minimale du terminal : 80 x 24.
"""
import argparse, collections, curses, getpass, locale, os, random, shutil, sys, time

# ---------------------------------------------------------------- décor
GLYPHS = {
    's': ["     ", " ___ ", "/ __|", "\\__ \\", "|___/"],
    'o': ["       ", "  ___  ", " / _ \\ ", "| (_) |", " \\___/ "],
    'l': [" _ ", "| |", "| |", "| |", "|_|"],
    'a': ["       ", "  __ _ ", " / _` |", "| (_| |", " \\__,_|"],
    'r': ["      ", " _ __ ", "| '__|", "| |   ", "|_|   "],
    'i': [" _ ", "(_)", "| |", "| |", "|_|"],
}
LOGO = ["".join(GLYPHS[c][r] for c in "solaris").rstrip() for r in range(5)]
# Mascotte (écureuil) : 16 lignes x 32 colonnes de cellules. Chaque cellule = 3 caractères :
#   [masque des 4 quarts en hexa][couleur des quarts allumés][couleur du fond]   (k = noir)
MASCOT = [
    "0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk8ok3dodokcokcok4ok0kk0kk0kk0kk0kk0kk0kk0kk0kk",
    "0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk8okcok0kk8okeokfokfokfokfokfokfokfokfokfokcokcokcokcok0kk0kk",
    "0kk0kk4ok0kk0kk0kk0kk8okcokcokcokcokeok5om8okfokfokfokfokfokfokfokfokfokfokfokfokfokfokfok5mk0kk",
    "0kk0kk3okfokfokfokfokfokfokfok7ok3ow3owdokbokfokfokfokfokfokfokfokfokfokfokfokfokfokfokfok5ok0kk",
    "0kk0kkcwkcwo3ow3okfokfokfokcdk7wk3wkfwk5wo5okfokfokfokfokfokfokfokfokfokfokfokfokfokfokfok5ok0kk",
    "0kk0kkfwkcwkewk5wm5mofokfokeodfwkfwk7wmemwbmofokfokfokfokfokfokfokfokfokfokfokfokfokfokfok5ok0kk",
    "0kk0kk0kkamkfmk7mofokfokfokfokfok3ok3ombomdokfokfokfokfokfokfokfokfokfokfokfokfokfokfokfok5ok0kk",
    "0kk0kk0kk0kk0kk2okfok3owewofwk5wdfdkedkfokfokfokfokfokfokfokfok3omemofmkdmobokfokfokfok7om1ok0kk",
    "0kk0kk0kk0kk0kk0kkaod5odfdkfdkfdkfdkfdkbodfokfokfokfokfok3omfmkfmk3mkemkfmkdmo3om3omfmk7mk0kk0kk",
    "0kk0kk0kk0kk0kk0kkaok9od7okadkfdk7dkaod7okbokfokbom7omfmkfmk7mkdmkfmkfmkfmkfmkfmkfmk3mk0kk0kk0kk",
    "0kk0kk0kk0kk0kk0kk7omfdkfdkfdkfdkfdkddkfdkfokfokbmofmkfmk7mk2mk3mk1mk0kk0kk0kk0kk0kk0kk0kk0kk0kk",
    "0kk0kk0kk0kk0kk0kk5omfdkfdkfdkfdkfdkfdkfdk6okfokfokbmkfmk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk",
    "0kk0kk0kk0kk0kkeok5omfdkfdkfdkfdkfdkfdkfdkddkbokfok5om5mk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk",
    "0kk0kk0kk8okfokfok5ombdkfdkfdkfdkfdkfdkfdkfdkeod7omfmk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk",
    "0kk0kk0kkaokfokfokdomfok3docmd3dobdocmkdmo3om3omfmkfmk5mk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk",
    "0kk0kk0kk2mk3mk3mk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk3mk3mk1mk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk0kk",
]
MASCOT_COLORS = {'k': 16, 'o': 130, 'm': 94, 'd': 52, 'w': 231, 'p': 235}   # repli : couleurs xterm-256 les plus proches
MASCOT_RGB = {"k": (0, 0, 0), "o": (160, 82, 2), "m": (112, 57, 3), "d": (97, 22, 4), "w": (255, 255, 255), "p": (44, 44, 54)}
MASCOT_SLOTS = {"o": 240, "m": 241, "d": 242, "w": 243, "p": 244}   # emplacements de palette redéfinis si possible
# Variantes (cellules modifiées seulement) : yeux fermés, cache-œil de pirate, cache-œil + œil fermé
MASCOT_VARIANTS = {
    "blink": {
    (3, 10): "fok", (3, 11): "fok", (3, 12): "fok", (4, 2): "cok", (4, 3): "eok", (4, 4): "fok",
    (4, 5): "7ok", (4, 9): "6ok", (4, 10): "3ok", (4, 11): "3ok", (4, 12): "3ok", (4, 13): "bok",
    (5, 2): "cok", (5, 3): "cok", (5, 4): "cok", (5, 5): "bmo", (5, 10): "fok", (5, 11): "fok",
    (5, 12): "fok", (5, 13): "5om",
},
    "patch": {
    (2, 10): "cpk", (2, 11): "cpk", (3, 7): "7op", (3, 8): "epo", (3, 9): "3po", (3, 10): "6op",
    (4, 2): "cpk", (4, 3): "epk", (4, 4): "dpo", (4, 5): "3op", (4, 6): "3po", (4, 7): "eop",
    (5, 2): "fpk", (5, 3): "fpk", (5, 4): "fpk", (5, 5): "fpk", (6, 3): "apk", (6, 4): "emp",
    (6, 6): "3po", (6, 7): "bop",
},
    "patch_blink": {
    (2, 10): "cpk", (2, 11): "cpk", (3, 7): "7op", (3, 8): "epo", (3, 9): "3po", (3, 10): "eop",
    (3, 11): "fok", (3, 12): "fok", (4, 2): "cpk", (4, 3): "epk", (4, 4): "dpo", (4, 5): "3op",
    (4, 6): "3po", (4, 7): "eop", (4, 9): "6ok", (4, 10): "3ok", (4, 11): "3ok", (4, 12): "3ok",
    (4, 13): "bok", (5, 2): "fpk", (5, 3): "fpk", (5, 4): "fpk", (5, 5): "fpk", (5, 10): "fok",
    (5, 11): "fok", (5, 12): "fok", (5, 13): "5om", (6, 3): "apk", (6, 4): "emp", (6, 6): "3po",
    (6, 7): "bop",
},
}
QUADS = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"   # caractère selon le masque (haut-gauche, haut-droit, bas-gauche, bas-droit)
SINCE = "━━━━━━━  ◆  S I N C E   2 0 0 8  ◆  ━━━━━━━"
# (nom, couleur vive 256, couleur sombre 256, couleur de secours 8 couleurs)
THEMES = [("matrix", 46, 34, 2), ("amber", 214, 172, 3), ("cyan", 51, 37, 6), ("rose", 213, 169, 5)]
BLOCKS = " ▁▂▃▄▅▆▇█"


# ---------------------------------------------------------------- utilitaires
def human(n, suffix=""):
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return (f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}") + suffix
        n /= 1024


def fmt_uptime(sec):
    d, r = divmod(int(sec), 86400); h, r = divmod(r, 3600); m = r // 60
    return (f"{d}j " if d else "") + f"{h:02d}h{m:02d}m"


def chart(vals, h, vmax):
    """Graphique en aires : renvoie h lignes de texte (blocs ▁▂▃▄▅▆▇█)."""
    rows = [[" "] * len(vals) for _ in range(h)]
    for x, v in enumerate(vals):
        lvl = int(min(v, vmax) / vmax * h * 8) if vmax else 0
        for r in range(h):
            rows[h - 1 - r][x] = BLOCKS[max(0, min(8, lvl - r * 8))]
    return ["".join(r) for r in rows]


def flag_emoji(cc):
    cc = (cc or "").upper()
    if len(cc) == 2 and cc.isalpha():
        return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in cc)
    return ""


def short_flags(flags):
    return "".join(l for name, l in (("Guard", "G"), ("Exit", "E"), ("Fast", "F"), ("Stable", "S"), ("HSDir", "H")) if name in flags)


def fmt_age(sec):
    sec = int(sec)
    if sec < 60: return f"{sec}s"
    if sec < 3600: return f"{sec // 60}m{sec % 60:02d}"
    return f"{sec // 3600}h{(sec % 3600) // 60:02d}"


def bar(pct, width):
    pct = max(0, min(100, pct or 0))
    f = int(round(width * pct / 100))
    return "█" * f + "░" * (width - f)


# ---------------------------------------------------------------- état du Pi
class SysStats:
    def __init__(self):
        self.prev = self._cpu()

    @staticmethod
    def _cpu():
        try:
            with open("/proc/stat") as f:
                v = list(map(int, f.readline().split()[1:]))
            return sum(v), v[3] + v[4]
        except Exception:
            return None

    def read(self):
        out = {"cpu": None, "temp": None, "mem": None, "mem_txt": "", "disk": 0, "load": None}
        cur = self._cpu()
        if cur and self.prev and cur[0] > self.prev[0]:
            out["cpu"] = 100 * (1 - (cur[1] - self.prev[1]) / (cur[0] - self.prev[0]))
        self.prev = cur
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                out["temp"] = int(f.read()) / 1000
        except Exception:
            pass
        try:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    mem[k] = int(v.split()[0])
            used = mem["MemTotal"] - mem["MemAvailable"]
            out["mem"] = 100 * used / mem["MemTotal"]
            out["mem_txt"] = f"{used // 1024}/{mem['MemTotal'] // 1024} Mo"
        except Exception:
            pass
        du = shutil.disk_usage("/")
        out["disk"] = du.used / du.total * 100
        try:
            out["load"] = os.getloadavg()
        except OSError:
            pass
        return out


# ---------------------------------------------------------------- sources de données
class TorSource:
    name = "TOR"

    def __init__(self, port, socket_path, password):
        try:
            from stem.control import Controller, EventType
        except ImportError:
            sys.exit("La bibliothèque 'stem' est absente (Nyx l'installe normalement) : pip install stem")
        try:
            self.c = Controller.from_socket_file(socket_path) if socket_path else Controller.from_port(port=port)
        except Exception as e:
            sys.exit(f"Impossible de joindre le ControlPort de Tor ({e}).\n"
                     "Vérifie dans /etc/tor/torrc : ControlPort 9051 et CookieAuthentication 1, puis redémarre Tor.")
        try:
            self.c.authenticate(password=password)
        except Exception as e:
            sys.exit(f"Authentification refusée ({e}).\n"
                     "Essaie :  sudo -u debian-tor python3 solaris-monitor.py")
        self.logs = collections.deque(maxlen=200)
        self.c.add_event_listener(self._on_log, EventType.NOTICE, EventType.WARN, EventType.ERR)
        g = self.c.get_info
        self.info = {
            "nickname": self.c.get_conf("Nickname", "-") or "-",
            "version": str(self.c.get_version()).split(" ")[0],
            "fingerprint": g("fingerprint", "-"),
        }
        self.last = None
        self.circuits, self.circ_t = 0, 0
        self.seen, self.ns_cache = {}, {}
        self.conns, self.hidden, self.conn_t = [], 0, 0

    def _relay_info(self, fp):
        """Infos publiques d'un relais (consensus). Inconnu du consensus => ip '?' (jamais affiché)."""
        if fp not in self.ns_cache:
            try:
                e = self.c.get_network_status(fp, None)
            except Exception:
                e = None
            if e is None:
                self.ns_cache[fp] = {"ip": "?"}
            else:
                try:
                    cc = self.c.get_info("ip-to-country/" + e.address, "??") or "??"
                except Exception:
                    cc = "??"
                self.ns_cache[fp] = {"ip": e.address, "port": e.or_port, "nick": e.nickname,
                                     "flags": list(e.flags or []), "cc": cc}
        return self.ns_cache[fp]

    def _poll_conns(self, now):
        raw = self.c.get_info("orconn-status", "") or ""
        live, hidden = {}, 0
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) < 2 or not parts[0].startswith("$") or parts[1] != "CONNECTED":
                continue
            fp = parts[0][1:41].upper()
            info = self._relay_info(fp)
            if info["ip"] == "?":
                hidden += 1            # client, bridge ou relais inconnu : compté, jamais détaillé
            else:
                live[fp] = info
        for fp in [f for f in self.seen if f not in live]:
            del self.seen[fp]
        for fp in live:
            self.seen.setdefault(fp, now)
        self.conns = [dict(live[fp], fp=fp, first=self.seen[fp]) for fp in live]
        self.hidden = hidden

    def _on_log(self, ev):
        self.logs.append((time.strftime("%H:%M:%S"), ev.runlevel, ev.message))

    def poll(self):
        g = self.c.get_info
        r, w, now = int(g("traffic/read")), int(g("traffic/written")), time.time()
        down = up = 0
        if self.last:
            dt = max(now - self.last[0], 0.001)
            down, up = (r - self.last[1]) / dt, (w - self.last[2]) / dt
        self.last = (now, r, w)
        if now - self.circ_t > 5:
            self.circuits, self.circ_t = len(self.c.get_circuits(default=[])), now
        if now - self.conn_t >= 2:
            self.conn_t = now
            try:
                self._poll_conns(now)
            except Exception:
                pass
        return {"down": max(down, 0), "up": max(up, 0), "read": r, "written": w,
                "uptime": int(g("uptime", 0)), "circuits": self.circuits, "ok": True,
                "conns": self.conns, "hidden": self.hidden}


class DemoSource:
    """Fausses données pour prévisualiser l'interface sans Tor."""
    name = "DEMO"

    def __init__(self):
        self.logs = collections.deque(maxlen=200)
        self.info = {"nickname": "solaris", "version": "0.4.8.x", "fingerprint": "A1B2C3D4E5F60718293A4B5C6D7E8F9012345678"}
        self.down, self.up, self.r, self.w, self.t0 = 300_000, 120_000, 0, 0, time.time() - 93784
        self.peers = [self._fake_peer(time.time() - random.uniform(5, 4000)) for _ in range(12)]
        self.msgs = [("NOTICE", "Heartbeat: Tor's uptime is 1 day 2:03 hours, with 41 circuits open."),
                     ("NOTICE", "Your Tor server's identity key fingerprint is confirmed."),
                     ("WARN", "Your system clock just jumped 1 seconds forward; assuming established circuits no longer work."),
                     ("NOTICE", "Performing bandwidth self-test...done."), ("NOTICE", "Received reload signal (hup).")]

    @staticmethod
    def _fake_peer(first):
        nicks = ["torrelay", "nightowl", "mistral", "borealis", "quasar", "cedar", "lighthouse", "polaris",
                 "northwind", "ember", "saffron", "vortex", "willow", "atlas", "kestrel", "zephyr"]
        flags = random.choice([["Guard", "Fast", "Stable"], ["Fast", "Stable", "HSDir"], ["Exit", "Fast", "Stable"],
                               ["Guard", "Fast", "Stable", "HSDir"], ["Fast"], ["Stable", "HSDir"]])
        return {"ip": f"{random.choice(['203.0.113', '198.51.100', '192.0.2'])}.{random.randint(1, 254)}",
                "port": random.choice([443, 9001, 9030, 8443]), "nick": random.choice(nicks) + str(random.randint(1, 99)),
                "flags": flags, "cc": random.choice(["fr", "de", "nl", "us", "se", "ch", "ca", "gb", "fi", "at", "ro", "cz", "jp"]),
                "fp": "%040X" % random.getrandbits(160), "first": first}

    def poll(self):
        if random.random() < .12 and len(self.peers) > 6: self.peers.pop(random.randrange(len(self.peers)))
        if random.random() < .16 and len(self.peers) < 16: self.peers.append(self._fake_peer(time.time()))
        self.down = min(4e6, max(8e3, self.down * random.uniform(.8, 1.25) + random.uniform(-2e4, 4e4)))
        self.up = min(3e6, max(5e3, self.up * random.uniform(.8, 1.25) + random.uniform(-2e4, 3e4)))
        self.r += self.down; self.w += self.up
        if random.random() < .15:
            lvl, msg = random.choice(self.msgs)
            self.logs.append((time.strftime("%H:%M:%S"), lvl, msg))
        return {"down": self.down, "up": self.up, "read": self.r, "written": self.w,
                "uptime": time.time() - self.t0, "circuits": random.randint(38, 46), "ok": True,
                "conns": list(self.peers), "hidden": 87}


# ---------------------------------------------------------------- interface
class UI:
    def __init__(self):
        self.theme = 0
        self.show_img = True
        self.patch = False     # cache-œil de pirate
        self.blink = True      # clignement des yeux
        self.t0 = time.time()
        self.mode = 0          # 0 = graphes, 1 = relais connectés
        self.emoji = False     # drapeaux emoji (selon le terminal)
        self.down = collections.deque([0] * 300, maxlen=300)
        self.up = collections.deque([0] * 300, maxlen=300)
        self.prev = None                       # relais connectés au passage précédent
        self.events = collections.deque()      # (heure, "+"/"-", relais) des 10 dernières minutes

    def track(self, conns):
        """Compare avec le passage précédent : qui vient d'arriver, qui vient de partir."""
        now = time.time()
        cur = {c["fp"]: c for c in conns}
        if self.prev is not None:
            for fp, c in cur.items():
                if fp not in self.prev: self.events.append((now, "+", c))
            for fp, c in self.prev.items():
                if fp not in cur: self.events.append((now, "-", c))
        self.prev = cur
        while self.events and now - self.events[0][0] > 600:
            self.events.popleft()


def make_attrs(theme):
    _, bright, dim, basic = THEMES[theme]
    rich = curses.COLORS >= 256
    black = curses.COLOR_BLACK
    curses.init_pair(1, bright if rich else basic, black)
    curses.init_pair(2, dim if rich else basic, black)
    curses.init_pair(3, 226 if rich else curses.COLOR_YELLOW, black)
    curses.init_pair(4, 196 if rich else curses.COLOR_RED, black)
    return {"main": curses.color_pair(1) | curses.A_BOLD,
            "dim": curses.color_pair(2) | (0 if rich else curses.A_DIM),
            "warn": curses.color_pair(3) | curses.A_BOLD, "err": curses.color_pair(4) | curses.A_BOLD}


def put(scr, y, x, s, attr):
    H, W = scr.getmaxyx()
    if 0 <= y < H and 0 <= x < W:
        try:
            scr.addstr(y, x, s[: W - x], attr)
        except curses.error:
            pass


_pairs = {}


def img_pair(fg, bg):
    """Associe (couleur avant, couleur arrière) à une paire curses, créée à la demande."""
    key = (fg, bg)
    if key not in _pairs:
        n = 10 + len(_pairs)
        if n >= curses.COLOR_PAIRS:
            return curses.color_pair(1)
        curses.init_pair(n, fg, bg)
        _pairs[key] = n
    return curses.color_pair(_pairs[key])


MASCOT_ACTIVE = dict(MASCOT_COLORS)


def setup_mascot_colors():
    """Si le terminal le permet, redéfinit quelques couleurs pour afficher les teintes EXACTES de l'image."""
    if curses.COLORS < 256 or not curses.can_change_color():
        return
    try:
        for key, slot in MASCOT_SLOTS.items():
            r, g, b = MASCOT_RGB[key]
            curses.init_color(slot, r * 1000 // 255, g * 1000 // 255, b * 1000 // 255)
            MASCOT_ACTIVE[key] = slot
    except curses.error:
        MASCOT_ACTIVE.update(MASCOT_COLORS)


def mascot_variant(ui):
    """Quelle image afficher maintenant ? Clignement ~0,3 s toutes les 5 s (parfois double), cache-œil en option."""
    cyc, ph = divmod(time.time() - ui.t0, 5.0)
    blinking = ui.blink and (ph < 0.3 or (int(cyc) % 3 == 0 and 0.55 < ph < 0.85))
    if ui.patch:
        return "patch_blink" if blinking else "patch"
    return "blink" if blinking else None


def draw_mascot(scr, y, x, A, variant=None):
    """Dessine l'image avec des quarts de bloc : 1 caractère = 4 pixels, 2 couleurs par caractère."""
    rich = curses.COLORS >= 256
    over = MASCOT_VARIANTS.get(variant, {})
    for r, row in enumerate(MASCOT):
        for c in range(len(row) // 3):
            cell = over.get((r, c)) or row[3 * c:3 * c + 3]
            m, fg, bg = int(cell[0], 16), cell[1], cell[2]
            if m == 0 and bg == "k":
                continue
            if rich:
                attr = img_pair(MASCOT_ACTIVE[fg], 0 if bg == "k" else MASCOT_ACTIVE[bg])
            elif fg == "k":
                continue
            else:
                attr = A["main"]
            put(scr, y + r, x + c, QUADS[m], attr)


def box(scr, y, x, h, w, title, A):
    if h < 3 or w < 6:
        return
    put(scr, y, x, "┌" + "─" * (w - 2) + "┐", A["dim"])
    for i in range(1, h - 1):
        put(scr, y + i, x, "│", A["dim"]); put(scr, y + i, x + w - 1, "│", A["dim"])
    put(scr, y + h - 1, x, "└" + "─" * (w - 2) + "┘", A["dim"])
    if title:
        put(scr, y, x + 2, f"┤ {title} ├", A["main"])


def level_attr(pct, A):
    return A["err"] if pct >= 85 else A["warn"] if pct >= 70 else A["main"]


def draw_graph(scr, y, x, h, w, title, hist, A):
    vals = list(hist)[-(w - 2):] if w > 2 else []
    vals = [0] * (w - 2 - len(vals)) + vals
    peak = max(vals + [10240])
    box(scr, y, x, h, w, f"{title}  {human(vals[-1], '/s')}   pic {human(max(vals), '/s')}", A)
    for i, row in enumerate(chart(vals, h - 2, peak)):
        put(scr, y + 1 + i, x + 1, row, A["main"])


def draw_conns(scr, y, x, h, w, data, ui, A):
    """Relais du réseau Tor connectés au tien, en temps réel. Aucun client / bridge n'est détaillé."""
    conns = sorted(data.get("conns", []), key=lambda c: -c["first"])
    rows = max(0, h - 5)
    box(scr, y, x, h, w, f"RELAIS CONNECTES ({len(conns)})  temps réel", A)
    iw, now = w - 4, time.time()
    put(scr, y + 1, x + 2, f"  {'PAYS':<4} {'ADRESSE':<22} {'NOM':<18} {'ROLE':<5} {'DEPUIS':>6}"[:iw], A["dim"])
    for i, c in enumerate(conns[:rows]):
        age = now - c["first"]
        cc = (c["cc"] or "??").upper()
        flag = flag_emoji(cc)
        shown = (flag + "  ") if (ui.emoji and flag) else f"[{cc[:2]:<2}]"
        row = (f"{'+' if age < 6 else ' '} {shown} {c['ip'] + ':' + str(c['port']):<22} {c['nick'][:18]:<18} "
               f"{short_flags(c['flags']):<5} {fmt_age(age):>6}")
        put(scr, y + 2 + i, x + 2, row[:iw], A["warn"] if age < 6 else A["main"])
    if len(conns) > rows:
        put(scr, y + h - 3, x + 2, f"  … +{len(conns) - rows} autres"[:iw], A["dim"])
    note = f"{data.get('hidden', 0)} autres connexions masquées (confidentialité)"
    put(scr, y + h - 2, x + 2, note[:iw], A["dim"])
    if not conns:
        put(scr, y + 3, x + 4, "Aucun relais connecté pour l'instant (ou vue indisponible).", A["dim"])


def draw_details(scr, y, x, h, w, ui, data, A):
    """Résumé en direct des relais connectés : totaux, rôles, mouvements récents, pays."""
    box(scr, y, x, h, w, "CONNEXIONS", A)
    iw, ih, now = w - 4, h - 2, time.time()
    conns, ev = data.get("conns", []), list(ui.events)
    arr = sum(1 for t, k, _ in ev if k == "+" and now - t <= 60)
    dep = sum(1 for t, k, _ in ev if k == "-" and now - t <= 60)
    n = lambda role: sum(1 for c in conns if role in c["flags"])
    lines = [(f"relais {len(conns)}   masquées {data.get('hidden', 0)}", A["main"]),
             (f"60 s : +{arr} / -{dep}", A["main"]),
             (f"G{n('Guard')} E{n('Exit')} H{n('HSDir')} F{n('Fast')} S{n('Stable')}", A["dim"]),
             ("mouvements", A["dim"])]
    for t, k, c in reversed(ev[-6:]):
        age = now - t
        cc = (c["cc"] or "??").upper()[:2]
        attr = (A["warn"] if k == "+" else A["err"]) if age < 6 else A["dim"]
        lines.append((f"{k} {fmt_age(age):>4} [{cc}] {c['nick']}", attr))
    if not ev:
        lines.append(("(rien pour l'instant)", A["dim"]))
    countries = collections.Counter((c["cc"] or "??").upper()[:2] for c in conns).most_common(3)
    if countries:
        lines.append(("pays", A["dim"]))
        for cc, k in countries:
            lines.append((f"[{cc}] {bar(100 * k / countries[0][1], 8)} {k}", A["main"]))
    for i, (txt, attr) in enumerate(lines[:ih]):
        put(scr, y + 1 + i, x + 2, txt[:iw], attr)


def draw(scr, ui, src, sysd, data, A):
    scr.erase()
    H, W = scr.getmaxyx()
    if H < 24 or W < 80:
        put(scr, 0, 0, f"Agrandis le terminal (80x24 minimum, actuellement {W}x{H}).", A["warn"])
        scr.refresh(); return
    # --- en-tête : logo + infos
    show_img = ui.show_img and W >= 115 and H >= 40
    ox, dy, hh = (34, (len(MASCOT) - 7) // 2, len(MASCOT)) if show_img else (0, 0, 7)
    if show_img:
        draw_mascot(scr, 0, 1, A, mascot_variant(ui))
    for i, line in enumerate(LOGO):
        put(scr, i + dy, ox + 3, line, A["main"])
    put(scr, 5 + dy, ox, SINCE, A["warn"] | curses.A_ITALIC if hasattr(curses, "A_ITALIC") else A["warn"])
    info, x0 = src.info, ox + 47
    fp = info["fingerprint"]
    state = ("● EN LIGNE", A["main"]) if data.get("ok") else ("● DECONNECTE", A["err"])
    rows = [("relais ", info["nickname"]), ("tor    ", info["version"]), ("uptime ", fmt_uptime(data["uptime"])),
            ("empr.  ", fp[:6] + "…" + fp[-6:] if len(fp) > 14 else fp),
            ("trafic ", f"↓{human(data['read'])}  ↑{human(data['written'])}"), ("circuit", f"{data['circuits']} ouverts")]
    for i, (k, v) in enumerate(rows):
        put(scr, i + dy, x0, f"{k} ", A["dim"]); put(scr, i + dy, x0 + 8, v, A["main"])
    put(scr, 6 + dy, x0, state[0], state[1])
    put(scr, 6 + dy, x0 + 14, f"[{src.name}] {THEMES[ui.theme][0]}", A["dim"])
    # --- zone centrale
    logh = 9 if H >= 36 else 7
    top = hh + 1
    mid_h = H - top - logh - 1
    lw = W * 2 // 3
    dh = mid_h // 2
    if ui.mode == 1:
        draw_conns(scr, top, 0, mid_h, lw, data, ui, A)
    else:
        draw_graph(scr, top, 0, dh, lw, "▼ DOWNLOAD", ui.down, A)
        draw_graph(scr, top + dh, 0, mid_h - dh, lw, "▲ UPLOAD", ui.up, A)
    # --- panneau système
    rx, rw = lw, W - lw
    sys_h = 7 if mid_h - 7 >= 7 else mid_h
    box(scr, top, rx, sys_h, rw, "SYSTEME", A)
    bw = max(4, rw - 2 - 7 - 7)
    items = [("CPU ", sysd["cpu"], f"{sysd['cpu']:.0f}%" if sysd["cpu"] is not None else "n/a"),
             ("RAM ", sysd["mem"], f"{sysd['mem'] or 0:.0f}%"),
             ("DISK", sysd["disk"], f"{sysd['disk']:.0f}%")]
    if sysd["temp"] is not None:
        items.insert(1, ("TEMP", sysd["temp"] / 85 * 100, f"{sysd['temp']:.0f}°C"))
    for i, (lab, pct, txt) in enumerate(items):
        yy = top + 1 + i
        put(scr, yy, rx + 2, lab, A["dim"])
        put(scr, yy, rx + 7, bar(pct, bw), level_attr(pct or 0, A))
        put(scr, yy, rx + 8 + bw, txt, A["main"])
    if sysd["load"]:
        put(scr, top + 1 + len(items), rx + 2, "LOAD " + " ".join(f"{v:.2f}" for v in sysd["load"]), A["main"])
    if mid_h - sys_h >= 7:
        draw_details(scr, top + sys_h, rx, mid_h - sys_h, rw, ui, data, A)
    # --- journal
    ly = H - logh - 1
    box(scr, ly, 0, logh, W, "JOURNAL TOR", A)
    for i, (ts, lvl, msg) in enumerate(list(src.logs)[-(logh - 2):]):
        a = A["err"] if lvl == "ERR" else A["warn"] if lvl == "WARN" else A["dim"]
        put(scr, ly + 1 + i, 2, f"{ts} {lvl[:4]:4} {msg}"[: W - 4], a)
    put(scr, H - 1, 1, " q quitter · t thème · m vue · p cache-œil · b clignement · f drapeaux · i image · s o l a r i s ", A["dim"])
    scr.refresh()


def main_loop(scr, src):
    curses.curs_set(0)
    curses.start_color()
    setup_mascot_colors()
    ui = UI()
    A = make_attrs(ui.theme)
    scr.bkgd(" ", curses.color_pair(1))
    sysst = SysStats()
    sysd = sysst.read()
    data = src.poll()
    ui.track(data.get("conns", []))
    last = time.time()
    scr.timeout(200)
    while True:
        if time.time() - last >= 1:
            try:
                data = src.poll()
            except Exception:
                data = dict(data, ok=False, down=0, up=0)
            sysd = sysst.read()
            ui.down.append(data["down"]); ui.up.append(data["up"])
            ui.track(data.get("conns", []))
            last = time.time()
        draw(scr, ui, src, sysd, data, A)
        k = scr.getch()
        if k in (ord("q"), ord("Q"), 27):
            break
        if k in (ord("t"), ord("T")):
            ui.theme = (ui.theme + 1) % len(THEMES)
            A = make_attrs(ui.theme)
        elif k in (ord("m"), ord("M")):
            ui.mode = (ui.mode + 1) % 2
        elif k in (ord("g"), ord("G")):
            ui.mode = 0
        elif k in (ord("c"), ord("C")):
            ui.mode = 1
        elif k in (ord("p"), ord("P")):
            ui.patch = not ui.patch
        elif k in (ord("b"), ord("B")):
            ui.blink = not ui.blink
        elif k in (ord("f"), ord("F")):
            ui.emoji = not ui.emoji
        elif k in (ord("i"), ord("I")):
            ui.show_img = not ui.show_img
        elif k == curses.KEY_RESIZE:
            scr.clear()


def main():
    ap = argparse.ArgumentParser(description="Tableau de bord Tor 'solaris'")
    ap.add_argument("--demo", action="store_true", help="fausses données (sans Tor)")
    ap.add_argument("--port", type=int, default=9051, help="ControlPort (défaut 9051)")
    ap.add_argument("--socket", help="socket de contrôle, ex. /run/tor/control")
    ap.add_argument("--ask-password", action="store_true", help="demander le mot de passe du ControlPort")
    args = ap.parse_args()
    locale.setlocale(locale.LC_ALL, "")
    pwd = getpass.getpass("Mot de passe ControlPort : ") if args.ask_password else os.environ.get("TOR_CONTROL_PASSWORD")
    src = DemoSource() if args.demo else TorSource(args.port, args.socket, pwd)
    try:
        curses.wrapper(main_loop, src)
    finally:
        sys.stdout.write("\033]104\007")   # remet la palette du terminal à l'état d'origine
        sys.stdout.flush()


if __name__ == "__main__":
    main()
