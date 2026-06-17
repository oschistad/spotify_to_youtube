# Spotify to YouTube Music Artist Migration

Migrates your Spotify followed artists to YouTube Music subscriptions.

## Requirements

- Python 3.8+
- A Spotify developer app
- A YouTube Music account (logged in via a browser)

## Setup

### 1. Install dependencies

```bash
uv sync
```

Optionally install `python-dotenv` to use a `.env` file:

```bash
uv add python-dotenv
```

### 2. Spotify app setup

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create app**.
3. Fill in a name and description, then set the **Redirect URI** to `http://127.0.0.1:8888/callback`.
4. After creation, note your **Client ID** and **Client Secret** from the app settings.

### 3. Configure Spotify credentials

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
```

Alternatively, export the variables directly in your shell:

```bash
export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret
```

### 4. YouTube Music auth setup

Searching YouTube Music needs no auth. Only the **subscribe** step is
authenticated.

> **Note:** As of mid-2026, YouTube made a server-side change that breaks
> OAuth for write actions (subscribe, like, library edits) — see
> [sigma67/ytmusicapi#676](https://github.com/sigma67/ytmusicapi/issues/676)
> and [#921](https://github.com/sigma67/ytmusicapi/issues/921). Browser
> auth (cookie-based) is currently the only method that works for
> `subscribe_artists`, so that's what this project uses by default.

**Browser auth (current default)**

```bash
uv run ytmusicapi browser
```

Follow the on-screen instructions: open [music.youtube.com](https://music.youtube.com)
in your browser (use a private/incognito window for longer-lived cookies),
open DevTools (F12) → Network tab, reload, click any request to
`music.youtube.com`, and paste the request headers as instructed by the
prompt. This writes `browser.json` to the current directory. Keep this file
private — it contains your session credentials, and they expire periodically
(re-run this command if subscribing starts failing).

**Brand accounts**

If `subscribe_artists` still fails with `HTTP 400: Bad Request` after a
fresh `browser.json`, your YouTube Music account may be a **brand
account** (a separate channel identity layered on your Google account) —
a known cause of this error. Go to
[myaccount.google.com/brandaccounts](https://myaccount.google.com/brandaccounts),
select the account, and copy the ID from the URL
(`https://myaccount.google.com/b/<user_id>/`). Set it in `.env`:

```
YT_BRAND_ACCOUNT_ID=<user_id>
```

**OAuth (fallback, currently broken upstream for subscribe)**

The codebase also supports OAuth via `get_ytmusic_auth_client_oauth()` in
`migrate.py`, kept around for when the upstream issue is fixed. To use it:
swap `get_ytmusic_auth_client()` to call `get_ytmusic_auth_client_oauth()`
instead of `get_ytmusic_auth_client_browser()`, then:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/), create/pick a project, enable **YouTube Data API v3**.
2. Under **Credentials**, create an **OAuth client ID** of type **TV and Limited Input devices**.
3. Under **OAuth consent screen**, set **User type** to **External** and add your account under **Test users**.
4. Put the client ID/secret in `.env` as `YT_OAUTH_CLIENT_ID` / `YT_OAUTH_CLIENT_SECRET`.
5. Run:
   ```bash
   uv run ytmusicapi oauth --client-id "$YT_OAUTH_CLIENT_ID" --client-secret "$YT_OAUTH_CLIENT_SECRET"
   ```

## Running the script

### Full migration

```bash
python migrate.py
```

### Dry run (find matches without subscribing)

```bash
python migrate.py --dry-run
```

### Test with a small batch

```bash
python migrate.py --limit 10
```

### Combine options

```bash
python migrate.py --dry-run --limit 20
```

## How it works

1. Authenticates with Spotify via OAuth (opens a browser window on first run; token cached in `.cache`).
2. Fetches all artists you follow on Spotify, handling pagination automatically.
3. For each artist, searches YouTube Music using the artist name.
   - Prefers an exact name match.
   - Falls back to the first search result if no exact match is found.
4. Subscribes to matched YouTube Music channels (unless `--dry-run` is set).
5. Prints a summary showing matched, subscribed, and not-found artists.

## Notes

- Artists not found on YouTube Music are listed at the end of the run.
- Errors during subscription (e.g., already subscribed, network issues) are logged and the script continues.
- The Spotify OAuth token is cached in `.cache` — delete it to force re-authentication.
