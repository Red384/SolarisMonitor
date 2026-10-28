#!/usr/bin/env python3
"""solaris-monitor : tableau de bord Tor en terminal (alternative visuelle à Nyx).

Il se connecte au ControlPort de Tor comme Nyx (via la bibliothèque `stem`, déjà
installée si Nyx l'est) et affiche : graphiques de bande passante, état du Pi,
circuits et journal Tor. AUCUNE adresse IP de client n'est affichée.

    python3 solaris-monitor.py                 # relais réel (ControlPort 9051)
    python3 solaris-monitor.py --demo          # fausses données, pour voir le rendu
    python3 solaris-monitor.py --socket /run/tor/control
    sudo -u debian-tor python3 solaris-monitor.py   # si l'accès est refusé

Touches : q = quitter, t = thème, m = changer de vue, g = graphes, c = relais connectés,
         s = infos du serveur Tor, n = réseau Tor global (Tor Metrics) puis 1-4 ou ←/→ pour les pages
         et u pour actualiser, a = à propos / remerciements, r = pluie Matrix on/off, f = drapeaux emoji, i = mascotte,
         p = cache-œil de pirate, b = clignement des yeux on/off.
La vue « n » lit les données PUBLIQUES de https://metrics.torproject.org, seulement quand tu l'ouvres
(désactivable avec --no-metrics). En haut à droite : les flags de TON relais (Guard, HSDir, Fast...) ; légendes dans les vues « c » et « s ».
Vue « relais connectés » : les relais du réseau Tor reliés au tien (adresses publiques du consensus),
avec pays, nom, rôle et ancienneté. Les connexions de clients/bridges ne sont JAMAIS affichées.
(La mascotte demande un terminal de 115x40 ou plus.)
Taille minimale du terminal : 80 x 24.
"""
import argparse, collections, csv, curses, datetime, getpass, locale, math, os, random, shutil, sys, threading, time
import textwrap, urllib.parse, urllib.request, zlib

# ---------------------------------------------------------------- remerciements (à modifier librement)
THANKS = [
    "Le Tor Project, et toutes les personnes qui développent et améliorent Tor.",
    "Les bénévoles qui font tourner des relais, des ponts (bridges) et des services .onion.",
    "Damian Johnson, auteur de Stem et de Nyx, dont ce tableau de bord s'inspire.",
    "L'équipe de Tor Metrics, qui publie ses données en libre accès (CC0).",
    "Les communautés Python et ncurses, sur lesquelles tout repose.",
]
THANKS_PERSO = [   # ajoute ici tes propres remerciements (famille, amis, communauté...), un par ligne
]
FREEDOM = "Parler, lire et chercher librement : un droit pour tous, partout dans le monde."
FREEDOM_SHORT = "Parler et lire librement, un droit pour tous."
FREEDOM_REF = "Inspiré de l'article 19 de la Déclaration universelle des droits de l'homme (ONU, 1948)."
MEMORIAL = ("À la mémoire d'Aaron Swartz (1986-2013), programmeur et militant, "
            "qui s'est battu pour un internet ouvert et pour l'accès libre à la connaissance.")
FREEDOM_MORE = ("Chaque relais est une petite porte ouverte pour celles et ceux à qui l'on refuse la parole : "
                "journalistes, militants, familles séparées, simples curieux.")


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


# (nom du flag Tor, lettre, légende complète, légende courte)
FLAG_INFO = [
    ("Guard", "G", "entrée du réseau", "entrée"),
    ("Exit", "E", "sortie vers internet", "sortie"),
    ("HSDir", "H", "annuaire des .onion", ".onion"),
    ("Fast", "F", "débit suffisant", "rapide"),
    ("Stable", "S", "disponible longtemps", ""),
    ("V2Dir", "D", "sert l'annuaire", "annuaire"),
    ("Authority", "A", "autorité d'annuaire", "autorité"),
    ("BadExit", "B", "sortie douteuse", "douteuse"),
]
OTHER_FLAGS = [("Valid", "reconnu valide"), ("Running", "joignable, en ligne")]
OWN_FLAG_ORDER = [f[0] for f in FLAG_INFO] + [f[0] for f in OTHER_FLAGS]
ROLE_FLAGS = {"Guard", "Exit", "HSDir", "Authority"}


def short_flags(flags):
    return "".join(f[1] for f in FLAG_INFO if f[0] in flags)


def wrap_pieces(pieces, width, sep="  "):
    """Assemble des morceaux de texte en lignes de largeur maximale `width`."""
    lines, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(sep) + len(p) > width:
            lines.append(cur); cur = p
        else:
            cur = p if not cur else cur + sep + p
    if cur:
        lines.append(cur)
    return lines


def fmt_age(sec):
    sec = int(sec)
    if sec < 60: return f"{sec}s"
    if sec < 3600: return f"{sec // 60}m{sec % 60:02d}"
    return f"{sec // 3600}h{(sec % 3600) // 60:02d}"


def bar(pct, width):
    pct = max(0, min(100, pct or 0))
    f = int(round(width * pct / 100))
    return "━" * f + "╌" * (width - f)     # traits fins : les barres des lignes voisines ne se collent plus


