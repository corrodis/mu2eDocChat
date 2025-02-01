# Slack Bot

## Installation
For the slack based chat interface, additional dependencies are needed that can be installed with
```bash
pip install -e ".[slack]"
```
(or drop the "-e" if not in deval mode)

## Environment Variables:
The following additional settings are needed (the settings listed in install.md are also needed)
Required:
  - MU2E_SLACK_BOT_TOKEN
  - MU2E_SLACK_APP_TOKEN
Optional:
  - MU2E_SLACK_CHANNEL: if a non-default ("llm_test") slack channel is required

## Run the Bot
I recommend to do this in a screen session:
```bash
mu2e-slack
```
