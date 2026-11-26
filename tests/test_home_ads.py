import io
import unittest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
import auth
import models
from database import get_db
from home_ads import router


class HomeAdsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        models.HomeAdvertisement.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.user = SimpleNamespace(role='Admin')
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[auth.get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_save_reload_hide_show_clear(self):
        result = self.client.put('/api/home-ad', data={'title': 'Offer', 'message': 'Earn rewards', 'visible': 'true'},
                                 files={'media': ('offer.png', io.BytesIO(b'example-media'), 'image/png')})
        self.assertEqual(result.status_code, 200)
        self.db.expire_all()
        self.assertEqual(self.client.get('/api/home-ad').json()['message'], 'Earn rewards')
        self.assertEqual(self.client.get('/api/home-ad/media').content, b'example-media')
        self.client.patch('/api/home-ad/visibility', data={'visible': 'false'})
        self.user.role = 'SalesExecutive'
        self.assertFalse(self.client.get('/api/home-ad').json()['visible'])
        self.assertEqual(self.client.get('/api/home-ad/media').status_code, 404)
        self.assertEqual(self.client.delete('/api/home-ad').status_code, 403)
        self.user.role = 'Admin'
        self.client.patch('/api/home-ad/visibility', data={'visible': 'true'})
        self.assertTrue(self.client.get('/api/home-ad').json()['visible'])
        self.client.delete('/api/home-ad')
        self.assertIsNone(self.db.get(models.HomeAdvertisement, 1))
        self.assertEqual(self.client.get('/api/home-ad/media').status_code, 404)

    def test_validation_and_media_removal(self):
        self.assertEqual(self.client.put('/api/home-ad', data={'message': 'x'}, files={'media': ('x.html', b'x', 'text/html')}).status_code, 422)
        self.assertEqual(self.client.put('/api/home-ad', data={'title': 'x' * 161}).status_code, 422)
        self.assertEqual(self.client.put('/api/home-ad', data={'title': ' '}).status_code, 422)
        self.db.rollback()
        self.client.put('/api/home-ad', data={'message': 'Offer'}, files={'media': ('x.mp4', b'video', 'video/mp4')})
        response = self.client.put('/api/home-ad', data={'message': 'Text only', 'remove_media': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['media_type'])
        self.assertEqual(self.client.get('/api/home-ad/media').status_code, 404)

    def test_all_users_can_view_but_only_admin_and_hr_can_edit(self):
        import ast
        from pathlib import Path
        source = ast.parse(Path('main.py').read_text(encoding='utf-8-sig'))
        roles = next(ast.literal_eval(node.value) for node in source.body
                     if isinstance(node, ast.Assign) and any(
                         isinstance(target, ast.Name) and target.id == 'VALID_ROLES'
                         for target in node.targets))
        self.client.put('/api/home-ad', data={'title': 'Offer', 'message': 'For everyone'},
                        files={'media': ('offer.png', b'example', 'image/png')})
        for role in roles + ['Owner']:
            with self.subTest(role=role):
                self.user.role = role
                self.assertEqual(self.client.get('/api/home-ad').json()['message'], 'For everyone')
                self.assertEqual(self.client.get('/api/home-ad/media').status_code, 200)
                if role not in {'Admin', 'HR'}:
                    self.assertEqual(self.client.put('/api/home-ad', data={'message': 'Unauthorized'}).status_code, 403)
                    self.assertEqual(self.client.patch('/api/home-ad/visibility', data={'visible': 'false'}).status_code, 403)
                    self.assertEqual(self.client.delete('/api/home-ad').status_code, 403)
        for role in ['Admin', 'HR']:
            self.user.role = role
            self.assertEqual(self.client.put('/api/home-ad', data={'message': 'For everyone'}).status_code, 200)
            self.assertEqual(self.client.patch('/api/home-ad/visibility', data={'visible': 'false'}).status_code, 200)
            self.assertEqual(self.client.get('/api/home-ad').json()['message'], 'For everyone')
            self.assertEqual(self.client.get('/api/home-ad/media').status_code, 200)
            self.assertEqual(self.client.patch('/api/home-ad/visibility', data={'visible': 'true'}).status_code, 200)
        self.assertEqual(self.client.delete('/api/home-ad').status_code, 200)


if __name__ == '__main__':
    unittest.main()
