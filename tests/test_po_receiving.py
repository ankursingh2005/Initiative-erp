import unittest
from datetime import date, datetime
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
import models
import po_receiving as receiving


class ReceivingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.store = models.Store(name='Outlet A', status='Active')
        self.db.add(self.store)
        self.db.flush()
        self.mis = models.User(username='MIS', email='mis@test', password_hash='x', role='MISExecutive')
        self.staff = models.User(username='Staff', email='staff@test', password_hash='x', role='SalesExecutive', store_id=self.store.id)
        self.warehouse = models.User(username='Warehouse', email='warehouse@test', password_hash='x', role='LogisticManager')
        self.accounts = models.User(username='Accounts', email='accounts@test', password_hash='x', role='Accounts')
        self.manager = models.User(username='Manager', email='manager@test', password_hash='x', role='AsstSalesManager', store_id=self.store.id)
        self.db.add_all([self.mis, self.staff, self.warehouse, self.accounts, self.manager])
        self.db.flush()
        self.po = models.PurchaseOrder(request_no='PO-1', request_date=date.today(), status='Ordered',
            email_sent_at=datetime.utcnow(), submitted_by_user_id=self.mis.id,
            items=[models.PurchaseOrderItem(product_name='Fridge', quantity=10, unit='Nos'),
                   models.PurchaseOrderItem(product_name='TV', quantity=2, unit='Nos')])
        self.db.add(self.po)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def receipt(self, quantities, document='INV-1', warehouse=False):
        return receiving.ReceiptInput(store_id=None if warehouse else self.store.id,
            document_number=document, received_date=date.today(),
            lines=[{'item_id': item.id, 'quantity': quantity} for item, quantity in zip(self.po.items, quantities)])

    def test_partial_deliveries_at_outlet_and_warehouse_then_verify(self):
        result = receiving.receive_order(self.po.id, self.receipt([4, 2]), self.db, self.staff)
        self.assertEqual(result['stage'], 'Receipt mismatch')
        with self.assertRaises(HTTPException) as error:
            receiving.verify_order(self.po.id, self.db, self.accounts)
        self.assertEqual(error.exception.status_code, 409)
        self.db.rollback()
        result = receiving.receive_order(self.po.id, self.receipt([6, 0], 'INV-2', True), self.db, self.warehouse)
        self.assertEqual(result['stage'], 'Awaiting verification')
        with self.assertRaises(HTTPException):
            receiving.verify_order(self.po.id, self.db, self.staff)
        result = receiving.verify_order(self.po.id, self.db, self.accounts)
        self.assertEqual(result['stage'], 'Completed')
        self.assertEqual(result['verified_by'], 'Accounts')
        with self.assertRaises(HTTPException):
            receiving.receive_order(self.po.id, self.receipt([1, 0], 'INV-3'), self.db, self.staff)
        self.db.rollback()
        with self.assertRaises(HTTPException):
            receiving.void_receipt(self.po.id, result['receipts'][0]['id'], self.db, self.mis)

    def test_excess_void_and_corrected_receipt(self):
        result = receiving.receive_order(self.po.id, self.receipt([11, 2]), self.db, self.staff)
        self.assertEqual(result['matching'][0]['difference'], 1)
        with self.assertRaises(HTTPException):
            receiving.verify_order(self.po.id, self.db, self.accounts)
        self.db.rollback()
        receiving.void_receipt(self.po.id, result['receipts'][0]['id'], self.db, self.staff)
        result = receiving.receive_order(self.po.id, self.receipt([10, 2]), self.db, self.staff)
        self.assertEqual(result['stage'], 'Awaiting verification')
        self.assertIsNotNone(result['receipts'][0]['voided_at'])

    def test_unsent_po_and_wrong_location_and_foreign_item_rejected(self):
        with self.assertRaises(HTTPException):
            receiving.receive_order(self.po.id, self.receipt([1, 0], warehouse=True), self.db, self.staff)
        payload = self.receipt([1, 0]); payload.lines[0].item_id = 9999
        with self.assertRaises(HTTPException):
            receiving.receive_order(self.po.id, payload, self.db, self.staff)
        self.db.rollback()
        self.po.email_sent_at = None; self.db.commit()
        with self.assertRaises(HTTPException):
            receiving.receive_order(self.po.id, self.receipt([10, 2]), self.db, self.staff)

    def test_duplicate_document_and_invalid_quantities(self):
        receiving.receive_order(self.po.id, self.receipt([1, 0]), self.db, self.staff)
        with self.assertRaises(HTTPException) as error:
            receiving.receive_order(self.po.id, self.receipt([1, 0]), self.db, self.staff)
        self.assertEqual(error.exception.status_code, 409)
        for quantity in [-1, 1.5, True]:
            with self.assertRaises(ValidationError):
                receiving.ReceiptLineInput(item_id=1, quantity=quantity)

    def test_http_receipt_verification_and_authentication(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(receiving.router)
        def database_override():
            with Session(self.engine) as session:
                yield session
        app.dependency_overrides[receiving.get_db] = database_override
        client = TestClient(app)
        self.assertEqual(client.get('/api/po-receiving-options').status_code, 401)
        app.dependency_overrides[receiving.auth.get_current_user] = lambda: self.staff
        options = client.get('/api/po-receiving-options').json()
        self.assertEqual(options['locations'], [{'id': self.store.id, 'name': 'Outlet A'}])
        self.assertFalse(options['can_verify'])
        prefix = f'/api/purchase-orders/{self.po.id}'
        result = client.post(prefix + '/receipts', json=self.receipt([10, 2]).model_dump(mode='json'))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['stage'], 'Awaiting verification')
        self.assertEqual(client.post(prefix + '/verify').status_code, 403)
        app.dependency_overrides[receiving.auth.get_current_user] = lambda: self.accounts
        result = client.post(prefix + '/verify')
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['stage'], 'Completed')

    def test_outlet_manager_can_verify_own_outlet(self):
        receiving.receive_order(self.po.id, self.receipt([10, 2]), self.db, self.staff)
        result = receiving.verify_order(self.po.id, self.db, self.manager)
        self.assertEqual(result['verified_by'], 'Manager')

    def test_mis_can_verify_completed_receipts(self):
        receiving.receive_order(self.po.id, self.receipt([10, 2]), self.db, self.staff)
        result = receiving.verify_order(self.po.id, self.db, self.mis)
        self.assertEqual(result['stage'], 'Completed')
        self.assertEqual(result['verified_by'], 'MIS')

    def test_outlet_manager_cannot_verify_warehouse_receipts(self):
        receiving.receive_order(self.po.id, self.receipt([10, 2], warehouse=True), self.db, self.warehouse)
        with self.assertRaises(HTTPException) as error:
            receiving.verify_order(self.po.id, self.db, self.manager)
        self.assertEqual(error.exception.status_code, 403)
        self.db.rollback()
        result = receiving.verify_order(self.po.id, self.db, self.warehouse)
        self.assertEqual(result['stage'], 'Completed')


if __name__ == '__main__':
    unittest.main()
