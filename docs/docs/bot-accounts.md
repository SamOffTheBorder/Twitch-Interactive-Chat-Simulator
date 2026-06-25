---
sidebar_position: 4
---

# Bot Accounts

Each bot account needs its own Twitch account and an OAuth token with `chat:read` and `chat:edit` scopes.

## Creating accounts

Create separate Twitch accounts for each bot — one account per viewer persona. The number of accounts equals the number of simultaneous viewers the bot simulates.

## Generating tokens

Use **[twitchtokengenerator.com](https://twitchtokengenerator.com)** to generate a token for each account:

1. Go to [twitchtokengenerator.com](https://twitchtokengenerator.com)
2. Select only these two scopes:
   - `chat:read`
   - `chat:edit`
3. Click **Generate Token**
4. Log in as the bot account when Twitch prompts you
5. Copy the **Access Token**

Paste it into `TWITCH_TOKENS` in your `.env`, comma-separated:

```
TWITCH_TOKENS=token_account1,token_account2,token_account3
```

Repeat for each bot account. Use a different browser or incognito window per account so sessions don't conflict.

:::tip Why twitchtokengenerator?
Tokens generated here with only `chat:read` + `chat:edit` scopes last significantly longer than standard OAuth flow tokens and don't require running any local scripts or keeping a server running.
:::

## Adding more accounts later

1. Create the new Twitch account
2. Go to [twitchtokengenerator.com](https://twitchtokengenerator.com) and generate a token logged in as that account
3. Append the token to `TWITCH_TOKENS` in `.env`
4. Restart the bot — it auto-detects the new account

## Token expiry

If a bot stops connecting with an authentication error, that token has expired. Just go back to [twitchtokengenerator.com](https://twitchtokengenerator.com), log in as that account again, and replace the old token in `.env`.
