# Production Plan API

This FastAPI project exposes an endpoint that generates an optimal production plan using the logic in [`planner.build_production_plan`](app/planner.py).

## Prerequisites

- Python 3.10.9 (see [.python-version](.python-version))
- Recommended: virtual environment (`python -m venv .venv`)

## Setup

1. Activate your virtual environment.
2. Install dependencies:

   ```sh
   pip install -r requirements.txt
   ```

## Running the API

Start the development server from the repository root:

```sh
uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

The server hosts the `/productionplan` endpoint defined in [app/main.py](app/main.py).

## Usage

Send a `POST` request with a JSON payload matching [`models.ProductionPlanRequest`](app/models.py):

```sh
curl -X POST http://localhost:8888/productionplan \
     -H "Content-Type: application/json" \
     -d @example_payloads/payload3.json
```

For Windows Powershell:

```sh
curl.exe -X POST http://localhost:8888/productionplan -H "Content-Type: application/json" -d "@example_payloads/payload3.json"
```


The response contains a list of [`models.ProductionPlanItem`](app/models.py) objects describing the allocated production.