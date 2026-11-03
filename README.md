# s3like – Dockerized Flask S3‑Compatible Console

A minimal Flask web console that connects to **any** S3‑compatible storage service via `boto3`. All connection parameters are supplied through **environment variables**, so the same Docker image can talk to:

* Local `moto` mock (for development & testing)
* Local MinIO or other self‑hosted S3 API
* Amazon S3, Google Cloud Storage, Wasabi, Ceph, etc.

The console provides:

| Feature | URL |
|---|---|
| List objects | `GET /` |
| List a specific bucket | `GET /bucket/<name>` |
| Upload a file | `POST /bucket/<name>/upload` |
| Presigned download URL | `GET /bucket/<name>/download/<key>` |
| Delete an object | `POST /bucket/<name>/delete/<key>` |
| Health check | `GET /health` |
| Optional Basic Auth | set `CONSOLE_USERNAME` / `CONSOLE_PASSWORD` |

---

## Quick Start (Docker)

```bash
# 1️⃣ Build the single image
docker build -t myorg/s3like-web:latest .

# 2️⃣ Run it (point at your S3 service)
docker run -d \
  -p 5000:5000 \
  -e FLASK_ENV=production \
  -e SECRET_KEY=super‑secret‑key‑change‑me \
  -e AWS_ACCESS_KEY_ID=myKey \
  -e AWS_SECRET_ACCESS_KEY=mySecret \
  -e S3_ENDPOINT_URL=https://s3.amazonaws.com \
  -e S3_REGION=us-east-1 \
  -e S3_USE_SSL=True \
  myorg/s3like-web:latest
```

The console will be reachable at `http://localhost:5000`.

### Using a local `moto` mock (development / testing)

```bash
# Start moto on port 5555
moto.server --port 5555

# Run the container pointing at moto
docker run -d \
  -p 5000:5000 \
  -e S3_ENDPOINT_URL=http://host.docker.internal:5555 \
  -e AWS_ACCESS_KEY_ID=testing \
  -e AWS_SECRET_ACCESS_KEY=testing \
  myorg/s3like-web:latest
```

---

## Configuration

All behaviour is driven by environment variables (see `app/config.py`). Defaults are included so the image runs out‑of‑the‑box.

| Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | `development` | Flask environment |
| `SECRET_KEY` | `super-secret-key-change-me` | Sign sessions – **change for production** |
| `AWS_ACCESS_KEY_ID` | `testkey` | Access key the S3 service accepts |
| `AWS_SECRET_ACCESS_KEY` | `testsecret` | Secret key the S3 service accepts |
| `S3_ENDPOINT_URL` | `http://localhost:5555` | The S3‑compatible service URL |
| `S3_REGION` | `us-east-1` | Region name |
| `S3_USE_SSL` | `False` | Set `True` if the endpoint uses HTTPS |
| `CONSOLE_USERNAME` | `` (empty) | If set, enables HTTP Basic Auth |
| `CONSOLE_PASSWORD` | `` (empty) | Password for the above user |
| `S3_BUCKET_NAME` | `my-bucket` | Default bucket name (overridable in UI) |

---

## Running the Test Suite

### Unit tests (no Docker)

```bash
pytest -m unit
```

Verifies that `Config` uses the correct defaults.

### Integration tests (uses `moto`)

```bash
pytest -m integration
```

Spins up an in‑process `moto` S3 mock and runs the CRUD flow (upload → list → presigned download → delete → health).

### Playwright UI tests

```bash
cd playwright_tests
npx playwright test
```

Opens the console in a headless browser, optionally logs in via Basic Auth, uploads a file, and verifies it appears in the bucket list.

---

## Directory Layout

```
s3like/
├── Dockerfile                # builds the Flask image
├── docker-compose.yml        # optional – only the Flask service
├── requirements.txt          # runtime deps (Flask, boto3, …)
├── test-requirements.txt     # test‑only deps (moto, pytest, playwright)
├── app/
│   ├── __init__.py          # Flask app factory + optional Basic Auth
│   ├── config.py            # env‑var driven config
│   ├── app.py               # routes + shared boto3 client
│   └── templates/           # Bootstrap HTML templates
├── tests/
│   ├── unit/                # pure unit tests
│   └── integration/         # tests using moto mock
└── playwright_tests/
    ├── playwright.config.mjs
    └── tests/
        └── test_console.test.ts   # Playwright UI test
```

---

## CI / CD (example)

A minimal GitHub Actions workflow could:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r test-requirements.txt
          npx playwright install
      - name: Run unit & integration tests
        run: pytest -vv
      - name: Run Playwright UI tests
        run: npx playwright test
      - name: Build Docker image
        run: docker build -t myorg/s3like-web:latest .
      - name: Push Docker image
        run: docker push myorg/s3like-web:latest
```

---

## License

MIT (or whatever you choose – the stack is all open‑source).