# ---------------------------------------------------------------- pluie Matrix
class Rain:
    """Pluie de caractères façon Matrix : une goutte par colonne, vitesse et longueur aléatoires."""
    CHARS = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ:.=*+-<>|"

    def __init__(self, w, h):
        self.w, self.h, self.t = w, h, time.time()
        self.cols = [self._new(h, True) for _ in range(w)]

    @staticmethod
    def _new(h, first=False):
        return {"y": random.uniform(-h, h + 2) if first else random.uniform(-0.6 * h, 0),
                "v": random.uniform(4.0, 10.0), "n": random.randint(3, max(4, h + 3))}

    def step(self):
        now = time.time(); dt = min(now - self.t, 0.5); self.t = now
        for i, c in enumerate(self.cols):
            c["y"] += c["v"] * dt
            if c["y"] - c["n"] > self.h:
                self.cols[i] = self._new(self.h)

    def draw(self, scr, y0, x0, A):
        tick = int(time.time() * 7)
        for x, c in enumerate(self.cols):
            head = int(c["y"])
            for i in range(c["n"]):
                yy = head - i
                if 0 <= yy < self.h:
                    ch = self.CHARS[(x * 7 + yy * 13 + tick * (1 + x % 3) + i * 5) % len(self.CHARS)]
                    attr = A["head"] if i == 0 else A["main"] if i < 3 else A["dim"]
                    put(scr, y0 + yy, x0 + x, ch, attr)


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
        self.server, self.server_t = {}, 0

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

    @staticmethod
    def _txt(v):
        if isinstance(v, bytes):
            v = v.decode("utf-8", "replace")
        return str(v).strip() if v is not None else ""

    def _poll_server(self):
        """Infos sur TON relais : flags, débits, plateforme, joignabilité, mémoire de Tor..."""
        c, g, sv = self.c, self.c.get_info, {}
        try:
            e = c.get_network_status(default=None)          # sans argument : notre propre relais
        except Exception:
            e = None
        try:
            d = c.get_server_descriptor(default=None)
        except Exception:
            d = None
        sv["flags"] = list(e.flags) if e is not None and getattr(e, "flags", None) else []
        sv["weight"] = getattr(e, "bandwidth", None) if e is not None else None
        sv["address"] = g("address", None)
        if d is not None:
            sv["observed"], sv["average"], sv["burst"] = d.observed_bandwidth, d.average_bandwidth, d.burst_bandwidth
            sv["platform"], sv["contact"] = self._txt(d.platform), self._txt(d.contact)
            sv["address"], sv["or_port"] = d.address or sv["address"], d.or_port
            try:
                sv["exit"] = bool(d.exit_policy.is_exiting_allowed())
            except Exception:
                sv["exit"] = None
        sv["status"] = g("status/version/current", None)
        sv["reach"] = g("status/reachability-succeeded", None)
        try:
            pid = c.get_pid(None)
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        sv["rss_mb"] = int(line.split()[1]) // 1024
        except Exception:
            pass
        self.server = sv

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
        if now - self.server_t >= 30:
            self.server_t = now
            try:
                self._poll_server()
            except Exception:
                pass
        return {"down": max(down, 0), "up": max(up, 0), "read": r, "written": w,
                "uptime": int(g("uptime", 0)), "circuits": self.circuits, "ok": True,
                "conns": self.conns, "hidden": self.hidden,
                "server": self.server, "flags": self.server.get("flags", [])}


class DemoSource:
    """Fausses données pour prévisualiser l'interface sans Tor."""
    name = "DEMO"

    def __init__(self):
        self.logs = collections.deque(maxlen=200)
        self.info = {"nickname": "solaris", "version": "0.4.8.x", "fingerprint": "A1B2C3D4E5F60718293A4B5C6D7E8F9012345678"}
        self.down, self.up, self.r, self.w, self.t0 = 300_000, 120_000, 0, 0, time.time() - 93784
        self.server = {"flags": ["Fast", "Guard", "HSDir", "Running", "Stable", "V2Dir", "Valid"], "weight": 4210,
                       "address": "203.0.113.42", "or_port": 9001, "observed": 3_400_000, "average": 4_000_000,
                       "burst": 6_000_000, "platform": "Tor 0.4.8.x on Linux (Raspberry Pi 3 B+)",
                       "contact": "operateur@exemple.org", "exit": False, "status": "recommended",
                       "reach": "OR=1 DIR=1", "rss_mb": 118}
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
                "conns": list(self.peers), "hidden": 87,
                "server": self.server, "flags": self.server["flags"]}


# ---------------------------------------------------------------- Tor Metrics (réseau Tor global)
METRICS_FLAGS = ["Running", "Exit", "Guard", "Fast", "Stable", "HSDir"]
NET_PAGES = ["Réseau", "Débit", "Utilisateurs", "Versions"]


