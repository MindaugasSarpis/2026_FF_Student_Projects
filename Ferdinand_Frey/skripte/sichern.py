"""Sichert das Projekt per Git: committet alle Änderungen und schiebt sie zu GitHub, falls „origin“ eingerichtet ist.
Was nicht ins Repository gehört (Logs, Feedback), steht in .gitignore. Läuft am Ende von taeglich.py."""
import subprocess
from datetime import datetime

from pfade import BASIS


def git(*args):
    return subprocess.run(["git", *args], cwd=BASIS, capture_output=True, text=True, encoding="utf-8", errors="replace")


git("add", "-A")
if git("diff", "--cached", "--quiet").returncode:
    ergebnis = git("commit", "-m", f"Sicherung {datetime.now():%Y-%m-%d %H:%M}")
    print("Commit:", ergebnis.stdout.strip().splitlines()[0] if ergebnis.returncode == 0 else ergebnis.stderr.strip())
else:
    print("Keine Änderungen.")

if git("remote", "get-url", "origin").returncode == 0:
    ergebnis = git("push", "origin", "HEAD")
    print("Hochgeladen." if ergebnis.returncode == 0 else f"Hochladen fehlgeschlagen: {ergebnis.stderr.strip()}")
else:
    print("Kein GitHub-Repository eingerichtet: nur lokal gesichert.")
