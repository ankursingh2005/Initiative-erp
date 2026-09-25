"""Universal signup gate and selectable role coverage on an isolated database."""
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
import test_analytics as isolated
import models
import schemas

main = isolated.main
tearDownModule = isolated.tearDownModule


class SignupRoleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def payload(self, role, code='Initiative@Universal'):
        return schemas.UserSignup(username=role, email=role+'@example.test',
            password='test-password', role=role, invite_code=code)

    @patch.dict('os.environ', {'SIGNUP_CODE_UNIVERSAL': 'Initiative@Universal'})
    @patch.object(main.auth, 'hash_password', return_value='test-hash')
    def test_non_admin_roles_accept_universal_code(self, _hash):
        for role in main.VALID_ROLES:
            if role == 'Admin':
                continue
            with self.subTest(role=role):
                user = main.signup(self.payload(role), self.db)
                self.assertEqual(user.role, role)

    @patch.dict('os.environ', {'SIGNUP_CODE_UNIVERSAL': 'Initiative@Universal',
                              'SIGNUP_CODE_ADMIN': 'test-admin-only-code'})
    @patch.object(main.auth, 'hash_password', return_value='test-hash')
    def test_admin_requires_separate_code(self, _hash):
        with self.assertRaises(HTTPException) as error:
            main.signup(self.payload('Admin'), self.db)
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.db.query(models.User).count(), 0)
        user = main.signup(self.payload('Admin', 'test-admin-only-code'), self.db)
        self.assertEqual(user.role, 'Admin')

    def test_incorrect_code_and_unknown_role_create_no_account(self):
        for role, code, status in [('Loader', 'incorrect', 403),
                                    ('InvalidRole', 'Initiative@Universal', 400)]:
            with patch.dict('os.environ', {'SIGNUP_CODE_UNIVERSAL': 'Initiative@Universal'}):
                with self.assertRaises(HTTPException) as error:
                    main.signup(self.payload(role, code), self.db)
                self.assertEqual(error.exception.status_code, status)
        self.assertEqual(self.db.query(models.User).count(), 0)

    @patch.dict('os.environ', {'SIGNUP_CODE_UNIVERSAL': 'Initiative@Universal'})
    @patch.object(main.auth, 'hash_password', return_value='test-hash')
    def test_signup_other_brand_creates_and_assigns_brand(self, _hash):
        payload = self.payload('BrandPartner')
        payload.brand_name_other = '  New Test Brand  '
        user = main.signup(payload, self.db)
        brand = self.db.query(models.Brand).filter_by(name='New Test Brand').one()
        self.assertEqual(
            self.db.query(models.UserBrand).filter_by(user_id=user.id, brand_id=brand.id).count(),
            1,
        )
