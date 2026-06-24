---
sidebar_position: 4
---

# Bot Accounts

Each bot account needs its own Twitch account and an OAuth token with `chat:read` and `chat:edit` scopes.

## Creating accounts

Create separate Twitch accounts for each bot. Use different email addresses. The number of accounts = the number of simultaneous viewer personas.

## Generating tokens

The project includes a token generator that handles the OAuth flow automatically:

```bash
python token_gen.py
```

It will:
1. Open a browser window to Twitch's login page
2. You log in as the bot account
3. The token is printed to your terminal

Paste the token into `TWITCH_TOKENS` in your `.env`, comma-separated:

```
TWITCH_TOKENS=token_for_account1,token_for_account2,token_for_account3
```

Run the script once per account. Use a private/incognito window for each one so sessions don't overlap.

:::tip
The number of viewers is automatically set to however many tokens you have — no other config needed.
:::

## Adding more accounts later

1. Create the Twitch account
2. Run `python token_gen.py` and log in as the new account
3. Append the token to `TWITCH_TOKENS` in `.env`
4. Restart the bot

## Token expiry

Tokens generated via the built-in OAuth flow don't expire unless the account password changes or the app authorization is revoked. If a bot stops connecting, regenerate its token.
