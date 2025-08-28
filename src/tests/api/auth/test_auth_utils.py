import unittest
from unittest.mock import patch, MagicMock
import base64
import json

from auth import auth_utils,sample_user 


class TestAuthUtils(unittest.TestCase):

    @patch("auth.sample_user")
    def test_get_authenticated_user_details_dev_mode(self, mock_sample_user):
        mock_sample_user.sample_user = {
            "x-ms-client-principal-id": "123",
            "x-ms-client-principal-name": "testuser",
            "x-ms-client-principal-idp": "aad",
            "x-ms-token-aad-id-token": "token123",
            "x-ms-client-principal": "encodedstring"
        }

        request_headers = {}  
        result = auth_utils.get_authenticated_user_details(request_headers)

        self.assertEqual(result["user_principal_id"], "123")
        self.assertEqual(result["user_name"], "testuser")
        self.assertEqual(result["auth_provider"], "aad")
        self.assertEqual(result["auth_token"], "token123")
        self.assertEqual(result["client_principal_b64"], "encodedstring")
        self.assertEqual(result["aad_id_token"], "token123")

    def test_get_authenticated_user_details_prod_mode(self):
        request_headers = {
            "x-ms-client-principal-id": "123",
            "x-ms-client-principal-name": "testuser",
            "x-ms-client-principal-idp": "aad",
            "x-ms-token-aad-id-token": "token123",
            "x-ms-client-principal": "encodedstring"
        }

        result = auth_utils.get_authenticated_user_details(request_headers)

        self.assertEqual(result["user_principal_id"], "123")
        self.assertEqual(result["user_name"], "testuser")
        self.assertEqual(result["auth_provider"], "aad")
        self.assertEqual(result["auth_token"], "token123")
        self.assertEqual(result["client_principal_b64"], "encodedstring")
        self.assertEqual(result["aad_id_token"], "token123")

    def test_get_tenantid_valid_b64(self):
        payload = {"tid": "tenant123"}
        b64_encoded = base64.b64encode(json.dumps(payload).encode()).decode()

        result = auth_utils.get_tenantid(b64_encoded)
        self.assertEqual(result, "tenant123")

    def test_get_tenantid_invalid_b64(self):
        with self.assertLogs(level='ERROR'):
            result = auth_utils.get_tenantid("notbase64!!!")
        self.assertEqual(result, "")

    def test_get_tenantid_none(self):
        result = auth_utils.get_tenantid(None)
        self.assertEqual(result, "")


if __name__ == '__main__':
    unittest.main()
