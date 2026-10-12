# 🤝 Contributing

First off — thanks for taking the time to contribute! 🎉

This project is open-source under AGPLv3. Anyone is welcome to open PRs, file issues, suggest improvements.

## 🐛 Found a bug? Have an idea?

1. **Search existing issues** first to avoid duplicates.
2. **Open a new issue** with:
   - Clear title
   - Reproduction steps (what you did, what happened, what you expected)
   - Logs (redact your `BOT_TOKEN`!)
   - Environment (OS, Python version, ffmpeg version)

## 🛠 Setting up for development

### Prerequisites

- Python 3.10+
- FFmpeg (`apt install ffmpeg`, `brew install ffmpeg`, or `winget install Gyan.FFmpeg`)
- A Telegram bot token for testing (create a separate test bot, don't share your prod token)

### One-command setup

```bash
git clone https://github.com/<your-username>/narezkashorts.git
cd narezkashorts
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
# source venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
pip install -r requirements-dev.txt   # tests, linters
cp .env.example .env
# Add your test bot's BOT_TOKEN to .env

# Verify it works
python config.py        # should print settings
python bot.py            # should start polling
```

### Running tests

```bash
pytest tests/ -v
```

We aim for ~70% code coverage. New features must come with tests.

### Code style

- **Black** for formatting (line length 100)
- **Ruff** for linting (configured in `pyproject.toml`)
- **Type hints** for all new code
- **Docstrings** for public functions in NumPy style

```bash
# Format and lint before committing
black .
ruff check --fix .
```

## 🔧 Submitting a Pull Request

1. **Fork** the repo
2. Create a branch: `git checkout -b feat/my-cool-feature`
3. Make your changes
4. Add tests in `tests/`
5. Run `pytest tests/` and ensure all pass
6. Run `black .` and `ruff check --fix .`
7. Commit with conventional messages: `feat: ...`, `fix: ...`, `docs: ...`
8. Push & open a PR

PR review checklist:
- [ ] Tests pass locally
- [ ] New code has type hints
- [ ] Public APIs have docstrings
- [ ] No secrets in code or commits
- [ ] `.env` is not committed

## 💬 Communication

- Issues: prefer GitHub Issues
- Discussions: GitHub Discussions
- For sensitive matters (security, commercial licensing): see `SECURITY.md`

## 📜 License

By contributing, you agree that your contributions will be licensed under the project's AGPLv3 license.
