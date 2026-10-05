"""Small fixtures for errors that can look plausible in aggregate metrics."""
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MetricBoundaries(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript((ROOT/'sql/schema.sql').read_text())

    def tearDown(self):
        self.db.close()

    def query(self,name):
        return self.db.execute((ROOT/'sql'/name).read_text()).fetchall()

    def user(self,uid,signup):
        self.db.execute('INSERT INTO users VALUES (?,?,?,?)',(uid,signup,'web','direct'))

    def test_exact_day_and_immature_retention(self):
        self.user(1,'2026-08-31')  # D30 exactly on observation end: eligible.
        self.user(2,'2026-09-01')  # D30 after observation end: excluded.
        self.user(3,'2026-08-31')  # Return on D29 is not D30 retention.
        self.db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?)',[
            (1,1,1,'2026-09-30 10:00:00','view','web','web'),
            (2,2,2,'2026-09-30 10:00:00','view','web','web'),
            (3,3,3,'2026-09-29 10:00:00','view','web','web')])
        rows = self.query('03_retention.sql')
        self.assertIn(('2026-08',30,2,1,.5),rows)
        self.assertFalse(any(cohort=='2026-09' and n==30 for cohort,n,*_ in rows))

    def test_out_of_order_and_cross_session_funnel(self):
        self.user(1,'2026-06-01')
        self.db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?)',[
            (1,1,1,'2026-06-01 10:00:00','view','web','web'),
            (2,1,1,'2026-06-01 09:00:00','add_to_cart','web','web'),
            (3,1,1,'2026-06-01 11:00:00','checkout','web','web'),
            (4,1,1,'2026-06-01 12:00:00','purchase','web','web'),
            (5,1,2,'2026-06-01 13:00:00','add_to_cart','web','web')])
        self.assertEqual([row[2] for row in self.query('01_funnel.sql')],[1,0,0,0])

    def test_repeat_purchase_full_window_and_day_30(self):
        for uid in range(1,4):
            self.user(uid,'2026-06-01')
        self.db.executemany('INSERT INTO orders VALUES (?,?,?,?,?,?)',[
            (1,1,1,'2026-08-31 12:00:00',1000,'paid'),
            (2,1,2,'2026-09-30 12:00:00',1000,'paid'),
            (3,2,3,'2026-09-01 12:00:00',1000,'paid'),
            (4,2,4,'2026-09-02 12:00:00',1000,'paid'),
            (5,3,5,'2026-08-30 12:00:00',1000,'paid'),
            (6,3,6,'2026-09-30 12:00:00',1000,'paid')])
        self.assertEqual(self.query('05_repeat_purchase.sql'),[(2,1,.5)])


if __name__ == '__main__':
    unittest.main()
