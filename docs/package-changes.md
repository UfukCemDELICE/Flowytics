# Package Changes Required

## Backend (pyproject.toml)

### Add
```bash
uv add sqlmodel asyncpg orjson
```

### Remove
```bash
uv remove supabase
```

Supabase Python SDK replaced by direct Postgres connection via SQLModel + asyncpg.
Supabase is still used as the managed database — just not the SDK.

### Note on QuickBooks
Direct integration via python-quickbooks.
httpx is already in dependencies. One file to maintain, zero SDK version risk.

### Final dependency list
```toml
dependencies = [
    "anthropic>=0.83.0",
    "apscheduler>=3.11.0",
    "asyncpg>=0.30.0",
    "clerk-backend-api>=5.0.2",
    "cryptography>=46.0.5",
    "fastapi[standard]>=0.129.2",
    "httpx>=0.28.1",
    "langchain-anthropic>=1.3.3",
    "langchain-core>=1.2.14",
    "langgraph>=1.0.9",
    "orjson>=3.10.0",
    "plaid-python>=29.0.0",
    "polars>=1.38.1",
    "pydantic-settings>=2.13.1",
    "pyjwt>=2.11.0",
    "python-dotenv>=1.2.1",
    "slack-bolt>=1.27.0",
    "slack-sdk>=3.40.1",
    "sqlmodel>=0.0.22",
    "stripe>=14.3.0",
    "uvicorn[standard]>=0.41.0",
]
```

## Frontend (package.json)

### Add
```bash
cd frontend
npm install react-plaid-link
```

Needed for Plaid Link UI in onboarding step 3.

### Final dependencies
```json
{
    "@clerk/nextjs": "^6.38.1",
    "@stripe/stripe-js": "^8.8.0",
    "next": "16.1.6",
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "react-plaid-link": "^3.6.0",
    "stripe": "^20.3.1"
}
```

Note: QuickBooks OAuth is handled via redirect from the backend.
