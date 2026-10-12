# 🔒 Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| main    | ✅ Active dev      |
| 0.1.x   | ✅ Initial release  |

## Reporting a Vulnerability

⚠️ **Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, email `security@<your-domain>.com` (TODO: setup) or DM a maintainer privately. We will respond within 48 hours.

When reporting, please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We follow responsible disclosure:
1. **Day 0:** You report the issue
2. **Day 1–7:** We triage, confirm, and develop a fix
3. **Day 7–14:** We coordinate disclosure timing with you
4. **After fix:** Public advisory with credit to the reporter

### What we care about

- **Token leakage** — anyone able to read `.env` should not be able to read Telegram creds
- **ffmpeg command injection** — we use shell=True; inputs must be sanitized
- **Path traversal** — file operations must validate paths
- **DOS via huge video files** — files in `downloads/` are user-controlled
- **Arbitrary URL fetching** — bot uses yt-dlp which can hit any URL

### Recent advisories

(none yet)

## Best practices for users running your own instance

- **Never commit `.env`** — `.gitignore` covers this
- **Use environment variables** in production, not files
- **Mount `downloads/` and `clips/` carefully** — anyone with access can read all user videos
- **Run the bot as a non-root user** — Docker image already does this
- **Keep `yt-dlp` updated** — they fix YouTube anti-bot changes frequently
- **Set `--max-filesize` on yt-dlp** to prevent large downloads
