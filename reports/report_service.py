from database.connection import Database

class ReportService:
    def __init__(self, db=None):
        self.db = db or Database()

    def get_daily_stats(self, days=90):
        days = max(1, min(int(days), 366))
        with self.db.cursor() as cursor:
            cursor.execute('SELECT DATE(timestamp) day, SUM(action=\'ENTRY\') entries, SUM(action=\'EXIT\') exits, COUNT(*) total FROM access_logs WHERE timestamp >= DATE_SUB(CURDATE(), INTERVAL %s DAY) GROUP BY DATE(timestamp) ORDER BY day DESC', (days,))
            return cursor.fetchall()

    def get_user_stats(self):
        with self.db.cursor() as cursor:
            cursor.execute('SELECT u.id,u.name,u.neptun,COUNT(a.id) total_scans,SUM(a.action=\'ENTRY\') entries,SUM(a.action=\'EXIT\') exits FROM users u LEFT JOIN access_logs a ON a.user_id=u.id GROUP BY u.id,u.name,u.neptun ORDER BY total_scans DESC,u.name')
            return cursor.fetchall()
