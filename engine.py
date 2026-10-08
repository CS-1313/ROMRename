import os
import re
import difflib
import xml.etree.ElementTree as ET

class MatchEngine:
    def __init__(self):
        self.hash_db = {}
        self.name_db = []
        self.ghost_db = {}
        self.ghost_list = []
        self.is_raw_math = False
        self.strip_n = True

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
                if g not in new_db: new_db[g] = []
                new_db[g].append(real_name)
                
        self.ghost_db = new_db
        self.ghost_list = list(new_db.keys())
        self.is_raw_math = is_raw
        self.strip_n = strip_n

    def break_ties_list(self, candidates, orig_raw, region_setting):
        if len(candidates) == 1: return candidates
        scores = [(c, difflib.SequenceMatcher(None, orig_raw, c).ratio()) for c in candidates]
        scores.sort(key=lambda x: x[1], reverse=True)
        if len(scores) > 1 and (scores[0][1] > scores[1][1] + 0.05): 
            return [x[0] for x in scores]
            
        region_aliases = []
        if region_setting == "USA / English": region_aliases = ["USA", "US", "En", "English", "World"]
        elif region_setting == "Europe": region_aliases = ["Europe", "EU", "En"]
        elif region_setting == "Japan": region_aliases = ["Japan", "JP", "Ja"]
        
        def score_region(name):
            s = 0
            name_lower = name.lower()
            for i, alias in enumerate(region_aliases):
                if alias.lower() in name_lower:
                    s += (100 - i)
            return s
            
        return sorted(candidates, key=score_region, reverse=True)

    def find_match(self, clean_name, orig_raw, curr_n, region_setting):
        alts = []
        if self.is_raw_math:
            if self.strip_n: clean_name = self.clean_string(clean_name, strip_num=True, strip_tags=False)
            matches = difflib.get_close_matches(clean_name, self.name_db, n=curr_n, cutoff=0.01)
            for m in matches:
                c = int(difflib.SequenceMatcher(None, clean_name, m).ratio() * 100)
                alts.append((m, c))
        else:
            ghost_orig = self.clean_string(clean_name, strip_num=self.strip_n, strip_tags=True)
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