def demo_rows(name, p):
    """Fausses séries au format des CSV de Tor Metrics, pour tester l'affichage hors ligne (valeurs inventées)."""
    rnd = random.Random(zlib.crc32(name.encode()))
    start, end = datetime.date.fromisoformat(p["start"]), datetime.date.fromisoformat(p["end"])
    days = [start + datetime.timedelta(days=i) for i in range((end - start).days + 1)]
    wig = lambda i, base, amp, noise: base + amp * math.sin(i / 11.0) + (amp * 0.15 if i % 7 in (5, 6) else 0) + rnd.uniform(-noise, noise)
    cc_w = [("us", .17), ("de", .12), ("ru", .09), ("fr", .06), ("nl", .05), ("gb", .04), ("ir", .04), ("in", .03), ("br", .03), ("ua", .03)]
    rows = []
    for i, d in enumerate(days):
        ds = d.isoformat()
        if name == "networksize":
            rows.append({"date": ds, "relays": f"{wig(i, 7200, 350, 60):.0f}", "bridges": f"{wig(i, 1900, 250, 40):.0f}"})
        elif name == "relayflags":
            run = wig(i, 7200, 350, 40)
            share = {"Running": 1.0, "Exit": .18, "Guard": .42, "Fast": .93, "Stable": .86, "HSDir": .71}
            for fl in p.get("flag", METRICS_FLAGS):
                rows.append({"date": ds, "flag": fl, "relays": f"{run * share[fl]:.0f}"})
        elif name == "bandwidth":
            adv = wig(i, 820, 60, 8)
            rows.append({"date": ds, "advbw": f"{adv:.1f}", "bwhist": f"{adv * (0.62 + 0.05 * math.sin(i / 5)):.1f}"})
        elif name == "userstats-relay-country":
            total = wig(i, 2_100_000, 150_000, 20_000)
            rows.append({"date": ds, "country": "", "users": f"{total:.0f}", "lower": "", "upper": "", "frac": "93"})
            if p.get("country") != "all":
                for cc, w in cc_w:
                    rows.append({"date": ds, "country": cc, "users": f"{total * w * rnd.uniform(.95, 1.05):.0f}", "lower": "", "upper": "", "frac": "93"})
        elif name == "userstats-bridge-country":
            rows.append({"date": ds, "country": "", "users": f"{wig(i, 130_000, 12_000, 2_000):.0f}", "frac": "92"})
        elif name == "versions":
            for v, w in (("0.4.8", .55), ("0.4.7", .18), ("0.4.9", .15), ("0.4.5", .05), ("0.3.5", .03), ("0.4.6", .02)):
                rows.append({"date": ds, "version": v, "relays": f"{7200 * w:.0f}"})
        elif name == "platforms":
            rows.append({"date": ds, **{k: f"{7200 * w:.0f}" for k, w in (("linux", .86), ("windows", .06), ("bsd", .04), ("macos", .02), ("other", .02))}})
    return rows


class MetricsClient:
    """Lit les CSV publics de Tor Metrics en tâche de fond, seulement quand on ouvre la vue réseau."""
    BASE, TTL = "https://metrics.torproject.org/", 6 * 3600

    def __init__(self, enabled=True, demo=False):
        self.enabled, self.demo = enabled, demo
        self.state, self.lock = {}, threading.Lock()

    def fetch_rows(self, name, **params):
        if self.demo:
            return demo_rows(name, params)
        url = f"{self.BASE}{name}.csv?" + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(url, headers={"User-Agent": "solaris-monitor (tableau de bord Tor)"})
        with urllib.request.urlopen(req, timeout=25) as r:
            text = r.read().decode("utf-8", "replace")
        lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]   # commentaires, puis en-tête, puis données
        return list(csv.DictReader(lines))

    def _load(self, page):
        t = datetime.datetime.now(datetime.timezone.utc).date()
        day = lambda n: (t - datetime.timedelta(days=n)).isoformat()
        end = t.isoformat()
        f = self.fetch_rows
        if page == 0:
            return {"net": f("networksize", start=day(90), end=end),
                    "flags": f("relayflags", start=day(10), end=end, flag=METRICS_FLAGS)}
        if page == 1:
            return {"bw": f("bandwidth", start=day(90), end=end)}
        if page == 2:
            return {"users": f("userstats-relay-country", start=day(90), end=end, country="all", events="off"),
                    "countries": f("userstats-relay-country", start=day(8), end=end, events="off"),
                    "bridges": f("userstats-bridge-country", start=day(90), end=end, country="all")}
        return {"versions": f("versions", start=day(10), end=end), "platforms": f("platforms", start=day(10), end=end)}

    def ensure(self, page, force=False):
        if not self.enabled:
            return
        with self.lock:
            st = self.state.get(page)
            if st and st["status"] == "loading":
                return
            age = time.time() - st["ts"] if st else 1e9
            if not force and st and ((st["status"] == "ok" and age < self.TTL) or (st["status"] == "error" and age < 120)):
                return
            self.state[page] = {"status": "loading", "data": st["data"] if st else None, "error": None, "ts": time.time()}
        threading.Thread(target=self._worker, args=(page,), daemon=True).start()

    def _worker(self, page):
        try:
            res = {"status": "ok", "data": self._load(page), "error": None}
        except Exception as e:
            with self.lock:
                old = (self.state.get(page) or {}).get("data")
            res = {"status": "error", "data": old, "error": f"{type(e).__name__}: {e}"}
        res["ts"] = time.time()
        with self.lock:
            self.state[page] = res

    def get(self, page):
        with self.lock:
            return dict(self.state.get(page) or {})


