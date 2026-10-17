import os
import re
import difflib
import xml.etree.ElementTree as ET

REGION_PREFS = {
    "USA / English": ["usa", "world", "en"],
    "Europe": ["europe", "world", "en"],
    "Japan": ["japan", "ja"],
    "World": ["world", "usa", "europe", "en"],
}

REGION_NAMES = {
    "usa", "europe", "japan", "world", "asia", "australia", "brazil", "canada", "china", "france", "germany",
    "hong kong", "italy", "korea", "netherlands", "spain", "sweden", "taiwan", "united kingdom", "uk", "russia",
    "scandinavia", "finland", "denmark", "norway", "portugal", "poland", "greece", "mexico", "argentina",
    "latin america", "india", "south africa", "new zealand", "belgium", "austria", "switzerland", "unknown",
}

REGION_CODES = {
    "u": ["usa"], "us": ["usa"], "e": ["europe"], "eu": ["europe"], "j": ["japan"], "jp": ["japan"], "w": ["world"],
    "ue": ["usa", "europe"], "ju": ["japan", "usa"], "uj": ["usa", "japan"], "je": ["japan", "europe"],
    "jue": ["japan", "usa", "europe"], "uk": ["united kingdom"], "a": ["australia"], "k": ["korea"], "ch": ["china"],
}

TAG_SEVERITY = {
    "pirate": 3, "hack": 3, "bootleg": 3, "bad dump": 3, "hw mod": 3, "mod": 3, "patched": 3, "trainer": 3, "cheat": 3,
    "beta": 2, "proto": 2, "prototype": 2, "alpha": 2, "demo": 2, "sample": 2, "preview": 2, "promo": 2,
    "kiosk": 2, "lodgenet": 2, "debug": 2, "trial": 2, "test": 2, "pre-release": 2, "taikenban": 2, "unl": 2,
    "addon": 2, "dlc": 2, "update": 2, "title update": 2, "theme": 2, "avatar": 2, "unlock key": 2, "data": 2,
    "firebrandx": 2,
    "aftermarket": 1, "homebrew": 1, "program": 1,
}

BRACKET_SEVERITY = {"b": 3, "h": 3, "p": 3, "t": 3, "o": 3, "f": 1, "a": 1}

BASE_VERSION_TAGS = {"v1.0", "v1.00", "v1.000", "rev 0", "rev a"}

_LANG_RE = re.compile(r'^[a-z]{2}(-[a-z]+)?$')

def _paren_tags(name):
    return [[t.strip().lower() for t in g.split(",") if t.strip()] for g in re.findall(r'\(([^)]*)\)', name)]

def _bracket_tags(name):
    return [g.strip().lower() for g in re.findall(r'\[([^\]]*)\]', name)]

def _first_word(token):
    m = re.match(r'[a-z\-]+', token)
    return m.group(0) if m else token

def _orig_tokens(orig_raw):
    tokens = set()
    for group in _paren_tags(orig_raw):
        for t in group:
            tokens.update(REGION_CODES.get(t, [t]))
            tokens.add(_first_word(t))
    return tokens

