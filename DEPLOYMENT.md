# Host Contour from GitHub

Contour requires a Python server and native CPU libraries. GitHub stores the source
and runs CI; **GitHub Pages cannot run this backend**. Use a Docker-capable web
service such as Render. These files do not publish a service or create an account.

## Local development

Keep using `python run.py`. It binds to loopback, processes images on that computer,
and can optionally remember an API key in `.local/settings.json`.

## Container

The Dockerfile targets Linux x86-64 with Python 3.12 and pinned headless OpenCV/ZXing dependencies.
Other CPU architectures require their own dependency and container verification.
A separate C++17 build stage compiles the included CImg bridge. The runtime runs as
UID 10001, contains no compiler and requires no GPU. Its build-context allowlist
excludes local credentials, environments and test artifacts.

```sh
docker build -t contour .
docker run --rm -p 127.0.0.1:8000:8000 --memory=2g --cpus=2 \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m contour
```

Open `http://127.0.0.1:8000`. This exercises public/BYO-key mode locally. For a public
domain, put an HTTPS reverse proxy in front and configure the exact hostname:

```sh
docker run --rm -p 127.0.0.1:8000:8000 --memory=2g --cpus=2 \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -e CONTOUR_ALLOWED_HOSTS=contour.example.com contour
```

Do not expose an unencrypted HTTP port on the internet: visitors send images and
API keys to this server. The app rejects HTTP browser origins for public hostnames.
The HTTPS proxy must preserve Host. Arbitrary forwarded host/IP headers are not
trusted. TLS is terminated by the hosting platform or your reverse proxy.

## Render

1. Put the source in a GitHub repository, excluding `.local/`, `.env`, `.venv/`,
   `.tools/` and `artifacts/`.
2. Create a Render Blueprint from `render.yaml`, or a Docker web service using this
   Dockerfile and `/api/health` as its health check.
3. Choose sufficient memory. **2 GB is a starting allocation for a small service,
   not a proven concurrency capacity**; load-test your actual image sizes.
4. Render supplies `PORT` and `RENDER_EXTERNAL_HOSTNAME`. That exact hostname is
   accepted automatically. Add custom domains as a comma-separated
   `CONTOUR_ALLOWED_HOSTS` value. Wildcards and unconfigured hosts are rejected.
   Omitted HTTPS ports and explicit `:443` are equivalent; other ports must be
   included explicitly, such as `contour.example.com:8443`.
5. Leave `CONTOUR_PUBLIC=1`. Do not set `OPENAI_API_KEY` or copy local settings.
   Public mode ignores saved and environment keys. Each visitor supplies their own.

No database or persistent disk is required. Workspaces stay in browser page memory
until users save a project. Uploads and keys are processed transiently in server
memory. Infrastructure logging/backups and provider retention are the operator's
responsibility. Do not enable request-body or header logging.

## Public-mode behavior and limits

- CV runs on the **server CPU**, not in the visitor's browser. Measured timings
  describe that server; estimates for a separate target remain estimates.
- Local key storage and automatic server-key fallback are disabled. A key supplied
  in `X-OpenAI-Key` is used for that request and excluded from projects/exports.
  AI actions send the selected training images/context to OpenAI with `store: false`.
- Writes require JSON and same-origin browser requests. Unknown hosts and
  cross-origin/cross-site browser requests are rejected. These checks do not
  authenticate users or stop non-browser clients.
- One process owns one CPU worker. Defaults are **two active POST requests** and
  **60 accepted POSTs per minute across the whole service**. Excess work receives
  503/429 with Retry-After before its body is buffered. Read routes remain available.
  Tune `CONTOUR_MAX_ACTIVE_POSTS` (1–8) and `CONTOUR_POSTS_PER_MINUTE` (1–600)
  only after checking memory/CPU capacity.
- Bodies are capped at 60 MB and uploads at 30 seconds. Existing image, pixel,
  graph and operation limits apply. Cancellation stops between native operations;
  it cannot interrupt an OpenCV/CImg/ZXing call already executing.
- The launcher uses one Uvicorn worker with a 16-connection/task cap. More workers
  or replicas multiply these in-memory limits; there is no distributed coordination.
- No accounts, tenant storage or distributed abuse controls are implemented. Use
  hosting-platform traffic protection for an internet-facing service.

## Verification

`.github/workflows/ci.yml` runs Python/JavaScript tests on Linux, builds the Docker
image and starts it with a read-only filesystem and resource caps. It checks
public health, Host policy, non-root identity and an actual native CImg operation.
It does not deploy. Locally, the policy and cancellation tests run without live AI.

The Linux x86-64 container build and smoke test passed on September 20, 2026 for
commit `b633506` in [GitHub Actions run 35493226806](https://github.com/hamaker-png/contour-vision/actions/runs/35493226806).
That run also passed the Linux Python and JavaScript suites. This verifies the
container setup; it does not establish a deployed Render service or production load capacity.
This development machine has no Docker runtime, so the container execution happened in CI.
Rebuild and rerun tests when updating the pinned runtime dependencies.

References: [Render Docker services](https://render.com/docs/docker),
[Render environment variables](https://render.com/docs/environment-variables),
[Uvicorn resource settings](https://www.uvicorn.org/settings/), and
[GitHub Pages scope](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site).
