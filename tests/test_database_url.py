import os
import unittest
from unittest.mock import patch


class DatabaseUrlTests(unittest.TestCase):
    def test_render_postgres_url_uses_installed_psycopg2_driver(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host/db"}):
            import importlib
            import database

            self.assertEqual(
                importlib.reload(database).get_database_url(),
                "postgresql+psycopg2://user:pass@host/db",
            )


if __name__ == "__main__":
    unittest.main()