def fmt_n(n):
    return f"{int(round(n)):,}".replace(",", " ")


def resample(vals, n):
    if n <= 0 or not vals:
        return []
    if len(vals) >= n:
        out = []
        for i in range(n):
            a = int(i * len(vals) / n); b = max(int((i + 1) * len(vals) / n), a + 1)
            out.append(sum(vals[a:b]) / len(vals[a:b]))
        return out
    return [vals[min(len(vals) - 1, int(i * len(vals) / n))] for i in range(n)]


def chart_range(vals, h, vmin, vmax):
    """Graphique en aires entre vmin et vmax (au moins 1/8 de case pour qu'on voie toujours la courbe)."""
    rows, span = [[" "] * len(vals) for _ in range(h)], (vmax - vmin) or 1.0
    for x, v in enumerate(vals):
        lvl = max(1, int((v - vmin) / span * (h * 8 - 1)) + 1)
        for r in range(h):
            rows[h - 1 - r][x] = BLOCKS[max(0, min(8, lvl - r * 8))]
    return ["".join(r) for r in rows]


def series(rows, col, where=None):
    out = []
    for r in rows or []:
        if where and not where(r):
            continue
        try:
            out.append((r["date"], float(r[col])))
        except (KeyError, ValueError, TypeError):
            pass
    out.sort()
    return out


def latest_by(rows, key, col, where=None):
    """Valeurs du dernier jour disponible : (date, {clé: valeur})."""
    rows = [r for r in rows or [] if (not where or where(r)) and r.get(col) not in (None, "")]
    if not rows:
        return None, {}
    last = max(r["date"] for r in rows)
    out = {}
    for r in rows:
        if r["date"] == last:
            try:
                out[r[key]] = float(r[col])
            except (KeyError, ValueError):
                pass
    return last, out


