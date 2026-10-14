# Spike S0.3 — FACEIT demo through a browser extension

Question: can a browser extension hand the demo of a FACEIT match to Untraded from the player's own session, without the official Downloads API?

How FACEIT serves demos (observed 2026-10-14): the match page's "Watch demo" button runs a Cloudflare Turnstile check, then `POST /api/download/v2/demos/download-url` exchanges the public `resource_url` (`demos-*.backblaze.faceit-cdn.net/cs2/<id>.dem.zst`) for a presigned Backblaze B2 URL valid for 299 s, which the browser downloads.

The extension never calls FACEIT and never touches the page. The player clicks "Watch demo" and passes FACEIT's checks as usual; the extension only sees the download the browser starts (`downloads` permission) and, if it is a FACEIT CS2 demo, posts its URL to the local server. The server must start downloading within the URL's 5-minute validity.

## Run

1. Start the local server (127.0.0.1:8765):

   ```bash
   just spike-faceit-server
   ```

2. Load the unpacked extension from `extension/`:
   - Firefox: `about:debugging#/runtime/this-firefox` → *Load Temporary Add-on…* → `extension/manifest.json` (removed when Firefox closes);
   - Chrome: `chrome://extensions` → *Developer mode* → *Load unpacked* → `extension/`.
3. Open a FACEIT CS2 match room and click "Watch demo". The extension badge shows `OK` when the server accepted the URL, `ERR` when the server is unreachable.

The server downloads the demo to `out/<id>.dem.zst` (ignored by Git), checks that it decompresses to a CS2 demo, and appends one line to `out/ingest.jsonl`: delay, remaining URL validity, size, download time. Signed URLs are never written to disk. Findings go to `RAPPORT.md`.
