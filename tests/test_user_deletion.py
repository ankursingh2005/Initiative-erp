"""Account deletion with real foreign-key enforcement and role checks."""
from datetime import date, datetime
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import test_analytics as isolated
import auth
import models
import ems_models

main = isolated.main
tearDownModule = isolated.tearDownModule


class UserDeletionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        event.listen(self.engine, 'connect', lambda conn, _: conn.execute('PRAGMA foreign_keys=ON'))
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.actor = models.User(username='Admin', email='admin@example.test', role='Admin', password_hash='unused')
        self.target = models.User(username='Target', email='target@example.test', role='Employee', password_hash='unused')
        self.db.add_all([self.actor, self.target])
        self.db.commit()
        app = FastAPI()
        app.delete('/users/{user_id}')(main.delete_user)
        app.dependency_overrides[main.get_db] = lambda: self.db
        app.dependency_overrides[auth.get_current_user] = lambda: self.actor
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_admin_and_hr_delete_accounts_with_linked_records(self):
        for role in ('Admin', 'HR'):
            with self.subTest(role=role):
                self.actor.role = role
                target = models.User(username=role+' target', email=role+'@target.test', role='Admin', password_hash='unused')
                self.db.add(target)
                self.db.flush()
                uid = target.id
                po = models.PurchaseOrder(request_no=role, request_date=date.today(), submitted_by_user_id=uid, approved_by_user_id=uid, verified_by_user_id=uid)
                self.db.add(po)
                self.db.flush()
                receipt = models.PurchaseOrderReceipt(purchase_order_id=po.id, location_name='Warehouse', document_number=role, received_date=date.today(), received_by_user_id=uid, voided_by_user_id=uid)
                other_leave = models.AttendanceLeave(user_id=self.target.id, created_by=uid, leave_date=date.today())
                self.db.add_all([receipt, other_leave,
                    models.AttendanceRecord(user_id=uid, attendance_date=date.today()),
                    models.AttendanceLocationPoint(user_id=uid, captured_at=datetime.now(), latitude=1, longitude=1),
                    models.AttendanceLeave(user_id=uid, created_by=uid, leave_date=date.today()),
                    models.IdentityCard(user_id=uid, employee_id=role, employee_name='Target', designation='Employee'),
                    ems_models.EMSLeaveRequest(user_id=uid, start_date=date.today(), end_date=date.today(), kind='casual', reason='Leave'),
                    ems_models.EMSEarning(user_id=uid, month='2026-09', kind='bonus', amount=100, note='Bonus', created_by=self.actor.id),
                    ems_models.EMSPayroll(user_id=uid, month='2026-09', basic=100, allowances=0, deductions=0, incentives=0, bonuses=0, net=100, created_by=self.actor.id)])
                self.db.commit()
                response = self.client.delete('/users/'+str(uid))
                self.assertEqual(response.status_code, 200, response.text)
                self.db.expire_all()
                self.assertIsNone(self.db.get(models.User, uid))
                self.assertEqual(po.submitted_by_user_id, self.actor.id)
                self.assertIsNone(po.verified_by_user_id)
                self.assertIsNone(po.approved_by_user_id)
                self.assertEqual(receipt.received_by_user_id, self.actor.id)
                self.assertIsNone(receipt.voided_by_user_id)
                self.assertIn('Originally received by', receipt.notes)
                self.assertEqual(other_leave.created_by, self.actor.id)
                for model in (models.AttendanceRecord, models.AttendanceLocationPoint, models.AttendanceLeave, models.IdentityCard, ems_models.EMSLeaveRequest, ems_models.EMSEarning, ems_models.EMSPayroll):
                    self.assertEqual(self.db.query(model).filter(model.user_id == uid).count(), 0)

    def test_other_roles_and_self_deletion_are_blocked(self):
        for role in ('Employee', 'Owner', 'CategoryManager', 'ServiceManager'):
            self.actor.role = role
            self.db.commit()
            self.assertEqual(self.client.delete('/users/'+str(self.target.id)).status_code, 403)
        for role in ('Admin', 'HR'):
            self.actor.role = role
            self.db.commit()
            self.assertEqual(self.client.delete('/users/'+str(self.actor.id)).status_code, 400)
