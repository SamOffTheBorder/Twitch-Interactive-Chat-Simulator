## ADDED Requirements

### Requirement: Reward discovery on startup
The system SHALL call `rewards.discover()` during startup in `main.py`, before any bot accounts connect. After discovery, the system SHALL print a summary of resolved reward IDs.

#### Scenario: TTS reward discovered
- **WHEN** `main.py` starts and `rewards.discover()` finds a reward matching "Text-to-Speech"
- **THEN** `config.TTS_REWARD_ID` is populated and the system prints "[Rewards] TTS → <id>"

#### Scenario: TTS reward not found
- **WHEN** `rewards.discover()` completes and `config.TTS_REWARD_ID` is still blank
- **THEN** the system SHALL print "[Rewards] TTS_REWARD_ID not resolved — TTS will fall back to chat"

#### Scenario: Highlight reward set to built-in
- **WHEN** `rewards.discover()` runs and `config.HIGHLIGHT_REWARD_ID` is blank
- **THEN** the system SHALL set it to "highlight-message" (built-in Twitch reward) and print "[Rewards] Highlight My Message → built-in (highlight-message)"

### Requirement: Structured redemption failure logging
When `rewards.redeem()` returns `False`, the calling code SHALL log a warning before falling back to regular chat. The log SHALL include which reward type failed and the masked token (last 6 characters only).

#### Scenario: TTS redemption fails
- **WHEN** `tts_sender._fire()` calls `rewards.redeem()` and it returns `False`
- **THEN** the system SHALL print "[TTS] Redemption failed (reward_id=<id>, token=…<last6>) — falling back to chat" before sending as regular chat

#### Scenario: Highlight redemption fails
- **WHEN** `responder._do_highlight()` calls `rewards.redeem()` and it returns `False`
- **THEN** the system SHALL print "[Highlight] Redemption failed (reward_id=<id>, token=…<last6>) — falling back to chat" before sending as regular chat

#### Scenario: Reward ID blank at fire time
- **WHEN** `rewards.redeem()` is called with an empty `reward_id`
- **THEN** it SHALL return `False` immediately without making a network request, and the caller logs the fallback with reward_id=<blank>
