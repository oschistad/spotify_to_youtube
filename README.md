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
3. Fill in a name and description, then set the **Redirect URI** to `http://localhost:8888/callback`.
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
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

Alternatively, export the variables directly in your shell:

```bash
export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret
export SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

### 4. YouTube Music auth setup

`ytmusicapi` authenticates using a `browser.json` file generated from your browser's request headers.

Run the following and follow the on-screen instructions (paste headers from a YouTube Music request):

```bash
ytmusicapi browser
```

This creates `browser.json` in your current directory. Keep this file private — it contains your session credentials.

> **How to get the headers:** Open [music.youtube.com](https://music.youtube.com) in your browser, open DevTools (F12), go to the Network tab, reload the page, click on any request to `music.youtube.com`, and copy the request headers as instructed by the `ytmusicapi browser` prompt.

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
