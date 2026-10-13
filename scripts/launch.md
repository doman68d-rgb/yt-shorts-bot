# 🚀 Launch Plan: posting templates & checklist

This is your public launch playbook. Use it carefully — first impressions matter.

## ⏱ Timeline

| Day | Task |
|---|---|
| Day 0 | Code freeze. Tag a release. |
| Day 0 | Record 60-sec GIF demo. |
| Day 0 | Deploy demo bot on a free tier (Railway/Fly.io) for live testing. |
| Day 0 | Push to GitHub. |
| Day 1 | Product Hunt (Tuesday/Wednesday 12:01 AM PT) |
| Day 1 | Hacker News ("Show HN: ...") |
| Day 2 | Reddit r/Python, r/TelegramBots, r/SideProject (staggered) |
| Day 2-3 | Reddit r/InternetIsBeautiful, r/Entrepreneur |
| Day 3-4 | Twitter thread (7-10 tweets) |
| Day 5 | Telegram channels @python_scripts, @telegram_bots |
| Day 5 | VC.ru post (for Russian-speaking audience) |
| Day 7-14 | Respond to ALL comments/issues within 24h |

---

## 📝 Post templates

### Hacker News ("Show HN")

**Title:** Show HN: I built a Telegram bot that turns YouTube videos into Shorts with AI

**Text:**
```
Hey HN,

I've been working on a Telegram bot that takes a YouTube link and turns it
into vertical Shorts automatically.

It uses:
- faster-whisper for transcription
- an LLM (OpenAI-compatible API) to pick the most engaging moments
- ffmpeg to cut and crop to 9:16

Fully open-source (AGPL-3.0), self-hostable via Docker, and ships with
50+ tests in CI.

The "smart" highlight picker was the trickiest part — getting the LLM to
return clean JSON with valid timestamps, especially for short videos where
the requested clip length is longer than the video itself.

Looking for feedback on:
1. The transcript-to-LLM prompt (in services/highlights.py)
2. UX in Telegram (commands vs inline buttons vs both)
3. What features would make this actually useful for content creators?

GitHub: https://github.com/doman68d-rgb/yt-shorts-bot
Demo bot: @@demo_yt_shorts_bot
```

### Reddit r/Python

**Title:** [Project] NarezkaShorts — Telegram bot that uses Whisper + LLM to cut YouTube videos into Shorts

**Text:**
```
I just open-sourced a Telegram bot that:
1. Downloads a YouTube video
2. Transcribes it with faster-whisper
3. Asks an LLM to pick the most engaging 45-second moments
4. Cuts them into vertical 1080x1920 clips
5. Sends them to you in Telegram with a live progress bar

Stack: aiogram, yt-dlp, faster-whisper, ffmpeg, OpenAI API.

Highlights:
- Fully Dockerized (one command to deploy)
- Pluggable LLM (works with OpenAI, OpenRouter, Ollama)
- 50+ tests in CI
- AGPL-3.0 + commercial dual-license

GitHub: https://github.com/doman68d-rgb/yt-shorts-bot

What's next: I'm thinking of adding subtitles-on-clip as an option.
What features would you want?
```

### Reddit r/TelegramBots

**Title:** Made a Telegram bot that uses Whisper to pick best moments from YouTube videos

**Text:**
```
Link your YouTube video → bot returns 3 vertical Shorts ready for TikTok.

Demo: @@demo_yt_shorts_bot

GitHub: https://github.com/doman68d-rgb/yt-shorts-bot
```

### Reddit r/SideProject

**Title:** I built a Telegram bot that turns YouTube videos into Shorts with AI

**Text (story format):**
```
I was getting tired of manually re-cutting my podcast episodes into clips.
After 3 weekends of work, I built a Telegram bot that does it for me.

Drop a YouTube link → wait 3 minutes → get back 3 vertical clips.

The "wait 3 minutes" is annoying, but it's still 10x faster than doing it
manually in Premiere. And the LLM picks moments I'd actually have picked
myself.

Open-sourced it last weekend with the LLM call being optional (it works
without an API key, just picks random clips).

GitHub: https://github.com/doman68d-rgb/yt-shorts-bot

Curious what other "I shouldn't have to do this manually" tasks would
benefit from this kind of automation.
```

