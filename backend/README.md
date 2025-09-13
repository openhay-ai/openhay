# Backend for Open AI Hay

This is the backend for Open AI Hay, a FastAPI application that provides AI-powered features. It uses PostgreSQL for data storage and connects to various LLM providers.

## Local Development Setup

Follow these steps to get the backend running directly on your local machine without Docker.

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended for package management)
- A running PostgreSQL instance

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/open-ai-hay.git
cd open-ai-hay/backend
```

### 2. Install Dependencies

It's recommended to use a virtual environment.

```bash
# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
uv sync --locked
```

### 3. Crawl4AI Setup (one-time)

Run the setup command once:

```bash
uv run crawl4ai-setup
```

If you later see Playwright/browser errors, install Chromium:

```bash
uv run playwright install --with-deps chromium
```

### 4. Configure Environment Variables

Create a `.env` file by copying the example file:

```bash
cp env.example .env
```

Now, open the `.env` file and fill in the required values. At a minimum, you must provide:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- The API key for your chosen `LLM_PROVIDER` (e.g., `GOOGLE_API_KEY`)

See the comments in the `.env.example` file for more details on each variable.

### 5. Database Setup

Ensure PostgreSQL is running and a database (e.g., `openhay`) exists. The app will create tables, extensions, and seed presets on first start.

For macOS with Homebrew:

```bash
# Install and start PostgreSQL
brew install postgresql@16
brew services start postgresql@16

# Create a default user and the database
createuser -s postgres || true
psql -U postgres -h 127.0.0.1 -p 5432 -c "ALTER USER postgres WITH PASSWORD 'postgres';"
createdb -U postgres -h 127.0.0.1 -p 5432 openhay
```

Set your database URL in `.env`:

```env
DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/openhay"
```

Optional: verify connectivity

```bash
psql "postgresql://postgres:postgres@localhost:5432/openhay" -c "SELECT 1;"
```

### 6. Run the Application

```bash
uv run uvicorn backend.api.main:app --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`.

## Architecture Overview

The backend is structured in a layered architecture to separate concerns. Here is a high-level overview of the request flow and component interaction:

```mermaid
graph TD
    subgraph User
        Client[Client / Frontend]
    end

    subgraph Backend Application
        API[API Layer<br>/api/routers]
        Services[Service Layer<br>/core/services]
        Agents[Agent Layer<br>/core/agents]
        Repositories[Data Access Layer<br>/core/repositories]
        DB[(PostgreSQL Database)]
    end

    subgraph External Services
        LLM[LLM Providers]
    end

    Client --> API
    API --> Services
    Services --> Agents
    Services --> Repositories
    Repositories --> DB
    Agents --> LLM

    style Client fill:#f9f,stroke:#333,stroke-width:2px
    style DB fill:#cff,stroke:#333,stroke-width:2px
    style LLM fill:#cff,stroke:#333,stroke-width:2px
```

The application leverages a few key libraries to handle complex tasks:

- **LLM Orchestration**: [pydantic-ai](https://github.com/pydantic/pydantic-ai) is used within the Agent Layer to orchestrate interactions with LLM providers, manage agentic workflows, and handle structured data parsing.
- **Observability**: [logfire](https://github.com/pydantic/logfire) is integrated for comprehensive logging and tracing, offering deep insights into request lifecycles and the behavior of LLM chains.

## Deployment on Railway

This project is configured to be deployed on [Railway](https://railway.app/) using the provided `Dockerfile`.

### 1. Create Project

- Create a new project on Railway and choose "Deploy from GitHub repo".
- Select your forked repository. Railway will automatically detect the `Dockerfile`.

### 2. Add a PostgreSQL Database

- Within your Railway project, add a new service and select "PostgreSQL".
- Railway will automatically provision a database and inject the `DATABASE_URL` environment variable into your application service.

### 3. Configure Environment Variables

- In your application service settings, go to the "Variables" tab.
- Add the required environment variables. You can copy them from your local `.env` file or reference `env.example`.
- Key variables to set include:
  - `JWT_SECRET_KEY`
  - `LLM_PROVIDER` and the corresponding API key (e.g., `GOOGLE_API_KEY`)
  - `BRAVE_API_KEY` (if used)
- **CORS Configuration**: To allow your frontend to communicate with the API, you need to configure CORS. Set the `HOST_URL` environment variable to your frontend's full URL (e.g., `https://my-frontend.up.railway.app`). If you have multiple domains, use `ALLOWED_ORIGINS` with a comma-separated list. Railway will automatically inject the `DATABASE_URL`.

### 4. Deployment

Railway will automatically build and deploy your application.
