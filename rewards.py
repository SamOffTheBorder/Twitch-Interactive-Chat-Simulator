"""
Channel-point redemptions via Twitch's internal GQL endpoint.
This is the same API the Twitch website uses when you click a reward —
no broadcaster OAuth needed, just a viewer's chat token.

NOTE: Twitch requires a Client-Integrity JWT for GQL mutations (added Sept 2022).
We fetch one from gql.twitch.tv/integrity before each redemption attempt.
Redemptions also silently return null when the channel is offline (rewards are
auto-paused by Twitch) — the fallback to chat is intentional in that case.
"""
import json
import threading
import uuid
import urllib.request

import config

_GQL_URL = "https://gql.twitch.tv/gql"
# Twitch's own web client ID — publicly known, used by every third-party Twitch tool
_WEB_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

_broadcaster_id_cache: str = ""
_reward_details: dict[str, dict] = {}  # reward_id → {title, cost}
_lock = threading.Lock()


def _get_integrity_token(token: str) -> str:
    """Fetch a Client-Integrity JWT — required by Twitch for GQL mutations since Sept 2022."""
    headers = {
        "Client-ID": _WEB_CLIENT_ID,
        "Content-Type": "application/json",
        "Origin": "https://www.twitch.tv",
        "Referer": "https://www.twitch.tv/",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        "https://gql.twitch.tv/integrity",
        data=b"{}",
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("is_bad_bot_token"):
                print("[Rewards] Warning: integrity check flagged this token as a bot")
            return data.get("token", "")
    except Exception as e:
        print(f"[Rewards] Integrity token fetch failed: {e}")
        return ""


def _gql(payload: dict, token: str, client_id: str = _WEB_CLIENT_ID, integrity: str = "") -> dict:
    import urllib.error
    body = json.dumps(payload).encode()
    headers = {
        "Client-ID": client_id,
        "Content-Type": "application/json",
        "Origin": "https://www.twitch.tv",
        "Referer": "https://www.twitch.tv/",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if integrity:
        headers["Client-Integrity"] = integrity
    req = urllib.request.Request(_GQL_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        raise Exception(f"HTTP {e.code}: {detail}")


def _get_broadcaster_id() -> str:
    """Look up the broadcaster's numeric ID — public data, no auth needed."""
    global _broadcaster_id_cache
    with _lock:
        if _broadcaster_id_cache:
            return _broadcaster_id_cache
        try:
            data = _gql(
                {
                    "query": "query($login:String!){user(login:$login){id}}",
                    "variables": {"login": config.TWITCH_CHANNEL},
                },
                token="",  # anonymous — user lookup is public
            )
            uid = data["data"]["user"]["id"]
            _broadcaster_id_cache = uid
            print(f"[Rewards] Broadcaster ID: {uid}")
            return uid
        except Exception as e:
            print(f"[Rewards] Could not get broadcaster ID: {e}")
            return ""


def discover() -> None:
    """Query channel rewards via GQL and populate reward IDs in config.

    - Custom rewards: searched by keyword for TTS.
    - Highlight My Message: a Twitch automaticReward (type SEND_HIGHLIGHTED_MESSAGE)
      with a channel-specific UUID — fetched from automaticRewards, not customRewards.
    """
    tokens_to_try: list[str] = [""] + list(config.TWITCH_TOKENS)
    query = {
        "query": """
        query($login:String!){
          user(login:$login){
            channel{
              communityPointsSettings{
                automaticRewards{
                  id type defaultCost minimumCost isEnabled
                }
                customRewards{
                  id title cost isEnabled
                }
              }
            }
          }
        }
        """,
        "variables": {"login": config.TWITCH_CHANNEL},
    }
    last_err = ""
    for token in tokens_to_try:
        try:
            data = _gql(query, token)
            settings = data["data"]["user"]["channel"]["communityPointsSettings"]

            # Built-in automatic rewards (Highlight My Message, etc.)
            auto_rewards = settings.get("automaticRewards") or []
            for r in auto_rewards:
                rtype = r.get("type", "")
                cost = r.get("minimumCost") or r.get("defaultCost") or 0
                title = rtype.replace("_", " ").title()
                print(f"  [auto] {rtype} — enabled={r.get('isEnabled')} cost={cost} id={r['id']}")
                _reward_details[r["id"]] = {"title": title, "cost": cost}
                if not config.HIGHLIGHT_REWARD_ID and rtype == "SEND_HIGHLIGHTED_MESSAGE":
                    config.HIGHLIGHT_REWARD_ID = r["id"]
                    print(f"  ↳ Highlight My Message → {r['id']} (cost={cost})")

            # Custom rewards (TTS etc.)
            custom_rewards = settings.get("customRewards") or []
            print(f"[Rewards] Found {len(custom_rewards)} custom + {len(auto_rewards)} automatic reward(s)")
            for r in custom_rewards:
                tl = r["title"].lower()
                print(f"  • {r['title']!r} — {r['cost']} pts (id={r['id']})")
                _reward_details[r["id"]] = {"title": r["title"], "cost": r["cost"]}
                if not config.TTS_REWARD_ID and "text" in tl and "speech" in tl:
                    config.TTS_REWARD_ID = r["id"]
                    print(f"  ↳ matched as TTS reward")

            if not config.HIGHLIGHT_REWARD_ID:
                print("[Rewards] Warning: Highlight My Message not found in automaticRewards — is it enabled on the channel?")
            return
        except Exception as e:
            last_err = str(e)
    print(f"[Rewards] Discovery failed: {last_err}")


def redeem(token: str, reward_id: str, message: str = "") -> bool:
    """Redeem a channel point reward on behalf of the viewer whose token is provided."""
    if not token or not reward_id:
        return False
    bid = _get_broadcaster_id()
    if not bid:
        return False
    # Look up cost and title — Twitch's GQL mutation requires them as non-null fields
    details = _reward_details.get(reward_id, {})
    cost = details.get("cost", 0)
    title = details.get("title", "")

    # Fetch integrity token — Twitch requires it for GQL mutations since Sept 2022
    integrity = _get_integrity_token(token)
    try:
        data = _gql(
            {
                "operationName": "RedeemCustomReward",
                "variables": {
                    "input": {
                        "channelID": bid,
                        "rewardID": reward_id,
                        "message": message,
                        "cost": cost,
                        "title": title,
                        "transactionID": str(uuid.uuid4()),
                    }
                },
                "query": """
                mutation RedeemCustomReward($input:RedeemCommunityPointsCustomRewardInput!){
                  redeemCommunityPointsCustomReward(input:$input){
                    redemption{ id status reward{ id title } }
                    error{ code }
                  }
                }
                """,
            },
            token,
            integrity=integrity,
        )
        gql_data = (data.get("data") or {})
        result = gql_data.get("redeemCommunityPointsCustomReward") or {}
        if not result:
            # Log raw response so we can diagnose what Twitch actually returned
            raw = json.dumps(data)[:400]
            print(f"[Rewards] GQL returned no redemption data. Raw: {raw}")
            return False
        if result.get("error"):
            print(f"[Rewards] Redemption error: {result['error']['code']}")
            return False
        redemption = result.get("redemption")
        if redemption:
            title = redemption.get("reward", {}).get("title", reward_id)
            print(f"[Rewards] Redeemed {title!r} — status: {redemption.get('status')}")
            return True
        raw = json.dumps(data)[:400]
        print(f"[Rewards] Redemption returned null (channel offline or reward paused?). Raw: {raw}")
        return False
    except Exception as e:
        print(f"[Rewards] GQL error: {e}")
        return False
