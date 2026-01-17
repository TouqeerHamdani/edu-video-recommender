import os
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from backend.app import app

class TestAuthCookies(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
    @patch("backend.auth.supabase")
    @patch.dict(os.environ, {"ENV": "development"})
    def test_login_cookies_development(self, mock_supabase):
        """
        Verify that in development (localhost), cookies are NOT Secure and SameSite=Lax.
        """
        # Mock successful login response
        mock_user = MagicMock()
        mock_user.id = "test-user-id"
        mock_user.email = "test@example.com"
        mock_user.user_metadata = {}

        mock_session = MagicMock()
        mock_session.access_token = "fake-access-token"
        mock_session.refresh_token = "fake-refresh-token"
        
        mock_auth_response = MagicMock()
        mock_auth_response.user = mock_user
        mock_auth_response.session = mock_session
        
        # Setup mock return
        mock_supabase.auth.sign_in_with_password.return_value = mock_auth_response

        # Reload module to pick up env var change if needed, 
        # but since the logic reads os.getenv inside the request handle or module level?
        # WAIT: In auth.py, ENV is read at module level: `ENV = os.getenv("ENV", "development")`
        # Patching os.environ here might be too late if the module is already imported.
        # We need to reload backend.auth to pick up the new ENV value.
        import importlib
        from backend import auth
        importlib.reload(auth)
        
        # Re-import app's router if needed or just rely on router using the reloaded module's variables?
        # FastAPI routers utilize the functions defined in the module. If we reload the module,
        # the function `login` is redefined with the new global `ENV`.
        # However, the `router` object itself might holding references to the old functions if they were decorated.
        # Actually, FastAPI stores the function reference. Reloading module changes the name binding in the module,
        # but the app instance might still point to the old function objects unless we re-include the router.
        
        # A safer way allows testing the logic without full app reload is to patch the ENV variable *where it is used* 
        # or refactor the code to read os.getenv inside the function. 
        # BUT, the user code has `ENV` global. 
        # Let's try to patch `backend.auth.ENV` directly.
        
        with patch("backend.auth.ENV", "development"):
             response = self.client.post("/api/login", json={
                "email": "test@example.com",
                "password": "password"
            })

        self.assertEqual(response.status_code, 200)
        
        # Check Cookies
        cookies = response.cookies
        self.assertIn("sb-access-token", cookies)
        
        # TestClient cookies jar handles state, but we want to inspect Set-Cookie headers or cookie attributes.
        # fastAPI TestClient is based on httpx. 
        # We can inspect `response.headers["set-cookie"]` to see raw attributes.
        
        set_cookie_header = response.headers["set-cookie"]
        
        # For development: Secure should NOT be present (or Secure=False implied by absence), SameSite=Lax
        self.assertNotIn("Secure", set_cookie_header)  # Simplistic check
        self.assertIn("SameSite=Lax", set_cookie_header)

    @patch("backend.auth.supabase")
    def test_login_cookies_production(self, mock_supabase):
        """
        Verify that in production (Render), cookies ARE Secure and SameSite=None.
        """
        # Mock successful login
        mock_user = MagicMock()
        mock_user.id = "test-user-id"
        mock_user.email = "test@example.com"
        mock_user.user_metadata = {}

        mock_session = MagicMock()
        mock_session.access_token = "fake-access-token"
        mock_session.refresh_token = "fake-refresh-token"
        
        mock_auth_response = MagicMock()
        mock_auth_response.user = mock_user
        mock_auth_response.session = mock_session
        
        mock_supabase.auth.sign_in_with_password.return_value = mock_auth_response

        # Patch the module-level ENV variable in backend.auth
        with patch("backend.auth.ENV", "production"):
            response = self.client.post("/api/login", json={
                "email": "test@example.com",
                "password": "password"
            })

        self.assertEqual(response.status_code, 200)
        
        set_cookie_header = response.headers["set-cookie"]
        
        # For production: Secure SHOULD be present, SameSite=Lax (Wait, code says None if production)
        # Let's check the code: samesite="none" if secure_flag else "lax"
        # Wait, the user code had `samesite="none" if secure_flag else "lax"`. 
        # In header it usually appears as `SameSite=None`.
        
        self.assertIn("Secure", set_cookie_header)
        # Note: TestClient/httpx might normalize headers. 
        # If strict check fails, we will debug output.
        self.assertTrue("SameSite=None" in set_cookie_header or "samesite=none" in set_cookie_header.lower())

if __name__ == "__main__":
    unittest.main()
