# Contributing

Thank you for your interest in improving Miktos Agentic System.

## Development Setup

1. Create and activate a virtual environment.
2. Install dependencies with development extras:
   - pip install -e .[dev]
3. Run checks:
   - pytest -q
   - ruff check .

## Branching and Commits

- Create a branch from main for each feature or fix.
- Use clear commit messages in imperative mood.
- Keep pull requests focused and small.

## Pull Request Checklist

- Tests pass locally.
- Lint passes locally.
- Documentation is updated when behavior changes.
- No secrets or credentials are included.

## Reporting Bugs

Please include:

- What you expected to happen
- What happened instead
- Steps to reproduce
- Relevant logs and environment details

## Security Issues

Do not open public issues for security vulnerabilities.
Follow the process in SECURITY.md.
