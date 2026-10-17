# Quickstart

Make your first Marble 2 API request and wait for its result.

Make a complete Marble 2 beta request in three steps: create a project-scoped
API key, provide an image, and wait for the returned operation.

> Marble 2 is in beta. Use the endpoint names and schemas in this documentation,
> not older Marble or World API examples.

For task selection, scene data, and model guidance, read [How To Use Atlas](/docs/how-to-use-atlas).

Claude Code and Codex: run World Labs commands directly in your own terminal
with the CLI. Install the CLI, then install the bundled `SKILL.md` for the
client you are running (`claude-code` for Claude Code or `codex` for Codex).
The skill includes task instructions and request examples.

```sh
npm install -g @worldlabsai/cli
worldlabs skills install --client claude-code
worldlabs skills install --client codex
```

Run `worldlabs auth login` in the agent's terminal so the user can enter their
API key privately, then verify setup with `worldlabs auth status` and
`worldlabs tasks list`. See [CLI](/docs/cli) for command examples.

For a TypeScript or web app, follow the [Web Quickstart](/docs/web-quickstart)
to install the client, pose an image, and generate a new view on your server.

## 1. Create an API key

Open [Developers](/developers), select **API keys**, and create a key with:

- `tasks.create`
- `operations.read`
- `assets.create`
- `assets.read`

Copy the secret when it appears. It cannot be shown again. The key belongs to
the project selected in the platform sidebar, so its assets, operations, usage,
and spend limits stay isolated from other projects.

## 2. Configure the client

Configure the current beta API root and API key in the server environment:

```bash
export WLT_API_BASE_URL="https://api.atlas-beta.worldlabs.ai/api/v2"
export WLT_API_KEY="wl_live_replace_with_your_key"
```

Confirm that the API host is reachable:

```bash
curl --fail-with-body --silent --show-error \
  "$WLT_API_BASE_URL/health"
```

The health route does not require an API key. It separates connectivity issues
from authentication or request-shape problems.

## 3. Submit a task

`images2PosedRGBD` estimates a camera and depth buffer for each input image.
This example uses a directly fetchable 1280-pixel JPEG of a _torii_ gate by
[Daniel Erlandson on Pexels](https://www.pexels.com/photo/scenic-view-of-red-torii-gate-at-lake-ashi-31252468/).
Pexels marks the image as
[free to use](https://www.pexels.com/license/).

```bash
IMAGE_URL="https://images.pexels.com/photos/31252468/pexels-photo-31252468.jpeg?auto=compress&cs=tinysrgb&w=1280"
SUBMISSION_FILE="images2-posed-submission.json"
IDEMPOTENCY_KEY="quickstart-$(date +%s)-$$-${RANDOM:-0}"
REQUEST=$(jq -cn --arg url "$IMAGE_URL" '{
  frames: [{imageAsset: {url: $url}}],
  targetResolution: [1280, 720]
}')

: > "$SUBMISSION_FILE"
HTTP_STATUS=$(curl --silent --show-error \
  --retry 5 --retry-delay 2 --retry-max-time 30 \
  --output "$SUBMISSION_FILE" --write-out '%{http_code}' \
  --request POST "$WLT_API_BASE_URL/tasks:images2PosedRGBD" \
  --header "WLT-Api-Key: $WLT_API_KEY" \
  --header "Content-Type: application/json" \
  --header "Idempotency-Key: $IDEMPOTENCY_KEY" \
  --data-binary "$REQUEST") || HTTP_STATUS=${HTTP_STATUS:-000}

if [[ "$HTTP_STATUS" != 2* ]]; then
  printf 'Submission failed (HTTP %s):\n' "$HTTP_STATUS" >&2
  jq . "$SUBMISSION_FILE" 2>/dev/null || cat "$SUBMISSION_FILE"
elif WLT_OPERATION_ID=$(jq -er '.id' "$SUBMISSION_FILE"); then
  export WLT_OPERATION_ID
  printf 'Submitted operation %s\n' "$WLT_OPERATION_ID"
  printf 'Saved submission to %s\n' "$SUBMISSION_FILE"
else
  printf 'Submission did not return an operation ID:\n' >&2
  jq . "$SUBMISSION_FILE" 2>/dev/null || cat "$SUBMISSION_FILE"
fi
```

The command generates a fresh idempotency key, checks the HTTP response, exports
`WLT_OPERATION_ID`, and saves the full submission response. Submitting a task
does not wait for the model to finish.

## 4. Check the result

Run this command whenever you want to check the operation. It makes one
non-blocking request and then returns control to your terminal, so it is safe to
rerun. If you opened a new terminal, it restores the operation ID from the
saved submission file.

```bash
SUBMISSION_FILE="images2-posed-submission.json"
if [[ -z "${WLT_OPERATION_ID:-}" ]]; then
  WLT_OPERATION_ID=$(jq -er '.id' "$SUBMISSION_FILE")
  export WLT_OPERATION_ID
fi

OPERATION_FILE="operation-$WLT_OPERATION_ID.json"
: > "$OPERATION_FILE"
HTTP_STATUS=$(curl --silent --show-error \
  --output "$OPERATION_FILE" --write-out '%{http_code}' \
  --request GET "$WLT_API_BASE_URL/operations/$WLT_OPERATION_ID" \
  --header "WLT-Api-Key: $WLT_API_KEY") || HTTP_STATUS=${HTTP_STATUS:-000}

if [[ "$HTTP_STATUS" == 404 ]]; then
  printf 'Operation is not readable yet. Retry shortly; report the ID if this persists.\n'
elif [[ "$HTTP_STATUS" != 2* ]]; then
  printf 'Operation check failed (HTTP %s):\n' "$HTTP_STATUS" >&2
  jq . "$OPERATION_FILE" 2>/dev/null || cat "$OPERATION_FILE"
else
  jq '{id, done, state: .metadata.state, error}' "$OPERATION_FILE"
  if jq -e '.done == true and .error == null' "$OPERATION_FILE" >/dev/null; then
    OUTPUT_FILE="images2-posed-response-$WLT_OPERATION_ID.json"
    jq -e '.response' "$OPERATION_FILE" | tee "$OUTPUT_FILE"
    printf 'Saved task output to %s\n' "$OUTPUT_FILE"
  elif jq -e '.error != null' "$OPERATION_FILE" >/dev/null; then
    jq '.error' "$OPERATION_FILE" >&2
  else
    printf 'The task is still running. Rerun this check later.\n'
  fi
fi
```

When the task completes, the check prints and saves `operation.response`. Each
result contains the normalized image, its estimated camera,
`depth.depthAsset` (linear-depth EXR), and `depth.confidenceAsset`.

A successful submission should produce a readable operation. A brief `404` can
be retried, but a persistent `404` is an API issue: keep the operation ID for
support rather than submitting the same work again.

## Where to go next

- Read [Images to posed RGBD](/docs/images-to-posed-images) before using
  multi-view inputs or known cameras.
- Use [Assets](/docs/assets) for private inputs instead of public URLs.
- Implement the production polling and retry rules in
  [Operations](/docs/operations) and [Errors and retries](/docs/errors).
- Open the [API reference](/docs/api-reference) for endpoint schemas and examples.