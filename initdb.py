
import sqlite3
from pathlib import Path
Path("sessions").mkdir(exist_ok=True)

connection = sqlite3.connect("session.db")

cursor = connection.cursor()
cursor.execute("DROP TABLE IF EXISTS session")
cursor.execute("CREATE TABLE session (id TEXT, currentversion TEXT, created_date TEXT, updated_date TEXT, status TEXT)")
cursor.close()
connection.close()  
