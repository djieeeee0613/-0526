# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Anonymous real-time chat app (AnyChat) backed by AWS API Gateway WebSocket + Lambda. The frontend is a single self-contained HTML file served from GitHub Pages.

**GitHub repo:** `samsonchen/ai_course_2`
**Frontend URL:** `https://samsonchen.github.io/ai_course_2/anychat.html`

## Frontend (`webui/anychat.html`)

Single-file vanilla HTML/CSS/JS — no build step, no dependencies. Deploy by pointing GitHub Pages at the `webui/` directory.

**WebSocket endpoint config:**
- Set `window.ANYCHAT_WS_ENDPOINT` before the `<script>` block (e.g. in a separate `config.js`)
- Or pass `?ws=wss://...` as a query parameter for quick local testing
- Default fallback: `wss://default.execute-api.us-west-2.amazonaws.com/prod`

**Connection URL format:** `wss://{endpoint}?callsign={callsign}`

**Incoming message shapes:**
```ts
{ type: "message"; callsign: string; text: string; timestamp: string }
{ type: "system";  event: "user_joined"|"user_left"; callsign: string; timestamp: string }
```

**Outgoing message shape:**
```ts
{ action: "sendMessage"; text: string }
```

**Reconnection:** exponential backoff (2 s → 4 s → 8 s → 16 s → 30 s), max 5 attempts, then shows a manual reconnect button.

## Backend (see `documents/`)

| Doc | Contents |
|-----|----------|
| `01-system-architecture.md` | Overall AWS architecture |
| `02-api-specification.md` | API Gateway WebSocket routes |
| `03-aws-configuration.md` | AWS resource config |
| `04-lambda-connect-spec.md` | `$connect` handler |
| `05-lambda-disconnect-spec.md` | `$disconnect` handler |
| `06-lambda-send-message-spec.md` | `sendMessage` handler |
| `07-frontend-design.md` | Frontend design spec |
