import base64
from io import BytesIO
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

import auth
import models
from database import get_db
from identity_cards import router, next_employee_id


class IdentityCardTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.year_patch = patch('identity_cards.issue_year', return_value='26')
        self.year_patch.start()
        self.addCleanup(self.year_patch.stop)
        self.hzt = models.Store(name='Hazratganj', code='BR004')
        self.ho = models.Store(name='Head Office', code='HO')
        self.db.add_all([self.hzt, self.ho])
        self.db.flush()
        self.users = []
        for i, role in enumerate(['Admin', 'HR', 'Owner', 'Employee', 'BrandPartner', 'Employee']):
            user = models.User(username=f'user{i}', full_name=f'Person {i}', email=f'{i}@example.test', password_hash='not-a-password', role=role, status='Active' if i != 5 else 'Inactive')
            self.db.add(user)
            user.store_id = self.ho.id if i < 3 else self.hzt.id
            self.users.append(user)
        self.db.commit()
        self.actor = self.users[0]
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[auth.get_current_user] = lambda: self.actor
        self.client = TestClient(app)
        self.payload = dict(employee_name='Corrected Name', designation='Team Lead', mobile='+91 98765 43210')

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def put(self, user=None, **changes):
        return self.client.put(f'/api/identity-cards/{(user or self.users[3]).id}', json={**self.payload, **changes})

    def test_directory_excludes_promoters_and_includes_inactive(self):
        response = self.client.get('/api/identity-cards')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(len(response.json()['cards']), 5)
        self.assertNotIn('BrandPartner', [c['role'] for c in response.json()['cards']])

    def test_employee_sees_only_self_and_cannot_edit(self):
        self.actor = self.users[3]
        data = self.client.get('/api/identity-cards').json()
        self.assertFalse(data['can_edit'])
        self.assertEqual([c['user_id'] for c in data['cards']], [self.actor.id])
        self.assertEqual(self.put().status_code, 403)

    def test_promoter_cannot_access_or_receive_card(self):
        self.assertEqual(self.put(self.users[4]).status_code, 404)
        self.actor = self.users[4]
        self.assertEqual(self.client.get('/api/identity-cards').status_code, 403)
        self.assertEqual(self.put().status_code, 403)

    def test_corrections_persist_without_changing_account(self):
        for actor in self.users[:3]:
            self.actor = actor
            self.assertEqual(self.put().status_code, 200)
        card = next(c for c in self.client.get('/api/identity-cards').json()['cards'] if c['user_id'] == self.users[3].id)
        self.assertEqual(card['employee_name'], 'Corrected Name')
        self.assertTrue(card['saved'])
        self.assertEqual(self.users[3].full_name, 'Person 3')
        self.assertEqual(self.users[3].role, 'Employee')

    def test_unique_ids_and_reserved_defaults(self):
        self.assertEqual(self.put().status_code, 200)
        self.assertEqual(self.put(self.users[5], employee_id='IDS-HZT-26001').status_code, 409)
        self.assertEqual(self.put(employee_id='IDSPL-00001').status_code, 409)
        self.assertEqual(self.put(employee_id='IDS-HZT-26001').status_code, 200)

    def test_database_rejects_duplicate_employee_id(self):
        self.client.get('/api/identity-cards')
        first = self.db.get(models.IdentityCard, self.users[3].id)
        second = self.db.get(models.IdentityCard, self.users[5].id)
        second.employee_id = first.employee_id
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_deleted_highest_serial_is_not_reused(self):
        self.client.get('/api/identity-cards')
        last = self.users[5]
        self.db.delete(self.db.get(models.IdentityCard, last.id))
        self.db.delete(last)
        self.db.commit()
        newcomer = models.User(username='replacement', email='replacement@example.test', role='Employee', password_hash='x', store_id=self.hzt.id)
        self.db.add(newcomer)
        self.db.commit()
        self.client.get('/api/identity-cards')
        self.assertEqual(self.db.get(models.IdentityCard, newcomer.id).employee_id, 'IDS-HZT-26003')

    def test_concurrent_number_reservations_are_unique(self):
        with TemporaryDirectory() as directory:
            engine = create_engine('sqlite:///' + (Path(directory) / 'identity-test.db').as_posix(),
                                   connect_args={'check_same_thread': False, 'timeout': 30})
            models.Base.metadata.create_all(engine)
            sessions = sessionmaker(bind=engine)
            def reserve(_):
                with sessions() as db:
                    value = next_employee_id(db, 'HZT')
                    db.commit()
                    return value
            try:
                with ThreadPoolExecutor(max_workers=6) as pool:
                    values = list(pool.map(reserve, range(24)))
                self.assertEqual(len(set(values)), 24)
                self.assertEqual(set(values), {f'IDS-HZT-26{i:03d}' for i in range(1, 25)})
            finally:
                engine.dispose()

    def test_outlet_numbering_and_year_rollover(self):
        data = self.client.get('/api/identity-cards').json()['cards']
        self.assertEqual([c['employee_id'] for c in data], [
            'IDS-HO-26001', 'IDS-HO-26002', 'IDS-HO-26003', 'IDS-HZT-26001', 'IDS-HZT-26002'])
        with patch('identity_cards.issue_year', return_value='27'):
            new_user = models.User(username='new', email='new@example.test', role='Employee', password_hash='x', store_id=self.hzt.id)
            self.db.add(new_user)
            self.db.commit()
            refreshed = self.client.get('/api/identity-cards').json()['cards']
        by_id = {c['user_id']: c['employee_id'] for c in refreshed}
        self.assertEqual(by_id[self.users[3].id], 'IDS-HZT-26001')
        self.assertEqual(by_id[new_user.id], 'IDS-HZT-27001')

    def test_legacy_migration_preserves_details_and_transfer_renumbers(self):
        self.db.add(models.IdentityCard(user_id=self.users[3].id, employee_id='IDSPL-00004', employee_name='Saved Name', designation='Saved Title', mobile='1234567890', photo=None))
        self.db.commit()
        self.client.get('/api/identity-cards')
        card = self.db.get(models.IdentityCard, self.users[3].id)
        self.assertEqual(card.employee_id, 'IDS-HZT-26001')
        self.assertEqual(card.employee_name, 'Saved Name')
        self.assertEqual(card.mobile, '1234567890')
        self.users[3].store_id = self.ho.id
        self.db.commit()
        self.client.get('/api/identity-cards')
        self.assertEqual(card.employee_id, 'IDS-HO-26004')
        another = models.User(username='later', email='later@example.test', role='Employee', password_hash='x', store_id=self.hzt.id)
        self.db.add(another)
        self.db.commit()
        self.client.get('/api/identity-cards')
        self.assertEqual(self.db.get(models.IdentityCard, another.id).employee_id, 'IDS-HZT-26003')

    def test_unassigned_users_do_not_get_a_false_outlet(self):
        self.users[3].store_id = None
        self.db.commit()
        self.client.get('/api/identity-cards')
        self.assertEqual(self.db.get(models.IdentityCard, self.users[3].id).employee_id, 'IDS-UNASSIGNED-26001')

    def test_invalid_data_and_photo_rejected(self):
        for change in [dict(employee_name='   '), dict(mobile='abc'), dict(employee_id='<bad>'), dict(photo='data:image/svg+xml;base64,xxx'), dict(photo='data:image/png;base64,YmFk'), dict(role='Admin')]:
            self.assertEqual(self.put(**change).status_code, 422, change)
        self.assertIsNone(self.db.get(models.IdentityCard, self.users[3].id))

    def test_photo_normalization_preservation_and_removal(self):
        output = BytesIO()
        Image.new('RGB', (100, 180), 'teal').save(output, 'PNG')
        photo = 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()
        response = self.put(photo=photo)
        self.assertEqual(response.status_code, 200)
        saved = response.json()['photo']
        self.assertTrue(saved.startswith('data:image/jpeg;base64,'))
        self.assertEqual(Image.open(BytesIO(base64.b64decode(saved.split(',')[1]))).size, (480, 480))
        self.assertEqual(self.put().json()['photo'], saved)
        self.assertIsNone(self.put(photo=None).json()['photo'])


if __name__ == '__main__':
    unittest.main()
