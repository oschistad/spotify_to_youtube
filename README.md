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
authenticated, and it uses OAuth (device flow), which works well over SSH.

**a. Create a Google OAuth client**

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create (or pick) a project.
2. Under **APIs & Services → Library**, enable the **YouTube Data API v3**.
3. Under **APIs & Services → Credentials**, click **Create Credentials → OAuth client ID**.
4. Choose application type **TV and Limited Input devices**.
5. Under **APIs & Services → OAuth consent screen**, set **User type** to **External**, then scroll to **Test users** and add the Google account you use for YouTube Music. (Your app stays in "Testing" status — that's fine for personal use, but only test users can authorize it. Skipping this causes an "app has not been approved" error.)
6. Copy the resulting **Client ID** and **Client Secret** into your `.env`:

   ```
   YT_OAUTH_CLIENT_ID=your_google_oauth_client_id
   YT_OAUTH_CLIENT_SECRET=your_google_oauth_client_secret
   ```

**b. Authorise your YouTube Music account**

```bash
uv run ytmusicapi oauth --client-id "$YT_OAUTH_CLIENT_ID" --client-secret "$YT_OAUTH_CLIENT_SECRET"
```

This prints a URL and a code — open the URL on any device, sign in with the
Google account tied to your YouTube Music, and enter the code. It writes
`oauth.json` to the current directory. Keep this file private.

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