### Twitter thread

**Tweet 1/7:**
```
I open-sourced a Telegram bot that turns YouTube videos into TikTok-ready
Shorts with one message.

Drop a link → wait 3 min → get back 3 vertical clips.

Under the hood: faster-whisper for transcription + LLM for highlight
selection + ffmpeg for cropping.

GitHub: https://github.com/doman68d-rgb/yt-shorts-bot 🧵👇
```

**Tweet 2/7:**
```
The interesting part was the LLM prompt.

The LLM gets the transcript chunked into 30-second windows with timestamps.
It picks N most "engaging" L-second moments.

The trick: enforcing valid JSON output without markdown wrappers.
```

**Tweet 3/7:**
```
Why this is cool:
1. Pluggable LLM — OpenAI / OpenRouter / local Ollama all work
2. With no API key, falls back to random clips (still useful)
3. One ffmpeg pass for the cut + crop + scale (fast)
4. Per-user settings (clip count, length, strategy)
```

**Tweet 4/7:**
```
The bot has a live progress bar in Telegram.

One message updates every ~1.5s showing:
- Download progress (speed + ETA)
- Whisper transcription progress
- Highlight selection
- Per-clip ffmpeg progress
- Send progress
```

**Tweet 5/7:**
```
Architecture:
- aiogram 3.x for the bot
- yt-dlp for downloads
- faster-whisper for ASR
- ffmpeg for everything video
- httpx for LLM API
- Dockerized with healthcheck

Modular package layout → easy to extend.
```

**Tweet 6/7:**
```
License: AGPL-3.0 + commercial dual.

Why?
- Free for personal/small use
- Companies that want to embed in closed-source products need a
  commercial license

This is the same model GitLab, Sentry, etc. use.
```

**Tweet 7/7:**
```
Try it:
- Demo: @@demo_yt_shorts_bot
- GitHub: https://github.com/doman68d-rgb/yt-shorts-bot
- Docker: `git clone && docker compose up`

If you make something cool with it, DM me!

PRs welcome. Especially:
- More languages
- Subtitle overlays
- Multi-platform support
```

### VC.ru (Russian)

**Title:** Как я сделал Telegram-бота, который сам режет YouTube в Shorts через AI

**Text (со ссылками на GitHub и демо-бота):**
```
Привет! Я тут запилил опенсорсный бот, который берёт ссылку на YouTube
и возвращает 3 готовых вертикальных клипа для TikTok / Shorts / Reels.

Под капотом:
- faster-whisper для распознавания речи
- LLM (через OpenAI/OpenRouter/Ollama) для выбора ярких моментов
- ffmpeg для нарезки + кадрирования в 9:16
- Всё в Docker, деплой одной командой

Технические интересности:
- Прогресс-бар в реальном времени в одном Telegram-сообщении
- Плагин-стратегия: можно с LLM, можно без (fallback на random)
- 50+ тестов в CI

Бот уже работает: @@demo_yt_shorts_bot
Код на GitHub: https://github.com/doman68d-rgb/yt-shorts-bot

Буду рад звёздам ⭐ и pull-реквестам. Особенно интересует:
- мультиязычность (сейчас работает на любых языках, но промпт LLM на английском)
- наложение субтитров
- поддержка Rutube / VK
```

---

## 🎯 Checklist before posting

- [ ] GitHub repo is **public**
- [ ] README is in **English** with quick-start
- [ ] `.env.example` is committed
- [ ] LICENSE is committed (AGPL-3.0)
- [ ] All 50+ tests pass in CI
- [ ] Bot runs in fresh Docker (test `docker compose build && docker compose up -d`)
- [ ] GIF demo recorded (60 sec, no sound, big text)
- [ ] Demo bot working on a free tier (Railway / Fly.io)
- [ ] Topics/tags set on GitHub
- [ ] GitHub repo description: "Telegram bot that turns YouTube videos into Shorts using AI"
- [ ] Commit history is clean (no `asdfg`, no `temp`)

## 🎯 Posting day checklist

- [ ] Online all day
- [ ] Respond within 1 hour to all comments
- [ ] Don't delete/edit posts after first hour
- [ ] Don't be defensive about criticism
- [ ] If something's broken in your demo bot → fix it immediately
