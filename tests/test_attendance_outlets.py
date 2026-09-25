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
        app.patch('/users/{user_id}/role', response_model=schemas.UserAdminOut)(main.update_user_role)
        app.patch('/users/{user_id}/details', response_model=schemas.UserAdminOut)(main.update_user_details)
        app.dependency_overrides[main.get_db] = lambda: self.db
        app.dependency_overrides[auth.get_current_user] = lambda: self.actor
        self.client = TestClient(app)

    def test_role_update_syncs_identity_and_attendance_designation(self):
        card = models.IdentityCard(user_id=self.employee.id, employee_id='IDS-TEST-26001',
                                   employee_name='Saved Name', designation='Other', mobile='9876543210', photo='saved-photo')
        self.db.add(card)
        self.db.commit()
        response = self.client.patch(f'/users/{self.employee.id}/role', json={'role': 'CategoryManager'})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.refresh(card)
        self.assertEqual(card.designation, 'Category Manager')
        self.assertEqual(card.employee_id, 'IDS-TEST-26001')
        self.assertEqual(card.employee_name, 'Saved Name')
        self.assertEqual(card.photo, 'saved-photo')
        self.assertEqual(card.mobile, '9876543210')
        from identity_cards import serialize
        self.assertEqual(serialize(self.employee, card, self.stores[0])['designation'], 'Category Manager')
        profile = main.attendance_user_history(self.employee.id, db=self.db, current_user=self.actor)
        self.assertEqual(profile['designation'], 'Category Manager')

    def test_brand_role_requires_valid_brands_and_saves_atomically(self):
        self.employee.role = 'Employee'
        brand = models.Brand(name='Test Brand')
        self.db.add(brand)
        self.db.commit()
        for payload in ({'role': 'BrandPartner'}, {'role': 'BrandPartner', 'brand_ids': [999999]}):
            response = self.client.patch(f'/users/{self.employee.id}/role', json=payload)
            self.assertEqual(response.status_code, 400)
            self.db.refresh(self.employee)
            self.assertEqual(self.employee.role, 'Employee')
        response = self.client.patch(f'/users/{self.employee.id}/role', json={'role': 'BrandPartner', 'brand_ids': [brand.id]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['brand_ids'], [brand.id])
        self.assertEqual(response.json()['role'], 'BrandPartner')

    def test_brand_role_can_create_other_brand(self):
        response = self.client.patch(
            f'/users/{self.employee.id}/role',
            json={'role': 'BrandManager', 'brand_name_other': '  Custom Finance Brand  '},
        )
        self.assertEqual(response.status_code, 200, response.text)
        brand = self.db.query(models.Brand).filter_by(name='Custom Finance Brand').one()
        self.assertEqual(response.json()['brand_ids'], [brand.id])
        self.assertEqual(
            self.db.query(models.UserBrand).filter_by(user_id=self.employee.id, brand_id=brand.id).count(),
            1,
        )
        self.assertEqual(response.json()['role'], 'BrandManager')

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

    def test_admin_and_hr_can_change_roles(self):
        for actor_role, assigned_role in [('Admin', 'AC Technician A'), ('HR', 'AC Technician B')]:
            self.actor.role = actor_role
            response = self.client.patch(f'/users/{self.employee.id}/role', json={'role': assigned_role})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['role'], assigned_role)
            self.assertEqual(self.employee.store_id, self.stores[0].id)

    def test_role_changes_reject_invalid_values_and_unauthorized_actors(self):
        path = f'/users/{self.employee.id}/role'
        self.assertEqual(self.client.patch(path, json={'role': 'Invalid'}).status_code, 400)
        for actor_role in ('Employee', 'Owner', 'BrandPartner'):
            self.actor.role = actor_role
            self.assertEqual(self.client.patch(path, json={'role': 'Admin'}).status_code, 403)
        self.assertEqual(self.employee.role, 'BrandPartner')

    def test_admin_and_hr_edit_details_and_clear_weekoff(self):
        path = f'/users/{self.employee.id}/details'
        for actor_role, weekoff in [('Admin', 'Monday'), ('HR', None)]:
            self.actor.role = actor_role
            result = self.client.patch(path, json={'username': ' Updated name ', 'email': ' New@Example.test ', 'weekoff_day': weekoff})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['username'], 'Updated name')
            self.assertEqual(result.json()['email'], 'new@example.test')
            self.assertEqual(result.json()['weekoff_day'], weekoff)
            self.assertEqual(result.json()['role'], 'BrandPartner')

    def test_user_details_reject_invalid_duplicate_and_unauthorized_changes(self):
        path = f'/users/{self.employee.id}/details'
        valid = {'username': 'New name', 'email': 'new@example.test', 'weekoff_day': ''}
        for changed, status in [({'username': '  '}, 400), ({'email': 'invalid'}, 400),
                                ({'email': 'A@EXAMPLE.TEST'}, 409), ({'weekoff_day': 'Holiday'}, 400),
                                ({'role': 'Admin'}, 422)]:
            response = self.client.patch(path, json={**valid, **changed})
            self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(self.employee.username, 'employee')
        for role in ['Owner', 'MISExecutive', 'Employee']:
            self.actor.role = role
            self.assertEqual(self.client.patch(path, json=valid).status_code, 403)

    def test_email_change_invalidates_old_recovery_code(self):
        self.employee.reset_token = 'old-code'
        self.db.commit()
        response = self.client.patch(f'/users/{self.employee.id}/details', json={
            'username': 'employee', 'email': 'corrected@example.test', 'weekoff_day': 'Sunday'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(self.employee.reset_token)
