import os
import psycopg2


class Database:
    def __init__(self):
        self.conn = psycopg2.connect(os.environ["DATABASE_URL"])

    def close(self):
        self.conn.close()
