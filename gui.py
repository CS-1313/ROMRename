import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, zipfile, threading, datetime, difflib, zlib
import xml.etree.ElementTree as ET
import shutil
import file_ops
from engine import MatchEngine
import time
import re

class ROMRenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ROMRename")
        self.root.geometry("1000x780")
        
        self.scan_results = []
        self.engine = MatchEngine()
        self.virtual_plan = []
        self.overrides = {}
        self.name_overrides = {}
        self.excluded_exts = set()
        self.excluded_folders = set()
        
        self.is_paused = False
        self.cancel_flag = False
        self.is_scanning = False  
        
        
        self.active_cb = None
        self.was_selected = False
        self.log_queue = []
        
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.build_ui()
        self.flush_logs()
        
    def build_ui(self):
        # Top-level notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.tab_main = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text="Dashboard")
        self.notebook.add(self.tab_settings, text="Settings & Engine")
        
        self.tab_exclusions = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_exclusions, text="Exclusions")
        
        self.current_tab = 0
        self.switching_tabs = False
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # --- TAB 3: EXCLUSIONS ---
        exc_top = tk.Frame(self.tab_exclusions)
        exc_top.pack(fill="x", padx=10, pady=5)
        tk.Button(exc_top, text="Scan Source Directory", command=self.populate_exclusions, bg="lightyellow").pack(side="left", padx=5)
        tk.Label(exc_top, text="(Note: ☐ = Included, ☑ = EXCLUDED)").pack(side="left", padx=20)
        tk.Button(exc_top, text="Expand All", command=lambda: self.set_tree_open(self.tree_folders, True)).pack(side="right", padx=2)
        tk.Button(exc_top, text="Collapse All", command=lambda: self.set_tree_open(self.tree_folders, False)).pack(side="right", padx=2)
        
        pane = tk.PanedWindow(self.tab_exclusions, orient="vertical")
        pane.pack(fill="both", expand=True, padx=10, pady=5)
        
        frame_sub = tk.LabelFrame(pane, text="Subfolders")
        pane.add(frame_sub, stretch="always")
        self.tree_folders = ttk.Treeview(frame_sub, show="tree")
        self.tree_folders.pack(side="left", fill="both", expand=True)
        vsb_f = ttk.Scrollbar(frame_sub, orient="vertical", command=self.tree_folders.yview)
        vsb_f.pack(side="right", fill="y")
        self.tree_folders.configure(yscrollcommand=vsb_f.set)
        self.tree_folders.bind("<ButtonRelease-1>", self.on_exc_click)
        
        frame_ext = tk.LabelFrame(pane, text="File Extensions")
        pane.add(frame_ext, stretch="always")
        self.tree_exts = ttk.Treeview(frame_ext, show="tree")
        self.tree_exts.pack(side="left", fill="both", expand=True)
        vsb_e = ttk.Scrollbar(frame_ext, orient="vertical", command=self.tree_exts.yview)
        vsb_e.pack(side="right", fill="y")
        self.tree_exts.configure(yscrollcommand=vsb_e.set)
        self.tree_exts.bind("<ButtonRelease-1>", self.on_exc_click)
        
        exc_bot = tk.Frame(self.tab_exclusions)
        exc_bot.pack(fill="x", padx=10, pady=5)
        tk.Button(exc_bot, text="Save Exclusions", command=self.save_exclusions, bg="lightgreen", font=("Arial", 10, "bold")).pack(side="right", padx=5)
        tk.Button(exc_bot, text="Clear Exclusions", command=self.clear_exclusions, bg="#ffdddd", font=("Arial", 10)).pack(side="right", padx=5)
        
        # --- TAB 1: DASHBOARD ---
        frame_paths = tk.LabelFrame(self.tab_main, text="1. Setup Paths & Scan")
        frame_paths.pack(fill="x", padx=10, pady=5)
        
        # We need a frame inside frame_paths to organize the paths on the left, and the scan button on the right
        path_left = tk.Frame(frame_paths)
        path_left.pack(side="left", fill="x", expand=True)
        path_right = tk.Frame(frame_paths)
        path_right.pack(side="right", padx=10, pady=5)
        
        self.src_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.dat_var = tk.StringVar(value=os.path.join(self.app_dir, "DATPACK"))
        
        self.add_path_row(path_left, "Source ROMs:", self.src_var)
        self.out_row = self.add_path_row(path_left, "Output Folder:", self.out_var)
        self.add_path_row(path_left, "DATPACK Folder:", self.dat_var)
        self.scan_subfolders_var = tk.BooleanVar(value=False)
        tk.Checkbutton(path_left, text="Scan Subfolders (Recursively process all child directories)", variable=self.scan_subfolders_var).pack(anchor="w", padx=10, pady=2)
        
        # Move Scan button here
        tk.Button(path_right, text="SCAN\n(Dry Run)", command=self.start_scan, bg="lightblue", font=("Arial", 12, "bold"), height=4, width=15).pack(fill="both", expand=True)
        
        frame_preview = tk.LabelFrame(self.tab_main, text="2. Master Preview (Click to select row, click again to open Dropdown)")
        frame_preview.pack(fill="both", expand=True, padx=10, pady=5)
        
        slider_frame = tk.Frame(frame_preview)
        slider_frame.pack(fill="x", pady=5)
        search_frame = tk.Frame(frame_preview)
        search_frame.pack(fill="x", pady=2)
        tk.Label(search_frame, text="Global Omni-Filter (Search ANY column):").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(search_frame, text="Export Audit CSV", bg="#d9edf7", command=self.export_audit_csv).pack(side="left", padx=5)
        search_entry.bind("<KeyRelease>", self.refresh_preview)
        tk.Label(slider_frame, text="Fuzzy Match Confidence Threshold:").pack(side="left")
        self.slider_var = tk.IntVar(value=90)
        self.slider = tk.Scale(slider_frame, from_=1, to=100, orient="horizontal", variable=self.slider_var, command=self.refresh_preview)
        self.slider.pack(side="left", fill="x", expand=True, padx=10)
        
        columns = ("Action", "Status", "Original", "Proposed Name", "Confidence")
        self.tree = ttk.Treeview(frame_preview, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_treeview(c, False))
        self.tree.heading("Action", text="Action (Dropdown)", command=lambda: self.sort_treeview("Action", False))
        self.tree.heading("Proposed Name", text="Proposed Name (Dropdown)", command=lambda: self.sort_treeview("Proposed Name", False))
            
        self.tree.column("Action", width=140)
        self.tree.column("Status", width=140)
        self.tree.column("Original", width=250)
        self.tree.column("Proposed Name", width=250)
        self.tree.column("Confidence", width=100)
        def on_yscroll(*args):
            self.destroy_active_cb()
            self.scrollbar.set(*args)
            
        self.scrollbar = ttk.Scrollbar(frame_preview, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=on_yscroll)
        self.scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        
        self.tree.tag_configure("override", foreground="black", background="lightblue")
        self.tree.tag_configure("hash", foreground="darkgreen")
        self.tree.tag_configure("fuzzy", foreground="darkgoldenrod")
        self.tree.tag_configure("duplicate", foreground="darkorange")
        self.tree.tag_configure("reject", foreground="firebrick")
        
        self.tree.bind("<Button-1>", self.on_tree_press)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_release)
        self.tree.bind("<MouseWheel>", self.destroy_active_cb)
        
        # --- TAB 2: SETTINGS & ENGINE ---
        frame_filters = tk.LabelFrame(self.tab_settings, text="List & Output Filters")
        frame_filters.pack(fill="x", padx=10, pady=10)
        
        self.inplace_var = tk.BooleanVar()
        tk.Checkbutton(frame_filters, text="Overwrite Source Files", variable=self.inplace_var, command=lambda: [self.toggle_inplace(), self.refresh_preview()]).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.copy_rejects_var = tk.BooleanVar()
        tk.Checkbutton(frame_filters, text="Transfer 'Rejects' (Keeping Original Name)", variable=self.copy_rejects_var, command=self.refresh_preview).grid(row=0, column=1, sticky="w", padx=10, pady=5)
        
        self.hide_ignored_var = tk.BooleanVar()
        tk.Checkbutton(frame_filters, text="Hide 'Skipped' files from List", variable=self.hide_ignored_var, command=self.refresh_preview).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.hide_hash_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_filters, text="Hide '100% Hash' files from List", variable=self.hide_hash_var, command=self.refresh_preview).grid(row=1, column=1, sticky="w", padx=10, pady=5)
        
        self.dup_var = tk.StringVar(value="append")
        tk.Radiobutton(frame_filters, text="Keep Duplicates (Append Digit)", variable=self.dup_var, value="append", command=self.refresh_preview).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        tk.Radiobutton(frame_filters, text="Keep One (Skip Other Duplicates)", variable=self.dup_var, value="ignore", command=self.refresh_preview).grid(row=2, column=1, sticky="w", padx=10, pady=5)
        
        self.hide_low_conf_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_filters, text="Hide items below Confidence Threshold", variable=self.hide_low_conf_var, command=self.refresh_preview).grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        
        frame_engine = tk.LabelFrame(self.tab_settings, text="Ghost Math Engine Preferences")
        frame_engine.pack(fill="x", padx=10, pady=10)
        
        self.strip_num_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame_engine, text="Strip Number Prefixes", variable=self.strip_num_var, command=self.on_smart_setting_change).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.prefer_base_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame_engine, text="Prefer Base Versions", variable=self.prefer_base_var, command=self.on_smart_setting_change).grid(row=0, column=1, sticky="w", padx=10, pady=5)
        
        frame_reg = tk.Frame(frame_engine)
        frame_reg.grid(row=1, column=0, sticky="w", padx=10, pady=5)
        tk.Label(frame_reg, text="Region:").pack(side="left")
        self.region_var = tk.StringVar(value="USA / English")
        cb_reg = ttk.Combobox(frame_reg, textvariable=self.region_var, values=["USA / English", "Europe", "Japan", "World", "None (Raw Math)"], state="readonly", width=15)
        cb_reg.pack(side="left", padx=5)
        cb_reg.bind("<<ComboboxSelected>>", self.on_smart_setting_change)
        
        frame_n = tk.Frame(frame_engine)
        frame_n.grid(row=1, column=1, sticky="w", padx=10, pady=5)
        tk.Label(frame_n, text="Max Dropdown Suggestions (Near Misses):").pack(side="left")
        self.n_var = tk.IntVar(value=4)
        spin = tk.Spinbox(frame_n, from_=1, to=50, textvariable=self.n_var, width=5, command=self.on_smart_setting_change)
        spin.pack(side="left", padx=5)
        spin.bind("<Return>", self.on_smart_setting_change)
        
        self.debug_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_engine, text="Debug Mode (Log Errors)", variable=self.debug_var).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        
        # --- GLOBAL UI (Outside Notebook) ---
        frame_exec = tk.Frame(self.root)
        frame_exec.pack(fill="x", padx=10, pady=5)
        
        self.pause_btn = tk.Button(frame_exec, text="Pause", command=self.toggle_pause, width=10)
        self.pause_btn.pack(side="left", padx=5)
        self.cancel_btn = tk.Button(frame_exec, text="Cancel", command=self.do_cancel, width=10, fg="red")
        self.cancel_btn.pack(side="left", padx=5)
        
        self.prog_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(frame_exec, variable=self.prog_var, maximum=100)
        self.progress.pack(side="left", fill="x", expand=True, padx=10)
        
        self.items_var = tk.StringVar(value="Items Remaining: --/--")
        tk.Label(frame_exec, textvariable=self.items_var, font=("Arial", 9, "bold")).pack(side="left", padx=5)

        self.eta_var = tk.StringVar(value="ETA: --:--")
        tk.Label(frame_exec, textvariable=self.eta_var, width=14, font=("Arial", 9, "bold")).pack(side="left", padx=5)
        
        tk.Button(frame_exec, text="EXECUTE", command=self.start_execute, bg="lightgreen", font=("Arial", 10, "bold")).pack(side="right", padx=5)
        
        self.log_text = tk.Text(self.root, height=8, state="disabled")
        self.log_text.pack(fill="x", padx=10, pady=5)


    def check_excluded(self, rel_dir, ext):
        if ext.lower() in self.excluded_exts: return True
        for ef in self.excluded_folders:
            if rel_dir == ef or rel_dir.startswith(ef + os.sep) or rel_dir.startswith(ef + "/"):
                return True
        return False

    def populate_exclusions(self):
        src = self.src_var.get()
        if not os.path.isdir(src):
            messagebox.showerror("Error", "Please select a valid Source ROMs folder first.")
            return
        self.tree_folders.delete(*self.tree_folders.get_children())
        self.tree_exts.delete(*self.tree_exts.get_children())
        all_exts = set()
        nodes = {"": ""}
        for root_dir, dirs, files in os.walk(src):
            rel_dir = os.path.relpath(root_dir, src)
            if rel_dir == '.': rel_dir = ""
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext: all_exts.add(ext)
            for d in sorted(dirs):
                d_rel = os.path.join(rel_dir, d) if rel_dir else d
                parent_node = nodes.get(rel_dir, "")
                state = "☑ " if d_rel in self.excluded_folders else "☐ "
                node_id = self.tree_folders.insert(parent_node, "end", text=f"{state}{d}", values=(d_rel,))
                nodes[d_rel] = node_id
        for ext in sorted(all_exts):
            state = "☑ " if ext in self.excluded_exts else "☐ "
            self.tree_exts.insert("", "end", text=f"{state}{ext}", values=(ext,))
        messagebox.showinfo("Scan Complete", "Directory indexed! You can now check items to exclude them.")

    def set_tree_open(self, tree, state, node=""):
        for child in tree.get_children(node):
            tree.item(child, open=state)
            self.set_tree_open(tree, state, child)

    def on_exc_click(self, event):
        tree = event.widget
        # Prevent the checkbox toggle if they just clicked the expand/collapse arrow (+/-)
        if "indicator" in tree.identify_element(event.x, event.y):
            return
            
        item = tree.identify_row(event.y)
        if not item: return
        text = tree.item(item, "text")
        if text.startswith("☐ "):
            tree.item(item, text="☑ " + text[2:])
            if tree == self.tree_folders: self.toggle_children(tree, item, "☑ ")
        elif text.startswith("☑ "):
            tree.item(item, text="☐ " + text[2:])
            if tree == self.tree_folders: self.toggle_children(tree, item, "☐ ")

    def toggle_children(self, tree, node, state):
        for child in tree.get_children(node):
            text = tree.item(child, "text")
            tree.item(child, text=state + text[2:])
            self.toggle_children(tree, child, state)

    def has_unsaved_exclusions(self):
        current_exts = set()
        for item in self.tree_exts.get_children():
            if self.tree_exts.item(item, "text").startswith("☑ "):
                current_exts.add(self.tree_exts.item(item, "values")[0])
        if current_exts != self.excluded_exts:
            return True
            
        current_folders = set()
        def collect_folders(node=""):
            for child in self.tree_folders.get_children(node):
                if self.tree_folders.item(child, "text").startswith("☑ "):
                    current_folders.add(self.tree_folders.item(child, "values")[0])
                collect_folders(child)
        collect_folders()
        if current_folders != self.excluded_folders:
            return True
            
        return False

    def revert_exclusion_trees(self):
        for item in self.tree_exts.get_children():
            ext = self.tree_exts.item(item, "values")[0]
            state = "☑ " if ext in self.excluded_exts else "☐ "
            self.tree_exts.item(item, text=f"{state}{ext}")
            
        def revert_folders(node=""):
            for child in self.tree_folders.get_children(node):
                f_rel = self.tree_folders.item(child, "values")[0]
                d_name = os.path.basename(f_rel) if f_rel else ""
                state = "☑ " if f_rel in self.excluded_folders else "☐ "
                self.tree_folders.item(child, text=f"{state}{d_name}")
                revert_folders(child)
        revert_folders()

    def on_tab_changed(self, event):
        if getattr(self, 'switching_tabs', False):
            return
            
        new_tab = self.notebook.index("current")
        try: exc_tab_idx = self.notebook.index(self.tab_exclusions)
        except: exc_tab_idx = 2
        
        # If user is navigating away from Exclusions tab
        if getattr(self, 'current_tab', 0) == exc_tab_idx and new_tab != exc_tab_idx:
            if self.has_unsaved_exclusions():
                ans = messagebox.askyesnocancel(
                    "Unsaved Exclusions",
                    "You have unsaved changes in the Exclusions tab.\n\n"
                    "Would you like to save them before leaving?\n\n"
                    "• Yes: Save changes and proceed\n"
                    "• No: Discard changes and proceed\n"
                    "• Cancel: Return to Exclusions tab"
                )
                if ans is True:
                    self.save_exclusions(show_feedback=False)
                    self.current_tab = new_tab
                elif ans is False:
                    self.revert_exclusion_trees()
                    self.current_tab = new_tab
                else:
                    self.switching_tabs = True
                    self.notebook.select(self.tab_exclusions)
                    self.switching_tabs = False
                    return
            else:
                self.current_tab = new_tab
        else:
            self.current_tab = new_tab

    def save_exclusions(self, show_feedback=True):
        self.excluded_exts = set()
        self.excluded_folders = set()
        for item in self.tree_exts.get_children():
            if self.tree_exts.item(item, "text").startswith("☑ "):
                self.excluded_exts.add(self.tree_exts.item(item, "values")[0])
        def collect_folders(node=""):
            for child in self.tree_folders.get_children(node):
                if self.tree_folders.item(child, "text").startswith("☑ "):
                    self.excluded_folders.add(self.tree_folders.item(child, "values")[0])
                collect_folders(child)
        collect_folders()
        
        self.log(f"Saved {len(self.excluded_folders)} folder exclusion(s) and {len(self.excluded_exts)} extension exclusion(s).")
        
        if self.is_scanning:
            self.pause_btn.config(text="Resume")
            self.is_paused = True
            msg = "A scan is currently running.\n\nWould you like to pause the scan, update the math for the items scanned so far with these exclusions, and then Resume?"
            if messagebox.askyesno("Recalculate", msg):
                self.update_math_engine()
                threading.Thread(target=self.recalc_thread, args=(True,), daemon=True).start()
            else:
                self.is_paused = False
                self.pause_btn.config(text="Pause")
        elif len(self.scan_results) > 0:
            if messagebox.askyesno("Recalculate", "Would you like to apply these exclusions to the current preview?"):
                self.update_math_engine()
                threading.Thread(target=self.recalc_thread, args=(False,), daemon=True).start()
        else:
            if show_feedback:
                messagebox.showinfo("Exclusions Saved", f"Successfully saved {len(self.excluded_folders)} folder exclusion(s) and {len(self.excluded_exts)} extension exclusion(s).")

    def clear_exclusions(self):
        if not self.excluded_folders and not self.excluded_exts and not self.has_unsaved_exclusions():
            messagebox.showinfo("Clear Exclusions", "There are no exclusions to clear.")
            return

        if not messagebox.askyesno("Clear Exclusions", "Are you sure you want to clear all exclusions and start fresh?"):
            return

        for item in self.tree_exts.get_children():
            ext = self.tree_exts.item(item, "values")[0]
            self.tree_exts.item(item, text=f"☐ {ext}")

        def uncheck_folders(node=""):
            for child in self.tree_folders.get_children(node):
                f_rel = self.tree_folders.item(child, "values")[0]
                d_name = os.path.basename(f_rel) if f_rel else ""
                self.tree_folders.item(child, text=f"☐ {d_name}")
                uncheck_folders(child)
        uncheck_folders()

        self.save_exclusions(show_feedback=False)
        self.log("All exclusions cleared.")
        if len(self.scan_results) == 0 and not self.is_scanning:
            messagebox.showinfo("Exclusions Cleared", "All exclusions have been cleared.")

    def destroy_active_cb(self, event=None):
        if getattr(self, 'active_cb', None):
            try:
                self.active_cb.place_forget()
                self.active_cb.destroy()
            except Exception as e:
                self.log_error("GUI Error (Destroying Combobox)", e)
            self.active_cb = None

    def on_tree_press(self, event):
        self.destroy_active_cb()
        self.destroy_active_cb()
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.was_selected = (row_id in self.tree.selection())
        else:
            self.was_selected = False

    def on_tree_release(self, event):
        self.destroy_active_cb()
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id: return
        
        if not getattr(self, 'was_selected', False):
            return
            
        if col_id not in ['#1', '#4']:
            return
            
        bbox = self.tree.bbox(row_id, col_id)
        if not bbox: return
        x, y, width, height = bbox
        
        values = list(self.tree.item(row_id, "values"))
        orig_name = values[2]
        
        if col_id == '#1':
            current_action = values[0]
            cb = ttk.Combobox(self.tree, values=["Rename", "Skip File (Leave in Source)", "Keep Original Name"], state="readonly")
            cb.place(x=x, y=y, width=width, height=height)
            cb.set(current_action)
            self.active_cb = cb
            
            def on_select(e, c=cb):
                new_action = c.get()
                try: c.place_forget(); c.destroy()
                except Exception as ex: self.log_error("GUI Error (on_select)", ex)
                if getattr(self, 'active_cb', None) == c: self.active_cb = None
                
                if new_action != current_action:
                    self.overrides[orig_name] = new_action
                    self.refresh_preview()
                    
            cb.bind("<<ComboboxSelected>>", on_select)
            
            cb.bind("<Escape>", self.destroy_active_cb)
            cb.focus_set()
            cb.event_generate('<Down>')
            
        elif col_id == '#4':
            res = next((r for r in self.scan_results if r["original"] == orig_name), None)
            if not res or res["is_hash"] or not res.get("alternatives"):
                return
                
            options = []
            for alt_name, alt_conf in res["alternatives"]:
                options.append(f"{alt_name} [{alt_conf}%]")
                
            if not options: return
                
            current_val = values[3]
            cb = ttk.Combobox(self.tree, values=options, state="readonly")
            cb.place(x=x, y=y, width=width, height=height)
            cb.set(current_val)
            self.active_cb = cb
            
            def on_alt_select(e, c=cb):
                selection = c.get()
                try: c.place_forget(); c.destroy()
                except Exception as ex: self.log_error("GUI Error (on_alt_select)", ex)
                if getattr(self, 'active_cb', None) == c: self.active_cb = None
                
                import re
                match = re.search(r' \[(\d+)%\]$', selection)
                if match:
                    new_conf = int(match.group(1))
                    new_name = selection[:match.start()]
                else:
                    new_name = selection
                    new_conf = res["confidence"]
                    
                self.name_overrides[orig_name] = (new_name, new_conf)
                self.refresh_preview()
                
            cb.bind("<<ComboboxSelected>>", on_alt_select)
            
            cb.bind("<Escape>", self.destroy_active_cb)
            cb.focus_set()
            cb.event_generate('<Down>')

    def add_path_row(self, parent, label, var):
        frame = tk.Frame(parent)
        frame.pack(fill="x", pady=2)
        tk.Label(frame, text=label, width=15, anchor="e").pack(side="left")
        tk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(frame, text="Browse", command=lambda: var.set(filedialog.askdirectory())).pack(side="left")
        return frame
        
    def toggle_inplace(self):
        if self.inplace_var.get():
            messagebox.showwarning("Warning", "'Overwrite Source Files' will modify your files directly in the original Source folder! Make sure you have backups.")
            self.out_var.set("")
            for child in self.out_row.winfo_children():
                child.configure(state="disabled")
        else:
            for child in self.out_row.winfo_children():
                child.configure(state="normal")

    def log(self, msg):
        self.log_queue.append(msg)

    def log_error(self, context, exception=None):
        if getattr(self, 'debug_var', None) and self.debug_var.get():
            import traceback
            if exception:
                self.log(f"[DEBUG] {context}: {exception}")
                for line in traceback.format_exc().split('\n'):
                    if line.strip(): self.log(f"[DEBUG] {line}")
            else:
                self.log(f"[DEBUG] {context}")
        
    def flush_logs(self):
        if self.log_queue:
            self.log_text.config(state="normal")
            self.log_text.insert("end", "\n".join(self.log_queue) + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
            self.log_queue.clear()
        self.root.after(100, self.flush_logs)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_btn.config(text="Resume" if self.is_paused else "Pause")
        if self.is_paused:
            self.pending_pause_msg = "Job Paused..."
        else:
            self.log("Job Resumed...")

    def do_cancel(self):
        if messagebox.askyesno("Cancel", "Are you sure you want to cancel?"):
            self.cancel_flag = True
            self.log("Canceling job... waiting for current file to finish.")

    def update_math_engine(self):
        is_raw = (self.region_var.get() == "None (Raw Math)")
        strip_n = self.strip_num_var.get()
        self.engine.update_math(is_raw, strip_n, self.log)

    def on_smart_setting_change(self, event=None):
        if not self.scan_results and not self.is_scanning:
            return
            
        was_scanning = self.is_scanning
        
        if was_scanning:
            self.is_paused = True
            self.pause_btn.config(text="Resume")
            self.pending_pause_msg = "Job Paused for Recalculation..."
            msg = "A scan is currently running.\n\nWould you like to pause the scan, update the math for the items scanned so far, and then Resume?"
        else:
            msg = "Would you like to fast-recalculate the Fuzzy Math with your new settings?\n\n(This skips the hard drive and takes only seconds)"
            
        if messagebox.askyesno("Recalculate", msg):
            self.update_math_engine()
            threading.Thread(target=self.recalc_thread, args=(was_scanning,), daemon=True).start()



    def break_ties_list(self, candidates, orig_raw):
        if len(candidates) == 1: return candidates
        region_setting = self.region_var.get()
        scores = [(c, difflib.SequenceMatcher(None, orig_raw, c).ratio()) for c in candidates]
        scores.sort(key=lambda x: x[1], reverse=True)
        if len(scores) > 1 and (scores[0][1] > scores[1][1] + 0.05): 
            return [x[0] for x in scores]
            
        region_aliases = []
        if region_setting == "USA / English": region_aliases = ["USA", "US", "En", "English", "World"]
        elif region_setting == "Europe": region_aliases = ["Europe", "EU", "En"]
        elif region_setting == "Japan": region_aliases = ["Japan", "JP", "Ja"]
        elif region_setting == "World": region_aliases = ["World", "USA", "En", "Europe"]
            
        preferred = []
        others = []
        for c, _ in scores:
            if region_aliases and any(re.search(r'\b' + a + r'\b', c, re.IGNORECASE) for a in region_aliases):
                preferred.append(c)
            else:
                others.append(c)
                
        if self.prefer_base_var.get():
            preferred.sort(key=len)
            others.sort(key=len)
            
        return preferred + others

    def recalc_thread(self, was_scanning_active):
        try:
            self._recalc_thread_impl(was_scanning_active)
        except Exception as e:
            self.log("Recalculation failed due to a critical error.")
            self.log_error("recalc_thread crashed", e)
            
    def _recalc_thread_impl(self, was_scanning_active):
        self.log("Recalculating fuzzy math in memory...")
        original_eta = self.eta_var.get()
        original_prog = self.prog_var.get()
        original_items = self.items_var.get()
        self.eta_var.set("Recalculating...")
        
        curr_is_raw = self.engine.is_raw_math
        curr_strip_n = self.engine.strip_n
        curr_ghost_db = self.engine.ghost_db
        curr_ghost_list = self.engine.ghost_list
        
        total = len(self.scan_results)
        self.items_var.set(f"Items Remaining: 0/{total:,}" if total > 0 else "Items Remaining: --/--")
        start_time = time.time()
        last_ui = time.time()
        
        for i, res in enumerate(self.scan_results):
            if self.cancel_flag: return
            
            rel_path = res["original"]
            rel_dir = os.path.dirname(rel_path)
            ext = os.path.splitext(rel_path)[1].lower()
            is_excluded_now = self.check_excluded(rel_dir, ext)
            res["is_excluded"] = is_excluded_now
            
            if is_excluded_now:
                res["proposed"] = ""
                res["confidence"] = 0
                res["is_hash"] = False
                res["alternatives"] = []
            elif not res.get("is_hash", False):
                orig_raw = os.path.splitext(os.path.basename(res["original"]))[0]
                try: curr_n = self.n_var.get()
                except: curr_n = 4
                prop, conf, alts = self.engine.find_match(orig_raw, orig_raw, curr_n, self.region_var.get())
                res["proposed"] = prop
                res["confidence"] = conf
                res["alternatives"] = alts
            
            self.prog_var.set(((i + 1) / total) * 100)
            
            curr_time = time.time()
            if curr_time - last_ui > 0.05:
                elapsed = curr_time - start_time
                if elapsed > 0:
                    speed = (i + 1) / elapsed
                    rem_sec = (total - (i + 1)) / speed
                    h, m, s = int(rem_sec // 3600), int((rem_sec % 3600) // 60), int(rem_sec % 60)
                    self.eta_var.set(f"Recalc ETA: {h}H {m}M {s}S" if h > 0 else f"Recalc ETA: {m}M {s}S")
                self.items_var.set(f"Items Remaining: {i + 1:,}/{total:,}")
                self.root.update_idletasks()
                last_ui = curr_time
                        
        self.refresh_preview()
        
        if was_scanning_active:
            self.prog_var.set(original_prog)
            self.eta_var.set(original_eta)
            self.items_var.set(original_items)
            self.log("Recalculation complete! Click 'Resume' to continue scanning.")
        else:
            self.prog_var.set(0)
            self.eta_var.set("ETA: --:--")
            self.items_var.set(f"Items Remaining: {total:,}/{total:,}" if total > 0 else "Items Remaining: --/--")
            self.log("Recalculation complete!")

    def start_scan(self):
        if not self.src_var.get():
            messagebox.showerror("Error", "Please select a source folder.")
            return
        self.is_paused = False
        self.cancel_flag = False
        self.overrides.clear()
        self.name_overrides.clear()
        self.pause_btn.config(text="Pause")
        threading.Thread(target=self.scan_thread, daemon=True).start()

    def scan_thread(self):
        try:
            self._scan_thread_impl()
        except Exception as e:
            self.log("Scan failed due to a critical error.")
            self.log_error("scan_thread crashed", e)
        finally:
            self.is_scanning = False
            
    def _scan_thread_impl(self):
        self.is_scanning = True
        self.scan_results.clear()
        self.virtual_plan.clear()
        for item in self.tree.get_children(): self.tree.delete(item)
            
        self.seen_names = {}
        self.prog_var.set(0)
        self.eta_var.set("ETA: --:--")
        self.items_var.set("Items Remaining: --/--")
        
        if not self.engine.load_dats(self.dat_var.get(), self.log): 
            self.is_scanning = False
            return
        
        src = self.src_var.get()
        files = []
        if self.scan_subfolders_var.get():
            for root_dir, _, filenames in os.walk(src):
                for fname in filenames:
                    rel_dir = os.path.relpath(root_dir, src)
                    if rel_dir == '.': rel_dir = ""
                    files.append((rel_dir, fname))
        else:
            for fname in os.listdir(src):
                if os.path.isfile(os.path.join(src, fname)):
                    files.append(("", fname))
        total = len(files)
        self.items_var.set(f"Items Remaining: 0/{total:,}" if total > 0 else "Items Remaining: --/--")
        
        self.update_math_engine()
        start_time = time.time()
        last_ui = time.time()
        
        for i, (rel_dir, f) in enumerate(files):
            if self.is_paused and getattr(self, 'pending_pause_msg', ""):
                self.log(self.pending_pause_msg)
                self.pending_pause_msg = ""
            while self.is_paused and not self.cancel_flag:
                time.sleep(0.1)
                
            if self.cancel_flag:
                self.prog_var.set(0)
                self.eta_var.set("ETA: --:--")
                self.items_var.set("Items Remaining: --/--")
                self.log("Scan cancelled.")
                self.is_scanning = False
                self.refresh_preview()
                return
            
            curr_is_raw = self.engine.is_raw_math
            curr_strip_n = self.engine.strip_n
            curr_ghost_db = self.engine.ghost_db
            curr_ghost_list = self.engine.ghost_list
            
            filepath = os.path.join(src, rel_dir, f) if rel_dir else os.path.join(src, f)
            rel_path = os.path.join(rel_dir, f) if rel_dir else f
            ext = os.path.splitext(f)[1].lower()
            
            is_excluded = self.check_excluded(rel_dir, ext)
            
            matched_name = ""
            confidence = 0
            is_zip = False
            is_hash_hit = False
            alts = []
            
            if not is_excluded:
                if ext in ['.zip', '.7z']:
                    is_zip = True
                    if ext == '.zip':
                        try:
                            import zipfile
                            with zipfile.ZipFile(filepath, 'r') as zf:
                                for info in zf.infolist():
                                    crc = "%08X".lower() % (info.CRC & 0xFFFFFFFF)
                                    if crc == "00000000": continue
                                    if crc in self.engine.hash_db:
                                        matched_name = self.engine.hash_db[crc]
                                        confidence = 100
                                        is_hash_hit = True
                                        break
                        except: pass
                else:
                    try:
                        crc = file_ops.calc_crc(filepath)
                        if crc in self.engine.hash_db:
                            matched_name = self.engine.hash_db[crc]
                            confidence = 100
                            is_hash_hit = True
                    except: pass
                
                if not matched_name:
                    clean_name = os.path.splitext(f)[0]
                    try: curr_n = self.n_var.get()
                    except: curr_n = 4
                    matched_name, confidence, alts = self.engine.find_match(clean_name, clean_name, curr_n, self.region_var.get())
            
            res = {
                "original": rel_path,
                "proposed": matched_name,
                "confidence": confidence,
                "is_zip": is_zip,
                "is_hash": is_hash_hit,
                "alternatives": alts,
                "is_excluded": is_excluded
            }
            self.scan_results.append(res)
            self._add_to_preview(res, self.slider_var.get(), auto_scroll=False)
            
            # Removed the modulus throttle: log every file!
            self.log(f"Scanned {f} -> {matched_name} ({confidence}%)")
            
            self.prog_var.set(((i + 1) / total) * 100)
            
            curr_time = time.time()
            if curr_time - last_ui > 0.05:
                elapsed = curr_time - start_time
                if elapsed > 0:
                    speed = (i + 1) / elapsed
                    rem_sec = (total - (i + 1)) / speed
                    h, m, s = int(rem_sec // 3600), int((rem_sec % 3600) // 60), int(rem_sec % 60)
                    self.eta_var.set(f"ETA: {h}H {m}M {s}S" if h > 0 else f"ETA: {m}M {s}S")
                self.items_var.set(f"Items Remaining: {i + 1:,}/{total:,}")
                self.root.update_idletasks()
                last_ui = curr_time
            
        self.prog_var.set(0)
        self.eta_var.set("ETA: --:--")
        self.items_var.set(f"Items Remaining: {total:,}/{total:,}" if total > 0 else "Items Remaining: --/--")
        self.log("Scan complete!")
        self.is_scanning = False

    def _write_csv_log(self, job_type):
        import csv
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        is_receipt = (job_type == "Receipt")
        subfolder = "Job Receipts" if is_receipt else "Audits"
        prefix = "Job_Receipt" if is_receipt else "Audit"
        
        target_dir = os.path.join(self.app_dir, "Logs", subfolder)
        os.makedirs(target_dir, exist_ok=True)
        filename = os.path.join(target_dir, f"{prefix}_{ts}.csv")
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([f"# ROMRename {job_type} Log"])
            writer.writerow([f"# Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
            writer.writerow([f"# Source: {self.src_var.get()}"])
            writer.writerow([f"# Output: {self.out_var.get()}"])
            writer.writerow(["# --- SETTINGS ---"])
            writer.writerow([f"# Threshold: {self.slider_var.get()} | Region: {self.region_var.get()} | Strip Nums: {self.strip_num_var.get()} | Base: {self.prefer_base_var.get()}"])
            writer.writerow([f"# Duplicates: {self.dup_var.get()} | Overwrite: {self.inplace_var.get()} | Transfer Rejects: {self.copy_rejects_var.get()}"])
            writer.writerow([f"# Hide Skipped: {self.hide_ignored_var.get()} | Hide 100%: {self.hide_hash_var.get()} | Hide Below Thresh: {self.hide_low_conf_var.get()}"])
            writer.writerow(["# ---------------------------------------------------------"])
            
            writer.writerow(["Original File", "Proposed Name", "Confidence", "Match Type", "Action Taken", "Alternatives"])
            
            vp_dict = {v[0]: v for v in self.virtual_plan}
            
            for res in self.scan_results:
                orig = res.get("original", "")
                prop = res.get("proposed", "")
                conf = res.get("confidence", 0)
                is_hash = res.get("is_hash", False)
                is_exc = res.get("is_excluded", False)
                
                match_type = "Excluded" if is_exc else ("Hash Hit" if is_hash else "Fuzzy")
                alts = res.get("alternatives", [])
                alts_str = ", ".join([f"{a[0]} ({a[1]}%)" for a in alts])
                
                if orig in self.name_overrides:
                    prop = self.name_overrides[orig]
                    match_type = "Manual Override"
                    conf = 100
                
                action = "Skipped"
                if orig in vp_dict:
                    action = vp_dict[orig][2]
                elif is_exc:
                    action = "Skipped (Excluded)"
                elif conf < self.slider_var.get():
                    action = "Skipped (Below Threshold)"
                    
                writer.writerow([orig, prop, f"{conf}%", match_type, action, alts_str])
        
        return filename

    def export_audit_csv(self):
        if not self.scan_results:
            from tkinter import messagebox
            messagebox.showinfo("Export Audit", "No scan results to export! Run a scan first.")
            return
        filename = self._write_csv_log("Audit")
        from tkinter import messagebox
        messagebox.showinfo("Export Complete", f"Audit CSV successfully exported to:\n{filename}")

    def _add_to_preview(self, res, threshold, auto_scroll=True):
        def passes_search(*fields):
            s = getattr(self, 'search_var', None)
            if not s or not s.get().strip(): return True
            import unicodedata
            def strip_a(text): return ''.join(c for c in unicodedata.normalize('NFKD', str(text)) if unicodedata.category(c) != 'Mn')
            s_clean = strip_a(s.get().lower().strip())
            for field in fields:
                if s_clean in strip_a(str(field).lower()):
                    return True
            return False
        orig = res["original"]
        prop = res["proposed"]
        conf = res["confidence"]
        ext = os.path.splitext(orig)[1] if not res["is_zip"] else ".zip"
        
        forced_action = self.overrides.get(orig)
        forced_name_tuple = self.name_overrides.get(orig)
        
        if forced_name_tuple:
            prop = forced_name_tuple[0]
            conf = forced_name_tuple[1]
        
        will_rename = False
        if forced_action == "Rename":
            will_rename = True
        elif forced_action in ["Skip File (Leave in Source)", "Keep Original Name"]:
            will_rename = False
        else:
            will_rename = (conf >= threshold and conf > 0)
            
        row_tag = ""
        item_id = None
        
        if will_rename:
            final_name = prop + ext
            action = forced_action if forced_action else "Rename"
            
            if conf == 100 and not forced_name_tuple:
                status = "\u25CF 100% Hash"
                row_tag = "hash"
            else:
                if not forced_action and not forced_name_tuple:
                    status = "\u25CF Fuzzy"
                    row_tag = "fuzzy"
                else:
                    status = "\u25CF Manual Override"
                    row_tag = "override"
            
            if final_name in self.seen_names:
                if self.dup_var.get() == "ignore":
                    action = "Skip File (Duplicate)"
                    status = "\u25CF Duplicate"
                    row_tag = "duplicate"
                    final_name = "None"
                else:
                    self.seen_names[final_name] += 1
                    final_name = f"{prop} ({self.seen_names[final_name]}){ext}"
                    if not forced_action: action = "Rename (Appended)"
            else:
                self.seen_names[final_name] = 0
                
            tags = ("override",) if (forced_action or forced_name_tuple) else (row_tag,)
            
            hide_visually = False
            if self.hide_hash_var.get() and conf == 100 and not forced_name_tuple:
                hide_visually = True
            if not passes_search(action, status, orig, final_name, f"{conf}%"):
                hide_visually = True
                
            item_id = None
            if not hide_visually:
                item_id = self.tree.insert("", "end", values=(action, status, orig, final_name, f"{conf}%"), tags=tags)
                
            if "Duplicate" not in action:
                self.virtual_plan.append((orig, final_name, action, res["is_zip"]))
        else:
            action = forced_action if forced_action else "Skip File (Leave in Source)"
            if not forced_action and not forced_name_tuple:
                status = "\u25CF Rejected"
                row_tag = "reject"
            else:
                status = "\u25CF Manual Override"
                row_tag = "override"
            
            if action == "Skip File (Leave in Source)" and self.copy_rejects_var.get() and not self.inplace_var.get():
                action = "Keep Original Name"
                
            proposed_display = (prop + ext) if prop != "Unknown" else "Unknown"
            
            hide_visually = False
            if action == "Skip File (Leave in Source)" and self.hide_ignored_var.get():
                hide_visually = True
            if self.hide_low_conf_var.get() and not forced_action and not forced_name_tuple:
                # Anything in this else block without a forced action is below threshold!
                hide_visually = True
            if not passes_search(action, status, orig, proposed_display, f"{conf}%"):
                hide_visually = True
                
            if not hide_visually:
                tags = ("override",) if (forced_action or forced_name_tuple) else (row_tag,)
                item_id = self.tree.insert("", "end", values=(action, status, orig, proposed_display, f"{conf}%"), tags=tags)
                
            if action == "Keep Original Name":
                self.virtual_plan.append((orig, orig, action, res["is_zip"]))
                
        if item_id and auto_scroll:
            self.tree.see(item_id)

    def refresh_preview(self, event=None):
        # Save current scroll position
        current_scroll = self.tree.yview()

        self.destroy_active_cb()
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        threshold = self.slider_var.get()
        self.virtual_plan.clear()
        self.seen_names = {}
        
        for res in self.scan_results:
            self._add_to_preview(res, threshold, auto_scroll=False)
            
        # Restore scroll position
        self.tree.yview_moveto(current_scroll[0])


    def sort_treeview(self, col, reverse):
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        if col == "Confidence":
            def parse_conf(x):
                try: return int(x.strip('%'))
                except: return -1
            l.sort(key=lambda t: parse_conf(t[0]), reverse=reverse)
        else:
            l.sort(key=lambda t: t[0].lower(), reverse=reverse)
            
        for index, (val, k) in enumerate(l):
            self.tree.move(k, "", index)
            
        self.tree.heading(col, command=lambda: self.sort_treeview(col, not reverse))

    def start_execute(self):
        if not self.virtual_plan:
            messagebox.showinfo("Execute", "Nothing to execute. Run scan first.")
            return
        if not self.inplace_var.get() and not self.out_var.get():
            messagebox.showerror("Error", "Please select an output folder.")
            return
            
        if self.is_scanning:
            if messagebox.askyesno("Scan in Progress", "A scan is currently running or paused.\n\nExecuting now will safely cancel the remainder of the scan and process only the items found so far.\n\nDo you want to proceed?"):
                self.log("Waiting for Scanner to safely finish its last file...")
                self.cancel_flag = True
                self.is_paused = False
                self.pause_btn.config(state="disabled")
                
                def wait_and_exec():
                    waited = 0.0
                    while self.is_scanning and waited < 5.0:
                        time.sleep(0.2)
                        waited += 0.2
                    self.is_scanning = False
                    self.cancel_flag = False
                    self.root.after(0, lambda: self.pause_btn.config(state="normal", text="Pause"))
                    threading.Thread(target=self.exec_thread, daemon=True).start()
                    
                threading.Thread(target=wait_and_exec, daemon=True).start()
            return

        self.is_paused = False
        self.cancel_flag = False
        self.pause_btn.config(text="Pause")
        threading.Thread(target=self.exec_thread, daemon=True).start()

    def exec_thread(self):
        try:
            self._exec_thread_impl()
        except Exception as e:
            self.log("Execution failed due to a critical error.")
            self.log_error("exec_thread crashed", e)
        finally:
            self.is_scanning = False
            self.cancel_flag = False
            self.is_paused = False
            self.root.after(0, lambda: self.pause_btn.config(state="normal", text="Pause"))

    def _exec_thread_impl(self):
        self.is_scanning = True
        src = self.src_var.get()
        out = src if self.inplace_var.get() else self.out_var.get()
        
        total = len(self.virtual_plan)
        self.prog_var.set(0)
        self.eta_var.set("ETA: --:--")
        self.items_var.set(f"Items Remaining: 0/{total:,}" if total > 0 else "Items Remaining: --/--")
        start_time = time.time()
        last_ui = time.time()
        
        for i, (orig, final, action, is_zip) in enumerate(self.virtual_plan):
            if self.is_paused and getattr(self, 'pending_pause_msg', ""):
                self.log(self.pending_pause_msg)
                self.pending_pause_msg = ""
            while self.is_paused and not self.cancel_flag:
                time.sleep(0.1)
            if self.cancel_flag:
                self.items_var.set("Items Remaining: --/--")
                self.log("Execution cancelled.")
                break
                
            src_path = os.path.join(src, orig)
            out_path = os.path.join(out, final)
            
            try:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                if action == "Keep Original Name":
                    file_ops.copy_standard_file(src_path, out_path)
                else:
                    if is_zip:
                        temp_dir = os.path.join(self.app_dir, "TEMP_WORKSPACE")
                        file_ops.process_zip_rename(src_path, out_path, final, temp_dir)
                        if self.inplace_var.get() and orig != final:
                            os.remove(src_path)
                    else:
                        if self.inplace_var.get():
                            os.rename(src_path, out_path)
                        else:
                            file_ops.copy_standard_file(src_path, out_path)
                self.log(f"Processed: {final}")
            except Exception as e:
                self.log(f"Error on {orig}: {e}")
                self.log_error(f"Execution Error on {orig}", e)
                
            if time.time() - last_ui > 0.1:
                self.prog_var.set(((i + 1) / total) * 100)
                elapsed = time.time() - start_time
                if i > 0:
                    rem_sec = (elapsed / i) * (total - i)
                    h, m, s = int(rem_sec // 3600), int((rem_sec % 3600) // 60), int(rem_sec % 60)
                    self.eta_var.set(f"ETA: {h}H {m}M {s}S" if h > 0 else f"ETA: {m}M {s}S")
                self.items_var.set(f"Items Remaining: {i + 1:,}/{total:,}")
                self.root.update_idletasks()
                last_ui = time.time()
                
        self.prog_var.set(0)
        self.eta_var.set("ETA: --:--")
        self.items_var.set(f"Items Remaining: {total:,}/{total:,}" if total > 0 else "Items Remaining: --/--")
        
        receipt_file = self._write_csv_log("Receipt")
        messagebox.showinfo("Job Complete", f"Execution finished successfully.\nReceipt saved to:\n{receipt_file}")
        self.log(f"Job finished. Receipt saved to {receipt_file}")
