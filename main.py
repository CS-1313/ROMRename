import sys
import tkinter as tk
from gui import ROMRenameApp

if __name__ == "__main__":
    if len(sys.argv) > 1:
        from cli import run_cli
        run_cli()
    else:
        root = tk.Tk()
        app = ROMRenameApp(root)
        root.mainloop()
