# CLI

Install the World Labs CLI and use it from a terminal or coding agent.

Install and connect the World Labs CLI:

```sh
npm install -g @worldlabsai/cli && worldlabs setup
```

Use the World Labs Developer API from a terminal, Codex, or Claude Code.
The CLI uses your project's API key and billing. It requires Node.js 24 or newer.

## Install and sign in

```sh
npm install -g @worldlabsai/cli && worldlabs setup
```

On Windows, run these commands in Command Prompt.

Setup opens the API keys page. Create a key for your project and paste it into
the hidden terminal prompt. Keep the key out of agent chats. Setup can also
install the World Labs skill for Codex or Claude Code.

Verify your connection and list the task names supported by the CLI:

```sh
worldlabs auth status
worldlabs tasks list
```

A successful status check confirms asset access. Individual tasks can require
additional key permissions or beta access.

## Use the agent skill (`SKILL.md`)

The npm package includes one `skills/worldlabs/SKILL.md` with task descriptions,
an upload/submit/result example, and essential authentication and retry guidance.
To install the skill separately from login, run the command for your agent:

```sh
worldlabs skills install --client codex
```

```sh
worldlabs skills install --client claude-code
```

The installer prints the skill directory. Open `SKILL.md` there to read the
instructions your agent receives. Start a new agent session to load the skill,
then ask it to use World Labs for your task. The agent reads the instructions,
writes request JSON, and runs the CLI through its terminal tools.

Before choosing model inputs, calculating cameras, or combining tasks, read
[How To Use Atlas](/docs/how-to-use-atlas). The skill links to this maintained
guide; detailed model documentation is not copied into the npm package.

## Submit JSON and save results

Upload your image:

```sh
worldlabs assets upload photo.jpg --json
```

Put the returned asset ID in `request.json`:

```json
{
  "frames": [{ "imageAsset": { "assetId": "<uploaded-asset-id>" } }]
}
```

Submit the file and wait for the result:

```sh
worldlabs tasks run images2PosedRGBD --request request.json --wait --json > result.json
```

Use `--request -` to read JSON from standard input. For example, stream the
same file into the command:

```sh
worldlabs tasks run images2PosedRGBD --request - --wait --json < request.json > result.json
```

Results go to stdout. Progress messages and the retry key go to stderr, so
`result.json` contains only the result. If submission is interrupted, retry
with the original request and `--idempotency-key <printed-key>`.

A wait timeout stops the local command without cancelling server work. Resume
with `worldlabs operations wait <operation-id> --json`. Check a completed
operation for `error` before using its `response`. Download output assets with
`worldlabs assets download <asset-id> --out result.png`.

## Credentials

Login saves the API key in a plaintext file in your user configuration directory.
`worldlabs auth status` reports its location. Use `WLT_API_KEY` for automation;
it takes precedence over saved credentials.

`worldlabs auth logout` removes the local key. To disable it everywhere,
revoke it on the API keys page.

See [Authentication](/docs/authentication) for key permissions and
[Errors and retries](/docs/errors) for recovering interrupted requests.