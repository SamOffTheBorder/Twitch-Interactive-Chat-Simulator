## ADDED Requirements

### Requirement: Configurable transcriber model list
The system SHALL read a `TRANSCRIBER_MODELS` environment variable (comma-separated list of Whisper model names, e.g. `base.en,small.en,medium.en`) to determine which models to load. If unset, it SHALL default to `base.en,small.en,medium.en`.

#### Scenario: Default models
- **WHEN** `TRANSCRIBER_MODELS` is not set in `.env`
- **THEN** the ensemble loads `base.en`, `small.en`, and `medium.en` Whisper models

#### Scenario: Single model configured
- **WHEN** `TRANSCRIBER_MODELS=base.en`
- **THEN** the system loads only `base.en` and behaves identically to the previous single-model transcriber

#### Scenario: Custom model set
- **WHEN** `TRANSCRIBER_MODELS=small.en,medium.en`
- **THEN** only those two models are loaded and compete per audio chunk

### Requirement: Parallel model inference
For each incoming audio chunk, the system SHALL run all configured Whisper models concurrently in separate threads. No model SHALL block another — all run simultaneously on the same PCM data.

#### Scenario: Three models on one chunk
- **WHEN** an audio chunk arrives and three models are configured
- **THEN** all three models begin transcribing the chunk at the same time in separate threads

#### Scenario: One model errors
- **WHEN** one model raises an exception during transcription
- **THEN** its result is discarded and the remaining model results are still used for selection

### Requirement: Best-result selection
After all models complete, the system SHALL select the best result using the following priority:
1. Discard any result where Whisper's `no_speech_prob` exceeds 0.6
2. Among remaining results, select the one with the most words
3. If all results are discarded (all above threshold), output nothing for that chunk

#### Scenario: All models agree
- **WHEN** all models return similar text with low no_speech_prob
- **THEN** the result with the most words is selected and placed on the text queue

#### Scenario: One model detects silence, others do not
- **WHEN** one model returns high no_speech_prob and the others return low no_speech_prob with text
- **THEN** the high-prob result is discarded and the best of the remaining is selected

#### Scenario: All models detect silence
- **WHEN** all models return no_speech_prob above 0.6
- **THEN** no text is placed on the queue and nothing is sent to the responder

### Requirement: Startup model loading log
The system SHALL print the name and load status of each Whisper model during startup, so the user knows which models are active.

#### Scenario: All models load successfully
- **WHEN** the ensemble transcriber starts
- **THEN** it prints "[Transcriber] Loading models: base.en, small.en, medium.en" and "[Transcriber] All models ready"

#### Scenario: Model load fails
- **WHEN** a model name in `TRANSCRIBER_MODELS` is invalid or fails to load
- **THEN** the system SHALL log a warning "[Transcriber] Failed to load <model>: <error>" and continue with the remaining models

### Requirement: Per-chunk selection log
The system SHALL print which model's result was selected and why, so the streamer can see transcription quality in the terminal.

#### Scenario: Best result selected
- **WHEN** a chunk is transcribed and a winner is selected
- **THEN** the system prints "[Transcript] <winner_model>: <raw_text> → <cleaned_text>"

#### Scenario: Chunk discarded
- **WHEN** all results are discarded due to high no_speech_prob
- **THEN** the system prints "[Transcript] Chunk discarded (all models: no speech detected)"
