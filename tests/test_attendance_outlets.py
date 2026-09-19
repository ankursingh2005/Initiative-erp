"""Isolated API coverage; never modifies the application's user database."""
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import test_analytics as isolated
import auth
import models
import schemas

main = isolated.main
tearDownModule = isolated.tearDownModule


class AttendanceOutletTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.stores = [models.Store(name='Old', status='Active', latitude=26, longitude=80),
                       models.Store(name='New', status='Active', latitude=27, longitude=81),
                       models.Store(name='No GPS', status='Active')]
        self.db.add_all(self.stores)
        self.db.flush()
        self.employee = models.User(username='employee', email='e@example.test', role='BrandPartner',
                                    status='Active', password_hash='unused', store_id=self.stores[0].id)
        self.actor = models.User(username='admin', email='a@example.test', role='Admin', status='Active', password_hash='unused')
        self.db.add_all([self.employee, self.actor])
        self.db.commit()
        app = FastAPI()
        app.patch('/users/{user_id}/outlet', response_model=schemas.UserAdminOut)(main.update_attendance_outlet)
        app.dependency_overrides[main.get_db] = lambda: self.db
        app.dependency_overrides[auth.get_current_user] = lambda: self.actor
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def update(self, store):
        return self.client.patch(f'/users/{self.employee.id}/outlet', json={'store_id': store.id})

    def test_admin_and_hr_can_reassign_including_promoters(self):
        for role in ('Admin', 'HR'):
            self.actor.role = role
            response = self.update(self.stores[1])
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['store_id'], self.stores[1].id)
            reference = main.attendance_reference_store(self.db, self.employee, lambda store: 0)
            self.assertEqual(reference.id, self.stores[1].id)

    def test_other_roles_cannot_reassign(self):
        for role in ('Employee', 'BrandPartner', 'Owner'):
            self.actor.role = role
            self.assertEqual(self.update(self.stores[1]).status_code, 403)
        self.assertEqual(self.employee.store_id, self.stores[0].id)

    def test_unconfigured_or_inactive_outlet_is_rejected(self):
        self.assertEqual(self.update(self.stores[2]).status_code, 400)
        self.stores[1].status = 'Inactive'
        self.db.commit()
        self.assertEqual(self.update(self.stores[1]).status_code, 400)
        self.assertEqual(self.employee.store_id, self.stores[0].id)
