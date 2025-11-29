#!/usr/bin/env python3
"""
Test forgot password functionality
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.routers.auth import forgot_password, reset_password, ForgotPasswordRequest, ResetPasswordRequest

async def test_forgot_password():
    """Test forgot password with a mock email"""
    try:
        # Test with a non-existent email (should not reveal if exists)
        request = ForgotPasswordRequest(email="nonexistent@example.com")
        result = await forgot_password(request)
        print("Forgot password result:", result)

        # Test with an existing email if possible, but for now, just check the flow
        print("Forgot password test completed successfully")
    except Exception as e:
        print(f"Forgot password test failed: {e}")

async def test_reset_password():
    """Test reset password (this will fail without a valid OTP)"""
    try:
        request = ResetPasswordRequest(
            email="test@example.com",
            otp="123456",
            new_password="newpassword123"
        )
        result = await reset_password(request)
        print("Reset password result:", result)
    except Exception as e:
        print(f"Reset password test failed (expected): {e}")

if __name__ == "__main__":
    asyncio.run(test_forgot_password())
    asyncio.run(test_reset_password())