class MatchEngine:
    def __init__(self):
        self.hash_db = {}
        self.name_db = []
        self.name_set = set()
        self.ghost_db = {}
        self.ghost_list = []
        self.is_raw_math = False
        self.strip_n = True
        self.prefer_base = True

    def load_dats(self, dat_dir, logger_func=print):
        if self.hash_db: return True
        logger_func("Loading DAT files...")
        self.hash_db.clear()
        self.name_db.clear()
        if not os.path.exists(dat_dir):
            logger_func("DATPACK directory not found.")
            return False
            
        count = 0
        for root_dir, dirs, files in os.walk(dat_dir):
            for f in files:
                if f.lower().endswith(".dat") or f.lower().endswith(".xml"):
                    try:
                        tree = ET.parse(os.path.join(root_dir, f))
                        root = tree.getroot()
                        for game in root.findall('.//game'):
                            name = game.get('name', '')
                            if name: self.name_db.append(name)
                            for rom in game.findall('rom'):
                                crc = rom.get('crc', '').lower()
                                if crc and crc != "00000000" and name:
                                    self.hash_db[crc] = name
                                    count += 1
                    except: pass
        self.name_db[:] = dict.fromkeys(self.name_db)
        self.name_set = set(self.name_db)
        logger_func(f"Loaded {count} hashes from DATs.")
        return count > 0

    def clean_string(self, text, strip_num=True, strip_tags=True):
        s = text
        if strip_tags:
            s = re.sub(r'\(.*?\)', '', s)
            s = re.sub(r'\[.*?\]', '', s)
        if strip_num:
            s = re.sub(r'^\d{1,4}\s*[-_]?\s*', '', s)
        return s.strip()

    def update_math(self, is_raw, strip_n, logger_func=print):
        logger_func("Updating Math Engine / Ghost Dictionary...")
        new_db = {}
        if not is_raw:
            for real_name in self.name_db:
                g = self.clean_string(real_name, strip_num=strip_n, strip_tags=True)
                if not g: g = real_name
                if g not in new_db: new_db[g] = {}
                new_db[g][real_name] = None
            new_db = {g: list(reals) for g, reals in new_db.items()}
                
        self.ghost_db = new_db
        self.ghost_list = list(new_db.keys())
        self.is_raw_math = is_raw
        self.strip_n = strip_n

    def version_penalty(self, name, orig_tokens):
        severity = 0
        extras = 0
        for group in _paren_tags(name):
            if all(t in orig_tokens for t in group):
                continue
            if all(t in REGION_NAMES for t in group) or all(_LANG_RE.match(t) for t in group):
                continue
            if len(group) == 1 and group[0] in BASE_VERSION_TAGS:
                continue
            extras += 1
            for t in group:
                severity = max(severity, TAG_SEVERITY.get(t, TAG_SEVERITY.get(_first_word(t), 0)))
        for tag in _bracket_tags(name):
            if tag in orig_tokens or tag == "!":
                continue
            extras += 1
            severity = max(severity, BRACKET_SEVERITY.get(tag.rstrip("0123456789"), 0))
        return severity, extras

    def tie_break_key(self, name, orig_raw, orig_tokens, region_setting):
        tokens = set()
        for group in _paren_tags(name):
            for t in group:
                tokens.add(t)
                tokens.add(_first_word(t))
        overlap = len(orig_tokens & tokens)
        aliases = REGION_PREFS.get(region_setting, [])
        region = next((len(aliases) - i for i, a in enumerate(aliases) if a in tokens), 0)
        similarity = difflib.SequenceMatcher(None, orig_raw, name).ratio()
        if self.prefer_base:
            severity, extras = self.version_penalty(name, orig_tokens)
            return (-overlap, severity, -region, extras, -similarity, len(name))
        return (-overlap, -region, -similarity)

    def break_ties_list(self, candidates, orig_raw, region_setting):
        if len(candidates) == 1: return candidates
        orig_tokens = _orig_tokens(orig_raw)
        return sorted(candidates, key=lambda c: self.tie_break_key(c, orig_raw, orig_tokens, region_setting))

    def find_match(self, clean_name, orig_raw, curr_n, region_setting):
        alts = []
        if self.is_raw_math:
            if self.strip_n: clean_name = self.clean_string(clean_name, strip_num=True, strip_tags=False)
            
            if clean_name in self.name_set:
                return clean_name, 100, [(clean_name, 100)]
                
            matches = difflib.get_close_matches(clean_name, self.name_db, n=curr_n, cutoff=0.01)
            for m in matches:
                c = int(difflib.SequenceMatcher(None, clean_name, m).ratio() * 100)
                alts.append((m, c))
            if self.prefer_base and len(alts) > 1:
                orig_tokens = _orig_tokens(orig_raw)
                alts.sort(key=lambda a: (-a[1],) + self.tie_break_key(a[0], orig_raw, orig_tokens, region_setting))
        else:
            ghost_orig = self.clean_string(clean_name, strip_num=self.strip_n, strip_tags=True)
            
            if ghost_orig in self.ghost_db:
                sorted_reals = self.break_ties_list(self.ghost_db[ghost_orig], orig_raw, region_setting)
                return sorted_reals[0], 100, [(r, 100) for r in sorted_reals[:curr_n]]
                
            matches = difflib.get_close_matches(ghost_orig, self.ghost_list, n=curr_n, cutoff=0.01)
            for ghost in matches:
                c = int(difflib.SequenceMatcher(None, ghost_orig, ghost).ratio() * 100)
                sorted_reals = self.break_ties_list(self.ghost_db[ghost], orig_raw, region_setting)
                for r in sorted_reals:
                    if (r, c) not in alts: alts.append((r, c))
                    if len(alts) >= curr_n: break
                if len(alts) >= curr_n: break
                
        if alts:
            return alts[0][0], alts[0][1], alts
        return "Unknown", 0, []