# ---------------------------------------------------------------- interface
class UI:
    def __init__(self):
        self.theme = 0
        self.show_img = True
        self.patch = False     # cache-œil de pirate
        self.blink = True      # clignement des yeux
        self.t0 = time.time()
        self.mode = 0          # 0 = graphes, 1 = relais connectés, 2 = serveur Tor
        self.rain = True       # pluie Matrix sous le logo
        self.rain_state = None
        self.metrics = None    # client Tor Metrics (créé dans main)
        self.net_page = 0
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
    curses.init_pair(5, 231 if rich else curses.COLOR_WHITE, black)
    return {"head": curses.color_pair(5) | curses.A_BOLD, "main": curses.color_pair(1) | curses.A_BOLD,
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


def trunc(v, n):
    return v if len(v) <= n else v[: max(0, n - 1)] + "…"


def draw_conns(scr, y, x, h, w, data, ui, A):
    """Relais du réseau Tor connectés au tien, en temps réel. Aucun client / bridge n'est détaillé."""
    conns = sorted(data.get("conns", []), key=lambda c: -c["first"])
    iw, now = w - 4, time.time()
    legend = wrap_pieces([f"{l} {n}" + (f" ({short})" if short else "") for n, l, _, short in FLAG_INFO], iw)
    avail = h - 4                                   # lignes intérieures hors en-tête de colonnes et note
    legend = legend[: min(len(legend), max(0, avail // 3))]    # la légende ne mange jamais plus d'un tiers
    base = max(0, avail - len(legend))
    more = len(conns) > base > 0
    rows = base - 1 if more else base
    box(scr, y, x, h, w, f"RELAIS CONNECTES ({len(conns)})  temps réel", A)
    put(scr, y + 1, x + 2, f"  {'PAYS':<4} {'ADRESSE':<21} {'NOM':<16} {'FLAGS':<8} {'DEPUIS':>6}"[:iw], A["dim"])
    for i, c in enumerate(conns[:rows]):
        age = now - c["first"]
        cc = (c["cc"] or "??").upper()
        flag = flag_emoji(cc)
        shown = (flag + "  ") if (ui.emoji and flag) else f"[{cc[:2]:<2}]"
        row = (f"{'+' if age < 6 else ' '} {shown} {c['ip'] + ':' + str(c['port']):<21} {c['nick'][:16]:<16} "
               f"{short_flags(c['flags']):<8} {fmt_age(age):>6}")
        put(scr, y + 2 + i, x + 2, row[:iw], A["warn"] if age < 6 else A["main"])
    if more:
        put(scr, y + 2 + rows, x + 2, f"  … +{len(conns) - rows} autres"[:iw], A["dim"])
    for i, line in enumerate(legend):
        put(scr, y + 2 + base + i, x + 2, line[:iw], A["dim"])
    put(scr, y + h - 2, x + 2, f"{data.get('hidden', 0)} autres connexions masquées (confidentialité)"[:iw], A["dim"])
    if not conns:
        put(scr, y + 3, x + 4, "Aucun relais connecté pour l'instant (ou vue indisponible).", A["dim"])


def draw_series(scr, y, x, h, w, label, pts, A, fmt=fmt_n, unit="", extra=""):
    if h < 2 or w < 10:
        return
    if not pts:
        put(scr, y, x, f"{label} : pas de données", A["dim"])
        return
    vals = [v for _, v in pts]; lo, hi = min(vals), max(vals)
    head = f"{label}  {fmt(vals[-1])}{unit}{extra}"
    full = f"{head}   min {fmt(lo)} · max {fmt(hi)} · {len(vals)} j"
    mid = f"{head}   min {fmt(lo)} · max {fmt(hi)}"
    put(scr, y, x, (full if len(full) <= w else mid if len(mid) <= w else head)[:w], A["main"])
    for i, row in enumerate(chart_range(resample(vals, w), h - 1, lo, hi)):
        put(scr, y + 1 + i, x, row, A["main"])


def draw_bars(scr, y, x, w, items, A, fmt=fmt_n, max_rows=99, flag_fn=None):
    """items : [(étiquette, valeur, part en %)] -> une ligne par élément avec barre fine."""
    bw = max(4, w - 9 - 10 - 6 - 3)
    biggest = max((v for _, v, _ in items), default=0) or 1
    for i, (lab, val, pct) in enumerate(items[:max_rows]):
        put(scr, y + i, x, f"{lab:<9}", A["dim"])
        put(scr, y + i, x + 10, bar(100 * val / biggest, bw), A["main"])
        put(scr, y + i, x + 11 + bw, f"{fmt(val):>9} {pct:4.0f}%"[: max(0, w - 11 - bw)], A["main"])


def net_page_network(scr, y, x, h, w, data, ui, A):
    two = w >= 90
    lw2 = (w * 60 // 100 - 1) if two else w
    h1 = h // 2
    draw_series(scr, y, x, h1, lw2, "Relais", series(data.get("net"), "relays"), A)
    draw_series(scr, y + h1, x, h - h1, lw2, "Ponts (bridges)", series(data.get("net"), "bridges"), A)
    if two:
        rx, rw = x + lw2 + 2, w - lw2 - 2
        last, vals = latest_by(data.get("flags"), "flag", "relays")
        put(scr, y, rx, f"Relais par flag  ({last or 'n/a'})", A["dim"])
        total = vals.get("Running") or max(vals.values(), default=0)
        items = [(f, vals[f], 100 * vals[f] / total if total else 0) for f in METRICS_FLAGS if f in vals]
        draw_bars(scr, y + 2, rx, rw, items, A)


def net_page_bandwidth(scr, y, x, h, w, data, ui, A):
    adv, used = series(data.get("bw"), "advbw"), series(data.get("bw"), "bwhist")
    extra = f"  · utilisation {100 * used[-1][1] / adv[-1][1]:.0f} %" if adv and used and adv[-1][1] else ""
    h1 = h // 2
    g = lambda v: f"{v:.0f}"
    draw_series(scr, y, x, h1, w, "Capacité annoncée", adv, A, fmt=g, unit=" Gbit/s")
    draw_series(scr, y + h1, x, h - h1, w, "Débit consommé", used, A, fmt=g, unit=" Gbit/s", extra=extra)


def net_page_users(scr, y, x, h, w, data, ui, A):
    is_all = lambda r: (r.get("country") or "") in ("", "all")
    users = series(data.get("users"), "users", is_all)
    bridges = series(data.get("bridges"), "users", is_all)
    two = w >= 90
    lw2 = (w * 60 // 100 - 1) if two else w
    draw_series(scr, y, x, h - 2, lw2, "Utilisateurs (relais)", users, A, unit="/jour")
    if bridges:
        put(scr, y + h - 1, x, f"Utilisateurs via ponts : {fmt_n(bridges[-1][1])}/jour"[:lw2], A["dim"])
    if two:
        rx, rw = x + lw2 + 2, w - lw2 - 2
        last, vals = latest_by(data.get("countries"), "country", "users", lambda r: (r.get("country") or "") not in ("", "all", "??"))
        _, tot = latest_by(data.get("countries"), "country", "users", lambda r: (r.get("country") or "") in ("", "all"))
        total = tot.get("") or sum(vals.values())
        put(scr, y, rx, f"Top pays par utilisateurs  ({last or 'n/a'})", A["dim"])
        top = sorted(vals.items(), key=lambda kv: -kv[1])[: max(0, h - 2)]
        items = []
        for cc, v in top:
            fl = flag_emoji(cc)
            items.append(((fl + " ") if (ui.emoji and fl) else f"[{cc.upper():<2}] ", v, 100 * v / total if total else 0))
        draw_bars(scr, y + 2, rx, rw, items, A)


def net_page_versions(scr, y, x, h, w, data, ui, A):
    two = w >= 70
    lw2 = (w * 55 // 100 - 1) if two else w
    last, vals = latest_by(data.get("versions"), "version", "relays")
    total = sum(vals.values())
    put(scr, y, x, f"Relais par version de Tor  ({last or 'n/a'})", A["dim"])
    top = sorted(vals.items(), key=lambda kv: -kv[1])[: max(0, h - 2)]
    draw_bars(scr, y + 2, x, lw2, [(v, n, 100 * n / total if total else 0) for v, n in top], A)
    if two:
        rx, rw = x + lw2 + 2, w - lw2 - 2
        plat = [r for r in (data.get("platforms") or []) if r.get("date")]
        put(scr, y, rx, "Relais par système", A["dim"])
        if plat:
            row = max(plat, key=lambda r: r["date"])
            pv = {k: float(row[k]) for k in ("linux", "windows", "bsd", "macos", "other") if row.get(k) not in (None, "")}
            ptot = sum(pv.values())
            draw_bars(scr, y + 2, rx, rw, [(k, v, 100 * v / ptot if ptot else 0) for k, v in sorted(pv.items(), key=lambda kv: -kv[1])], A)


NET_PAGE_FUNCS = [net_page_network, net_page_bandwidth, net_page_users, net_page_versions]


def draw_network(scr, y, x, h, w, ui, A):
    """Réseau Tor global (Tor Metrics) : sous-menu de 4 pages."""
    m = ui.metrics
    box(scr, y, x, h, w, "RESEAU TOR · TOR METRICS" + ("  (données fictives)" if m and m.demo else ""), A)
    if h < 12 or w < 60:
        put(scr, y + 2, x + 3, "Agrandis le terminal pour cette vue (environ 30 lignes).", A["dim"])
        return
    if m is None or not m.enabled:
        put(scr, y + 2, x + 3, "Tor Metrics désactivé (lancé avec --no-metrics).", A["dim"])
        return
    page = ui.net_page % len(NET_PAGES)
    m.ensure(page)
    st = m.get(page)
    cx = x + 2
    for i, name in enumerate(NET_PAGES):                       # sous-menu
        txt = f" {i + 1} {name} "
        put(scr, y + 1, cx, txt, (A["main"] | curses.A_REVERSE) if i == page else A["dim"])
        cx += len(txt) + 1
    put(scr, y + 1, cx + 2, "← → pages · u actualiser", A["dim"])
    cy, ch, cw = y + 3, h - 5, w - 4
    data, status = st.get("data"), st.get("status")
    if data:
        NET_PAGE_FUNCS[page](scr, cy, x + 2, ch, cw, data, ui, A)
    if status == "error":
        msg, attr = f"erreur : {st.get('error')}  (u pour réessayer)", A["err"]
    elif status == "loading" or not st:
        msg, attr = "chargement depuis metrics.torproject.org…", A["warn"]
    else:
        ago = int((time.time() - st["ts"]) // 60)
        msg, attr = f"source : Tor Metrics (CC0) · actualisé il y a {ago} min" + ("  · DEMO : valeurs inventées" if m.demo else ""), A["dim"]
    put(scr, y + h - 2, x + 2, msg[: w - 4], attr)


def draw_about(scr, y, x, h, w, ui, A):
    """Remerciements, liberté d'expression et hommage."""
    box(scr, y, x, h, w, "A PROPOS · REMERCIEMENTS", A)
    put(scr, y + 1, x + 3, "solaris  ·  Since 2008", A["warn"])

    def section(title, parts, width):
        out = [(title, A["dim"], 0)]
        for text, attr in parts:
            out += [(l, attr, 2) for l in textwrap.wrap(text, max(10, width - 4)) or [""]]
        return out

    iw = w - 6
    two = iw >= 80
    cw = (iw - 4) // 2 if two else iw
    thanks = section("MERCI", [(t, A["main"]) for t in THANKS + THANKS_PERSO], cw)
    free = section("LIBERTE D'EXPRESSION", [("« " + FREEDOM + " »", A["warn"]), (FREEDOM_REF, A["dim"]), (FREEDOM_MORE, A["main"])], cw)
    memo = section("EN MEMOIRE", [(MEMORIAL, A["main"])], cw)
    top, rows = y + 3, h - 4
    if two:
        cols = [(x + 3, thanks), (x + 3 + cw + 4, free + [("", A["dim"], 0)] + memo)]
    else:
        cols = [(x + 3, thanks + [("", A["dim"], 0)] + memo + [("", A["dim"], 0)] + free)]
    for cx, lines in cols:
        for i, (txt, attr, ind) in enumerate(lines[:rows]):
            put(scr, top + i, cx + ind, txt[:cw], attr)


def draw_topbar(scr, W, src, data, A):
    """Ligne du haut : nom du relais à gauche, flags de TON relais à droite."""
    put(scr, 0, 1, f"◆ {src.info['nickname']}", A["main"])
    flags = [f for f in OWN_FLAG_ORDER if f in data.get("flags", [])]
    left_end = 5 + len(src.info["nickname"])
    right_start = W - 2 - (6 + sum(len(f) + 1 for f in flags)) if flags else W - 16
    if right_start - left_end >= len(FREEDOM_SHORT) + 4:
        put(scr, 0, left_end + (right_start - left_end - len(FREEDOM_SHORT)) // 2, FREEDOM_SHORT, A["dim"])
    if not flags:
        put(scr, 0, max(1, W - 16), "flags : n/a", A["dim"])
        return
    x = W - 2 - (6 + sum(len(f) + 1 for f in flags))
    put(scr, 0, x, "FLAGS ", A["dim"]); x += 6
    for f in flags:
        put(scr, 0, x, f, A["warn"] if f in ROLE_FLAGS else A["main"]); x += len(f) + 1


def put_flow(scr, y, x, width, pieces, max_lines=99, sep=2):
    """Écrit des morceaux (texte, couleur) à la suite, en passant à la ligne quand il n'y a plus de place."""
    cx, line = 0, 0
    for text, attr in pieces:
        if cx and cx + sep + len(text) > width:
            line += 1; cx = 0
        if line >= max_lines:
            break
        cx += sep if cx else 0
        put(scr, y + line, x + cx, text, attr); cx += len(text)
    return line + 1


def draw_server(scr, y, x, h, w, src, data, ui, A):
    """Informations sur le serveur Tor (ton relais) + légende des flags."""
    box(scr, y, x, h, w, "SERVEUR TOR", A)
    sv, iw, ih = data.get("server") or {}, w - 4, h - 2
    if not sv:
        put(scr, y + 2, x + 3, "Infos du relais indisponibles (relais pas encore publié dans le consensus ?).", A["dim"])
        return
    info, status = src.info, sv.get("status")
    rate = lambda v: human(v, "/s") if v is not None else "n/a"
    reach = sv.get("reach") or ""
    reach_txt = f"ORPort {'✔' if 'OR=1' in reach else '✘'}   DirPort {'✔' if 'DIR=1' in reach else '✘'}" if reach else "n/a"
    ok_status = status in (None, "recommended", "new in series", "new")
    kind = {True: "relais de sortie (exit)", False: "relais non-exit"}.get(sv.get("exit"), "n/a")
    fp = info["fingerprint"]
    vw = (iw - 36 - 2 - 14) if iw >= 76 else iw - 14            # largeur disponible pour les valeurs
    fp_rows = [("empreinte", fp, A["main"])] if len(fp) <= vw else [("empreinte", fp[:20], A["main"]), ("", fp[20:], A["main"])]
    rows = [("nom", info["nickname"], A["main"]), *fp_rows,
            ("adresse", f"{sv.get('address') or 'n/a'}:{sv.get('or_port', '?')}", A["main"]),
            ("version", info["version"] + (f" ({status})" if status else ""), A["main"] if ok_status else A["warn"]),
            ("plateforme", sv.get("platform") or "n/a", A["main"]), ("contact", sv.get("contact") or "n/a", A["main"]),
            ("uptime", fmt_uptime(data["uptime"]), A["main"]), ("joignable", reach_txt, A["main"]),
            ("débit observé", rate(sv.get("observed")), A["main"]),
            ("débit moyen", rate(sv.get("average")) + (f"  burst {rate(sv.get('burst'))}" if sv.get("burst") else ""), A["main"]),
            ("poids", str(sv["weight"]) if sv.get("weight") is not None else "n/a", A["main"]),
            ("type", kind, A["main"]),
            ("mémoire tor", f"{sv['rss_mb']} Mo" if sv.get("rss_mb") is not None else "n/a", A["main"]),
            ("circuits", str(data["circuits"]), A["main"]),
            ("connexions OR", f"{len(data.get('conns', []))} relais + {data.get('hidden', 0)} masquées", A["main"])]
    own = set(sv.get("flags", []))
    flag_attr = lambda n: (A["warn"] if n in ROLE_FLAGS else A["main"]) if n in own else A["dim"]
    dot = lambda n: "● " if n in own else "○ "
    if iw >= 76:                                     # deux colonnes : infos à gauche, légende complète à droite
        leg_w = 36; left_w = iw - leg_w - 2
        for i, (k, v, a) in enumerate(rows[:ih]):
            put(scr, y + 1 + i, x + 2, f"{k:<14}", A["dim"])
            put(scr, y + 1 + i, x + 16, trunc(v, left_w - 14), a)
        lx = x + 2 + left_w + 2
        put(scr, y + 1, lx, "FLAGS  (● obtenu  ○ non)", A["dim"])
        legend = [(n, g) for n, _, g, _ in FLAG_INFO] + OTHER_FLAGS
        for i, (n, g) in enumerate(legend[: ih - 1]):
            put(scr, y + 2 + i, lx, trunc(dot(n) + f"{n:<10}{g}", leg_w), flag_attr(n))
    else:                                            # une colonne : infos puis légende compacte
        pieces = [(dot(n) + n + (f" ({short})" if short else ""), flag_attr(n)) for n, _, _, short in FLAG_INFO] + \
                 [(dot(n) + n, flag_attr(n)) for n, _ in OTHER_FLAGS]
        n_leg = len(wrap_pieces([t for t, _ in pieces], iw))
        shown = rows[: max(0, ih - n_leg - 1)]
        for i, (k, v, a) in enumerate(shown):
            put(scr, y + 1 + i, x + 2, f"{k:<14}", A["dim"])
            put(scr, y + 1 + i, x + 16, trunc(v, iw - 14), a)
        put_flow(scr, y + 2 + len(shown), x + 2, iw, pieces, max_lines=max(0, ih - len(shown) - 1))


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
    # --- barre du haut : nom du relais + flags de TON relais
    draw_topbar(scr, W, src, data, A)
    # --- en-tête : mascotte, logo, infos, pluie Matrix
    show_img = ui.show_img and W >= 115 and H >= 42
    if show_img:
        ox, dy, hh = 34, 1 + (len(MASCOT) - 7) // 2, 1 + len(MASCOT)
        draw_mascot(scr, 1, 1, A, mascot_variant(ui))
    else:
        ox, dy, hh = 0, 1, 8
    rain_y, rain_rows = dy + 8, 0
    if ui.rain and ui.mode != 4:                      # la page « à propos » récupère la place de la Matrix
        if show_img:
            rain_rows = hh - rain_y
        elif H >= 40:
            rain_rows = 4
            hh = rain_y + rain_rows + 1
    for i, line in enumerate(LOGO):
        put(scr, i + dy, ox + 3, line, A["main"])
    put(scr, 5 + dy, ox, SINCE, A["warn"] | curses.A_ITALIC if hasattr(curses, "A_ITALIC") else A["warn"])
    info, x0 = src.info, ox + 47
    fp = info["fingerprint"]
    state = ("● EN LIGNE", A["main"]) if data.get("ok") else ("● DECONNECTE", A["err"])
    status = (data.get("server") or {}).get("status")
    rows = [("relais ", info["nickname"]), ("tor    ", info["version"] + (f" ({status})" if status else "")),
            ("uptime ", fmt_uptime(data["uptime"])),
            ("empr.  ", fp[:6] + "…" + fp[-6:] if len(fp) > 14 else fp),
            ("trafic ", f"↓{human(data['read'])}  ↑{human(data['written'])}"), ("circuit", f"{data['circuits']} ouverts")]
    for i, (k, v) in enumerate(rows):
        put(scr, i + dy, x0, f"{k} ", A["dim"]); put(scr, i + dy, x0 + 8, v, A["main"])
    put(scr, 6 + dy, x0, state[0], state[1])
    put(scr, 6 + dy, x0 + 14, f"[{src.name}] {THEMES[ui.theme][0]}", A["dim"])
    if rain_rows >= 2:
        rw_ = W - ox - 1
        if ui.rain_state is None or (ui.rain_state.w, ui.rain_state.h) != (rw_, rain_rows):
            ui.rain_state = Rain(rw_, rain_rows)
        ui.rain_state.step()
        ui.rain_state.draw(scr, rain_y, ox, A)
    # --- zone centrale
    logh = 9 if H >= 36 else 7
    top = hh + 1
    mid_h = H - top - logh - 1
    lw = W if ui.mode in (3, 4) else W * 2 // 3     # les vues « réseau » et « à propos » prennent toute la largeur
    dh = mid_h // 2
    if ui.mode == 4:
        draw_about(scr, top, 0, mid_h, W, ui, A)
    elif ui.mode == 3:
        draw_network(scr, top, 0, mid_h, W, ui, A)
    elif ui.mode == 1:
        draw_conns(scr, top, 0, mid_h, lw, data, ui, A)
    elif ui.mode == 2:
        draw_server(scr, top, 0, mid_h, lw, src, data, ui, A)
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
    put(scr, H - 1, 1, " 1-4 ou ←/→ pages · u actualiser · m vue suivante · t thème · q quitter " if ui.mode == 3 else
        " q quitter · t thème · m/g/c/s/n/a vues · r matrix · p pirate · b clignement · f drapeaux · i image ", A["dim"])
    scr.refresh()


def main_loop(scr, src, metrics=None):
    curses.curs_set(0)
    curses.start_color()
    setup_mascot_colors()
    ui = UI()
    ui.metrics = metrics
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
            ui.mode = (ui.mode + 1) % 5
        elif k in (ord("g"), ord("G")):
            ui.mode = 0
        elif k in (ord("c"), ord("C")):
            ui.mode = 1
        elif k in (ord("s"), ord("S")):
            ui.mode = 2
        elif k in (ord("n"), ord("N")):
            ui.mode = 3
        elif k in (ord("a"), ord("A")):
            ui.mode = 4
        elif ui.mode == 3 and ord("1") <= k <= ord("4"):
            ui.net_page = k - ord("1")
        elif ui.mode == 3 and k in (curses.KEY_RIGHT, ord("]")):
            ui.net_page = (ui.net_page + 1) % len(NET_PAGES)
        elif ui.mode == 3 and k in (curses.KEY_LEFT, ord("[")):
            ui.net_page = (ui.net_page - 1) % len(NET_PAGES)
        elif ui.mode == 3 and k in (ord("u"), ord("U")) and ui.metrics:
            ui.metrics.ensure(ui.net_page, force=True)
        elif k in (ord("r"), ord("R")):
            ui.rain = not ui.rain
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
    ap.add_argument("--no-metrics", action="store_true", help="n'interroge jamais metrics.torproject.org (vue réseau désactivée)")
    ap.add_argument("--ask-password", action="store_true", help="demander le mot de passe du ControlPort")
    args = ap.parse_args()
    locale.setlocale(locale.LC_ALL, "")
    pwd = getpass.getpass("Mot de passe ControlPort : ") if args.ask_password else os.environ.get("TOR_CONTROL_PASSWORD")
    src = DemoSource() if args.demo else TorSource(args.port, args.socket, pwd)
    try:
        curses.wrapper(main_loop, src, MetricsClient(enabled=not args.no_metrics, demo=args.demo))
    finally:
        sys.stdout.write("\033]104\007")   # remet la palette du terminal à l'état d'origine
        sys.stdout.flush()


if __name__ == "__main__":
    main()
