# S3Like external Compose consumer

This example demonstrates a separate application using the reusable S3Like image
over a shared Docker network. Copy the template first:

```bash
cp .env.example .env
docker compose up --build --abort-on-container-exit
```

The `--build` workflow builds the repository image locally. To use a prebuilt
image instead, set `S3LIKE_IMAGE` in `.env` and run:

```bash
S3LIKE_IMAGE=cosqnetwork/s3like:0.2.0 docker compose up --abort-on-container-exit
```

The published image is available from Docker Hub. Replace `0.2.0` with the
release you want to consume; `cosqnetwork/s3like:latest` is also updated by
version-tagged releases.

Only host-side ports are configurable with `S3LIKE_API_PORT` and
`S3LIKE_CONSOLE_PORT`. Verify the API at
`http://localhost:${S3LIKE_API_PORT:-9000}` and the console at
`http://localhost:${S3LIKE_CONSOLE_PORT:-9001}`.

The application connects to `http://s3like:9000`. Inside a container,
`localhost:9000` is the application container itself and is therefore incorrect;
the published host ports are not needed for container-to-container traffic.

Clean up the project-scoped containers, network, and named volume with:

```bash
docker compose down -v
```
