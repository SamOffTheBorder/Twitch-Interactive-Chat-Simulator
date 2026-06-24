"""
Channel-point redemptions via Twitch's internal GQL endpoint.
This is the same API the Twitch website uses when you click a reward —
no broadcaster OAuth needed, just a viewer's chat token.
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
_lock = threading.Lock()


def _gql(payload: dict, token: str, client_id: str = _WEB_CLIENT_ID) -> dict:
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
    """Query the channel's custom rewards via GQL and populate reward IDs in config.
    Also sets the Highlight My Message ID — it's a Twitch built-in with a fixed ID."""
    # Highlight My Message is a built-in reward with a known fixed Twitch reward ID
    if not config.HIGHLIGHT_REWARD_ID:
        config.HIGHLIGHT_REWARD_ID = "highlight-message"
        print("[Rewards] Highlight My Message → built-in (highlight-message)")

    # Channel rewards are public — try without auth first, then with a viewer token
    tokens_to_try: list[str] = [""] + list(config.TWITCH_TOKENS)
    query = {
        "query": """
        query($login:String!){
          user(login:$login){
            channel{
              communityPointsSettings{
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
            channel = data["data"]["user"]["channel"]
            reward_list = channel["communityPointsSettings"]["customRewards"]
            print(f"[Rewards] Found {len(reward_list)} reward(s):")
            for r in reward_list:
                tl = r["title"].lower()
                print(f"  • {r['title']!r} — {r['cost']} pts (id={r['id']})")
                if not config.TTS_REWARD_ID and "text" in tl and "speech" in tl:
                    config.TTS_REWARD_ID = r["id"]
                    print(f"  ↳ matched as TTS reward")
                if not config.HIGHLIGHT_REWARD_ID and "highlight" in tl:
                    config.HIGHLIGHT_REWARD_ID = r["id"]
                    print(f"  ↳ matched as Highlight reward")
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
    # Use the user's own registered app client_id so it matches the token
    client_id = config.TWITCH_CLIENT_ID or _WEB_CLIENT_ID
    try:
        data = _gql(
            {
                "operationName": "RedeemCustomReward",
                "variables": {
                    "input": {
                        "channelID": bid,
                        "rewardID": reward_id,
                        "message": message,
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
            client_id=client_id,
        )
        result = data.get("data", {}).get("redeemCommunityPointsCustomReward", {})
        if result.get("error"):
            print(f"[Rewards] Redemption failed: {result['error']['code']}")
            return False
        redemption = result.get("redemption")
        if redemption:
            title = redemption.get("reward", {}).get("title", reward_id)
            print(f"[Rewards] Redeemed {title!r} — status: {redemption.get('status')}")
            return True
        return False
    except Exception as e:
        print(f"[Rewards] GQL error: {e}")
        return False
