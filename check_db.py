import sqlite3
c = sqlite3.connect('insurance_platform.db')
print(c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
