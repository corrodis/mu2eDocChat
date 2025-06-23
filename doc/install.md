# Instalaltion and Setup

## Python environment
It might be worth to start with a clean python environment. I don't think that's really needed though.
```bash
python -m venv --clear .venv
. .venv/bin/activate
```

## Development mode
Run the following in the base folder of the cloned repository (only needs to be done ones)
```bash
pip install -e .
```

## Environment Variables
The package requires several environment variables to be set for accessing various services. These are managed using a `.env` file in the repository root. They can be overwritten by setting them as system envrionment variables.

1. Copy the example environment file to create your own:
```bash
cp .env.example .env
```

Edit `.env` and fill in your information:
- docdb authentication: FNAL SSO credientials, needed for all docdb access
- Anthropic and OpenAI API keys: needed for the use of these LLM APIs
- Slack bot details: only needed for the slack bot interface

*Important*: Never commit your `.env` file to version control as it contains sensitive credentials. The `.env` file is already included in `.gitignore` to prevent accidental commits.
