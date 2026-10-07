import os
import sqlite3
import tempfile
import unittest

import app as core


class MonthlyActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = core.DB_PATH
        self.original_upload_dir = core.UPLOAD_DIR
        core.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        core.UPLOAD_DIR = self.temp_dir.name
        core.init_db()
        with sqlite3.connect(core.DB_PATH) as db:
            db.executemany(
                """INSERT INTO users
                   (username, password_hash, full_name, role, department)
                   VALUES (?,?,?,?,?)""",
                [
                    ("manager-one", "unused", "Şube Müdürü 1", "manager", "Şube 1"),
                    ("manager-two", "unused", "Şube Müdürü 2", "manager", "Şube 2"),
                ],
            )
        self.manager_one = 2
        self.manager_two = 3
        self.client = core.app.test_client()

    def tearDown(self):
        core.DB_PATH = self.original_db_path
        core.UPLOAD_DIR = self.original_upload_dir
        self.temp_dir.cleanup()

    def login(self, user_id, role):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role
            session["full_name"] = "Test"

    def activity(self, client_id="legacy-1"):
        return {
            "client_id": client_id,
            "unit": "Bilgi Sistemleri",
            "type": "Destek",
            "date": "2026-09-14",
            "status": "Tamamlandı",
            "description": "Açıklama",
        }

    def test_legacy_import_is_idempotent(self):
        self.login(self.manager_one, "manager")
        payload = {"records": [self.activity()]}

        first = self.client.post("/monthly-activities/import", json=payload)
        second = self.client.post("/monthly-activities/import", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json["imported"], 1)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json["duplicates"], 1)
        with sqlite3.connect(core.DB_PATH) as db:
            count = db.execute("SELECT COUNT(*) FROM monthly_activities").fetchone()[0]
        self.assertEqual(count, 1)

    def test_manager_cannot_read_or_change_another_managers_activity(self):
        with sqlite3.connect(core.DB_PATH) as db:
            db.execute(
                """INSERT INTO monthly_activities
                   (owner_id, client_id, unit, activity_type, activity_date, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (self.manager_two, "other", "Bilgi Sistemleri", "Destek", "2026-09-14",
                 "Tamamlandı", "2026-09-14", "2026-09-14"),
            )
            activity_id = db.execute("SELECT id FROM monthly_activities").fetchone()[0]

        self.login(self.manager_one, "manager")
        response = self.client.get("/monthly-activities/data")
        update = self.client.put(
            f"/monthly-activities/activities/{activity_id}",
            json=self.activity("tampering"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["activities"], [])
        self.assertEqual(update.status_code, 403)

    def test_approved_period_rejects_new_activity(self):
        self.login(self.manager_one, "manager")
        approved = self.client.post(
            "/monthly-activities/period",
            json={"month": "2026-09"},
        )
        created = self.client.post(
            "/monthly-activities/activities",
            json=self.activity("blocked"),
        )

        self.assertEqual(approved.status_code, 200)
        self.assertTrue(approved.json["approved"])
        self.assertEqual(created.status_code, 409)

    def test_admin_can_view_all_branch_activities(self):
        with sqlite3.connect(core.DB_PATH) as db:
            for owner_id, client_id in ((self.manager_one, "one"), (self.manager_two, "two")):
                db.execute(
                    """INSERT INTO monthly_activities
                       (owner_id, client_id, unit, activity_type, activity_date, status, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (owner_id, client_id, "Bilgi Sistemleri", "Destek", "2026-09-14",
                     "Tamamlandı", "2026-09-14", "2026-09-14"),
                )

        self.login(1, "admin")
        response = self.client.get("/monthly-activities/data")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["activities"]), 2)

    def test_monthly_module_has_separate_entry_and_report_pages(self):
        self.login(self.manager_one, "manager")
        entry = self.client.get("/monthly-activities/entry")
        report = self.client.get("/monthly-activities/report")

        self.assertEqual(entry.status_code, 200)
        self.assertIn(b"Kayıt Girişi", entry.data)
        self.assertEqual(report.status_code, 200)
        self.assertIn(b"Aylık Rapor", report.data)


if __name__ == "__main__":
    unittest.main()
