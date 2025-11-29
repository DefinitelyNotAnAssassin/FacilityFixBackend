# Backend for FacilityFix

## Setup Instructions
1. Copy `.env.example` to `.env`
2. Fill in your Firebase credentials
3. Add your `firebase-service-account.json` file
4. Configure email settings (SendGrid API key for production email sending)
5. Set up Redis for background tasks (Celery)

## Environment Variables

### Required
- `FIREBASE_PROJECT_ID` - Your Firebase project ID
- `FIREBASE_STORAGE_BUCKET` - Firebase Storage bucket name
- `FIREBASE_WEB_API_KEY` - Firebase Web API key
- `FIREBASE_SERVICE_ACCOUNT_PATH` - Path to Firebase service account JSON file

### Optional
- `SENDGRID_API_KEY` - SendGrid API key for email sending (leave empty for mock mode)
- `FROM_EMAIL` - Email address for sending emails (default: noreply@facilityfix.com)
- `FROM_NAME` - Name for email sender (default: FacilityFix)
- `REDIS_URL` - Redis URL for Celery (default: redis://localhost:6379/0)
- `EMAIL_MOCK_MODE` - Set to `false` for production email sending (default: true)
- `USE_GROQ` - Enable GROQ AI features (default: false)
- `GROQ_API_KEY` - GROQ API key for AI features

## Running the Application

### Development
```bash
# Start the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker for background tasks
celery -A app.core.celery_app.celery_app worker --loglevel=info
```

### Production
- Set `EMAIL_MOCK_MODE=false` and provide `SENDGRID_API_KEY` for real email sending
- Ensure Redis is running for Celery background tasks
- Use a production WSGI server like Gunicorn instead of uvicorn

## API Endpoints

### Authentication
- `POST /auth/login` - Login with email and password
- `POST /auth/register/admin` - Register admin user
- `POST /auth/register/staff` - Register staff user
- `POST /auth/register/tenant` - Register tenant user
- `GET /auth/me` - Get current user info
- `PATCH /auth/change-password` - Change own password
- `POST /auth/logout` - Logout current user
- `POST /auth/logout-all-devices` - Logout from all devices
- `POST /auth/forgot-password` - Request password reset OTP via email
- `POST /auth/reset-password` - Reset password using OTP

**Note**: The forgot password feature sends OTP codes via email. In development, emails are logged to console when `EMAIL_MOCK_MODE=true`. For production, set `EMAIL_MOCK_MODE=false` and provide a valid `SENDGRID_API_KEY`.

### Other Endpoints
... (add other endpoints as needed)