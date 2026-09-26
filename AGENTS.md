# AGENTS.md

## Current implementation state — Phases 0 through 8 complete; Phase 9 in progress

The repository is `pi-voice-ai` inside the parent workspace `RaspberryPI5`; execute
Git commands from the clone.
The origin URL is `https://github.com/crismoraes/pi-voice-ai.git`. Phase 0 produced
the initial commits on `main`, pushed them to `origin/main` without rewriting
remote history, and was approved for the `v0.1.0` milestone.

Windows inspection confirmed Windows 11 Home 64-bit, PowerShell 5.1, OpenSSH 9.5p2,
Git 2.49.0.windows.1 and VS Code 1.136.1. See README.md and Curso_Step.md for the
actual observations, commands and environment permission issues encountered.

An existing ED25519 pair dedicated to another project was preserved. The user
created the project pair at the default Windows OpenSSH path. The public key
fingerprint was verified locally and in the Pi user's `authorized_keys`; never
record the private key, its passphrase, or public-key contents in this repository.

Key authentication is validated for the Linux user `cristiano`. The Windows SSH
config contains the alias `voicepi`, with `IdentitiesOnly yes`, and remote commands
work through it. The target is a Raspberry Pi 5 Model B Rev 1.0 named `home-ai`,
running Debian GNU/Linux 13 (trixie), aarch64. README.md and Curso_Step.md contain
the sanitized baseline. Do not publish its private IP address in repository files.
The Pi clone is at `/home/cristiano/pi-voice-ai`.

README.md contains reproduction procedures; Curso_Step.md separates observed
results from work still to be demonstrated. Phase 1 reads `APP_HOST`, `APP_PORT`
and `LOG_LEVEL` from `.env`; other template values remain future placeholders and
engine names are not permanent selections.

Phase 0 validation passed and the user authorized `v0.1.0` and continuation into
Phase 1. Preserve SSH password access. Phase 1 may implement only the application
foundation described below; do not start WebRTC, STT, TTS, VAD, audio processing,
or OpenAI API integration yet.

Phase 1 local foundation now includes:

* Python 3.11+ package metadata in `pyproject.toml`
* pinned FastAPI, Uvicorn and pydantic-settings direct dependencies
* `GET /health` returning exactly `{"status":"ok"}` without external dependencies
* environment-backed host, port and log-level settings
* JSON logs for application and Uvicorn events
* a meaningful ASGI health test
* idempotent Raspberry Pi bootstrap with package presence checks
* clean-tree, fast-forward-only deployment with compile and test gates
* a rendered systemd service running as the invoking non-root user
* start, stop, restart and health-check scripts

The local Windows validation used Python 3.12.0. `pytest` passed, Python bytecode
compilation passed, all Bash scripts passed `bash -n`, and a real Uvicorn process
returned the expected health JSON. The OpenAI key in the ignored local `.env` is
not read or used by Phase 1. Do not copy that file through Git.

The Pi clone now exists at `/home/cristiano/pi-voice-ai`. Bootstrap detected all
system tools, created a Python 3.13 virtual environment, installed the ARM64
dependencies, and created an ignored `.env` with mode 600 from the safe template.
Remote pytest and compileall passed. A temporary Uvicorn process returned the
expected health JSON over the LAN and was then terminated. The Git tree is clean.
The systemd unit is installed, enabled and active. The first deployment exposed a
startup race: curl ran before Uvicorn opened port 8000. Subsequent inspection showed
the service healthy. `healthcheck.sh` now retries for up to 20 seconds. Never request,
store or transmit sudo passwords in repository files, commands or documentation.

The corrected script passed on the Pi. Final Phase 1 checks showed `active/running`,
`enabled`, `ExecMainStatus=0`, `NRestarts=0`, no error-priority journal entries, a
clean Pi Git tree, and the expected health response locally and over the LAN. The
enabled unit is configured for boot, but an actual Pi reboot has not been performed
as part of this phase. Phase 1 is complete; do not begin Phase 2 without explicit
user authorization.

The user authorized Phase 2. The current local implementation adds `aiortc 1.15.0`,
browser assets, HTTP offer/answer signaling, peer lifecycle management and audio
track loopback. It does not add VAD, STT, LLM, TTS or USB audio. The browser and
server use the same FastAPI origin; no CORS configuration is required.

The signaling API is:

* `POST /api/webrtc/offer` with an SDP offer, returning SDP answer and peer ID
* `DELETE /api/webrtc/peers/{peer_id}` for explicit cleanup

Every received audio track is attached to the same peer connection as an outbound
track for the Phase 2 loopback. Peer connections are closed on failure, explicit
disconnect and application shutdown. Log events include track receipt, state
changes, `WEBRTC_CONNECTED`, negotiation failure and `WEBRTC_DISCONNECTED`.

Phase 2 tests use two real aiortc peers and require one audio frame to pass through
ICE, DTLS and SRTP. All three current tests pass on Windows Python 3.12 and Raspberry
Pi Python 3.13 ARM64. The Pi installed binary wheels for aiortc, PyAV, cryptography
and SRTP without native compilation.

Browser microphone access uses direct Uvicorn HTTPS during development. Windows
trusts a local mkcert CA. The certificate covers the local Pi hostname and private
address and expires in December 2028. Certificate, TLS key and CA files live outside
the repository and were installed in the Pi user's private config directory with
directory mode 700 and key mode 600. The app reads `TLS_CERT_FILE` and
`TLS_KEY_FILE`; `healthcheck.sh` switches to HTTPS, connects locally with
`--resolve`, and validates the hostname with `TLS_CA_FILE`. Never publish certificate
private keys or mkcert's root CA private key.

The Pi service is active and enabled on HTTPS port 8443. The Windows health request,
web page request and `scripts/live_webrtc_check.py` all passed with certificate
validation. The live check negotiated ICE, DTLS and SRTP, received a returned audio
frame and explicitly removed the peer; journald recorded the full connection and
cleanup lifecycle without warnings. An initial Pi health check failed because it
used the `127.0.0.1` URL while the certificate covered the hostname. It now uses the
Pi hostname for TLS validation and resolves it to loopback for the local request.
The user completed the browser test with real microphone and speaker hardware and
confirmed that the returned voice audio worked correctly. Phase 2 is complete at
version `0.2.0`. The user later provided explicit authorization for Phase 3.

Peer deletion is intentionally idempotent. The physical browser test exposed a race
where the connection-state callback removed a closed peer before the browser sent
its DELETE request. Both the first cleanup request and later repeats return 204.

The user authorized Phase 3. Version `0.3.0` implements manual utterance
capture and local offline STT. `MediaRelay` splits the inbound WebRTC track between
the optional loopback and a 16 kHz mono capture consumer. The `SpeechToText`
abstraction is currently implemented by sherpa-onnx 1.13.8 with the multilingual
Whisper Tiny int8 encoder and decoder. NumPy is pinned to 2.4.6 for Python 3.11+
compatibility.

The model is downloaded outside Git by `scripts/download_stt_model.sh`. Its archive
is approximately 110 MB, extracts to 245 MB, and is verified against the recorded
SHA-256 before extraction. Bootstrap invokes the idempotent downloader. The model
loads lazily, so `/health` does not require model files or inference initialization.

Transcription endpoints are:

* `POST /api/webrtc/peers/{peer_id}/transcription/start`
* `POST /api/webrtc/peers/{peer_id}/transcription/finish`

The finish response contains text, audio seconds, processing seconds and RTF.
Inference runs with `asyncio.to_thread` behind a decode lock so it does not block
WebRTC event handling. Audio is not persisted or logged. Capture is limited to the
configured duration. VAD, partial transcripts, automatic endpointing, LLM and TTS
remain outside Phase 3.

Six tests pass on Windows Python 3.12 and Pi Python 3.13 ARM64. The Pi installed
binary wheels and loaded the real model. An English reference produced the correct
text with RTF 0.171 (1.134 s inference for 6.625 s audio). The live deployment test
also sent 6.539 s over WebRTC and completed local inference in 1.147 s, RTF 0.175.
The user tested several real Portuguese utterances in the browser. The last long
sample was understandable and preserved its subject and sentence sequence, with
some word errors expected from Whisper Tiny. Its 18.06 s of audio were decoded in
3.346 s, RTF 0.185. Phase 3 is complete at version `0.3.0`.

The user authorized Phase 4. Version `0.4.0` adds a replaceable
`LanguageModel` abstraction backed by the OpenAI Responses API. After local STT,
the browser sends only the transcript to `POST /api/assistant/responses` and reads
SSE events containing text deltas and completion timing. The API key remains on the
server. Requests use `store=false`, a 300-token default limit and a single-request
lock. Prompts and response text are not logged.

The default model is configurable and currently set to `gpt-6-luna` for low latency
and cost. Nine tests pass on Windows and Raspberry Pi ARM64, including
provider-independent streaming. A minimal real API call using the ignored local
`.env` succeeded. The deployed HTTPS endpoint also streamed a real response with
1.520 s to first text and 1.683 s total. Logs contain only model, character counts
and timing. The user completed the physical browser flow with a Portuguese question.
STT processed 7.08 s in 0.98 s, RTF 0.14. The model understood the question despite
a minor transcription error, produced the correct historical answer, started text
in 1.97 s and completed in 2.85 s. Phase 4 is complete at version `0.4.0`.
The final deployed check after the plain-text instruction returned no Markdown,
with 2.216 s to first text and 2.393 s total.

The user authorized Phase 5. Version `0.5.0` adds the replaceable
`TextToSpeech` abstraction backed by sherpa-onnx 1.13.8 and the Brazilian Portuguese
Piper voice `vits-piper-pt_BR-jeff-medium`. The model archive is about 64 MB, its
installed directory is about 82 MB, and `scripts/download_tts_model.sh` verifies its
recorded SHA-256 before extracting it under the ignored `models/` directory.

`POST /api/webrtc/peers/{peer_id}/speech` synthesizes text locally and queues its
audio on the session's outbound track. Piper's 22,050 Hz mono float samples are
converted to 48 kHz signed PCM with PyAV and sent through WebRTC. The same track
sends microphone loopback when explicitly enabled and silence otherwise. Loopback
is now controlled server-side through `PUT /api/webrtc/peers/{peer_id}/loopback` so
the browser can always play assistant speech.

Eleven tests pass on Windows and Raspberry Pi ARM64. The real model generated 3.036
seconds of audio in 0.707 seconds, RTF 0.233. The deployed HTTPS check generated
3.882 seconds in 0.795 seconds, RTF 0.205, and delivered 185 audible frames over
WebRTC to Windows. The service is active, health is good and recent TTS/WebRTC logs
contain no errors. The user completed the physical browser test with a 5.50-second
Portuguese question. STT took 0.79 seconds, RTF 0.14; first LLM text arrived in
0.97 seconds and completed in 1.13 seconds. The correct Washington, D.C. answer
produced 2.79 seconds of audible speech in 0.56 seconds, RTF 0.20. Phase 5 is
complete at version `0.5.0`.

The user authorized and completed Phase 6. Version `0.6.0` adds automatic utterance
segmentation with the official sherpa-onnx Silero VAD model and a transport-neutral
`ConversationManager`. The VAD receives the existing 16 kHz mono stream, uses a
0.5 threshold, 0.3-second minimum speech and 0.8-second ending silence. Its 643,854
byte model is downloaded outside Git and checked against the recorded SHA-256.

Each automatic turn runs local STT, streams an OpenAI text response, runs local TTS
and queues the synthesized samples on the peer's WebRTC output. An SSE stream reports
speech boundaries, transcript metrics, text deltas, LLM timing, TTS timing and ready
state to the browser. Manual capture remains available when automatic mode is off.

Conversation history is isolated by peer, limited to six user/assistant pairs and
deleted on disconnect. Only text context is sent to OpenAI; audio stays local. While
a turn is being processed and played, microphone frames are ignored to prevent echo
feedback. Barge-in remains Phase 7 work and is not enabled.

Fourteen tests pass on Windows and Raspberry Pi ARM64. The real VAD loaded on both
platforms and segmented synthesized Portuguese speech. A deployed two-turn check
finished with four history messages, delivered two spoken responses over WebRTC and
produced 463 audible frames on Windows without log errors. Synthetic speech exposed
expected Whisper Tiny word errors, while the second response still proved the first
recognized turn was present in context. Physical browser validation detected
5.00-second and 5.39-second utterances automatically. STT took 0.95 and 1.03 seconds,
first text arrived in 1.32 and 0.94 seconds, and local TTS took 0.34 seconds for each
response. The same peer's history advanced through 4, 6, 8 and the configured
12-message limit. Every turn completed, the peer closed normally and the service
remained active without journal errors. Phase 6 is complete at version `0.6.0`.
Phase 7 began only after the user's explicit authorization.

The user authorized Phase 7. Version `0.7.0` keeps VAD active while an automatic
turn is processing or playing. New detected speech cancels the current task, clears
queued assistant audio and continues collecting that same utterance for the next
turn. The `interrupted` SSE event reports whether processing or playback was stopped
and how much queued audio was discarded. `ENABLE_BARGE_IN` controls the behavior.
Sixteen tests pass on Windows and Raspberry Pi, including a five-second queued
response interrupted during playback followed by a second completed turn. The live
deployed WebRTC check interrupted playback with 1.573 seconds queued, completed the
new turn, received 140 audible frames on Windows and produced no errors in that run.
The physical browser test interrupted a 36.351-second answer about Moses with 28.194
seconds still queued, then completed the new request about Jesus. The new 2.54-second
utterance took 0.60 seconds for STT, 1.60 seconds to first text and 4.67 seconds to
synthesize 23.61 seconds of speech. Two earlier OpenAI calls returned no text, so the
conversation pipeline now retries once only for an empty completion. Phase 7 is
complete at `0.7.0`. Do not begin Phase 8 without explicit user authorization.

The user authorized Phase 8. Version `0.8.0` adds Whisper model-prefix discovery,
INT8/FP32 selection, unbuffered WebRTC capture relay and sentence-sized TTS streaming.
The first audio chunk is queued while later chunks are still synthesized, and
`tts_chunk` reports playback progress. Baseline Raspberry Pi 5 medians favor three
threads: Tiny INT8 STT took about 0.324 seconds for 1.467 seconds of audio; short TTS
took about 0.182 seconds versus 0.218 with two threads. The official Whisper Base
benchmark model occupies 433 MiB versus 245 MiB for Tiny. Model comparison, deployed
results favored Tiny INT8: median 0.325 seconds versus 0.426 for Tiny FP32, 0.719 for
Base INT8 and 0.969 for Base FP32 on 1.467 seconds of audio. The Base model also made
more errors and its temporary files were removed. A 240-character TTS ceiling gave
about 0.605 seconds to first audio and 2.449 seconds total for the long benchmark.
Deployed warm turns queued first audio in 0.257 and 0.362 seconds. Parallel startup
preloading reduced the observed cold first-audio time from 1.652 to 0.586 seconds.
Seventeen tests pass on Windows and Pi. In the physical browser validation, 3.31
seconds of speech were transcribed in 0.55 seconds. An 802-character response was
split into 12 chunks and produced 43.75 seconds of continuous speech. The first
audio was queued in 0.462 seconds while full synthesis took 7.323 seconds, confirming
generation and playback overlap. The service remained active and the turn had no
logged errors. Phase 8 is complete at `0.8.0`. Do not begin Phase 9 without explicit
user authorization.

The user authorized Phase 9 with a USB microphone and speaker already connected.
The Raspberry Pi detects one bidirectional P10S USB Audio interface for capture and
playback at the stable ALSA name `plughw:CARD=P10S,DEV=0`; the service user belongs
to the `audio` group. Version `0.9.0.dev0` introduces an ALSA adapter built on
`arecord` and `aplay`. It feeds 16 kHz mono PCM into the existing Silero VAD and
transport-independent conversation pipeline, and streams Piper chunks to one
playback process. `AUDIO_MODE=webrtc` remains the default. USB mode is selected by
`AUDIO_MODE=usb`, with separate capture/playback device settings and a configurable
capture period. Before capture starts, the adapter restores the configured ALSA
playback and capture levels through `amixer`; mixer failures are logged without
blocking devices that expose different control names. USB barge-in defaults off
until physical echo behavior is validated.
The first physical USB conversation passed after troubleshooting the P10S: playback
volume was initially zero, a diagnostic `aplay` process remained open, and the
capture endpoint required `usbreset 1234:5684`. Native capture then returned 192,000
bytes for one second at 48 kHz stereo. A physical 3.244-second turn took 0.540 seconds
for STT; first audio was queued in 0.191 seconds and 18.472 seconds of speech played
in five chunks. The service returned to ready and remained active. `Curso_Step.md`
ends with a FAQ and troubleshooting chapter built from the real project incidents;
continue adding new observed incidents there. Do not publish `v0.9.0` or begin Phase
10 until the remaining USB behavior, including the desired barge-in policy, is decided.

## Project Goal

Build a low-latency voice assistant running primarily on a Raspberry Pi 5.

The Raspberry Pi 5 is the runtime target.

Development is performed remotely from a Windows laptop using:

* Visual Studio Code
* Codex
* PowerShell
* SSH
* Git
* GitHub

The agent should configure, deploy, run, inspect, debug, test, document, version, and maintain the Raspberry Pi remotely over SSH whenever possible.

The initial audio interface will be a web browser using WebRTC.

Later, the application must also support a USB microphone and USB speaker connected directly to the Raspberry Pi without changing the core:

* STT
* LLM
* TTS
* conversation logic

The project must be designed so that it can be recreated in the future using the repository documentation.

---

# 1. Core Project Principle

This repository must become a complete record of how the project was built.

The combination of:

```text
AGENTS.md
README.md
Curso_Step.md
CHANGELOG.md
source code
scripts
configuration examples
Git history
GitHub releases
```

should make it possible to rebuild the project from a clean Raspberry Pi installation in the future.

Documentation is part of the implementation.

A feature is not considered fully complete until its relevant documentation has been updated.

---

# 2. Architecture

Initial architecture:

```text
Browser on Windows / phone
        |
        | WebRTC audio
        v
Raspberry Pi 5
        |
        +--> VAD
        |
        +--> Local STT
        |
        +--> OpenAI text LLM
        |
        +--> Local TTS
        |
        +--> WebRTC audio response
        |
        v
Browser speaker
```

Future architecture:

```text
USB microphone
        |
        v
Raspberry Pi 5
        |
        +--> VAD
        +--> STT
        +--> OpenAI LLM
        +--> TTS
        |
        v
USB speaker
```

The core processing pipeline must not depend directly on WebRTC or USB audio.

Use abstractions such as:

* AudioInput
* AudioOutput
* SpeechToText
* LanguageModel
* TextToSpeech
* ConversationManager

---

# 3. Primary Goals

Prioritize:

1. Low latency
2. Streaming wherever practical
3. Natural voice interaction
4. Barge-in support
5. Local STT
6. Local TTS
7. OpenAI used primarily for text LLM inference
8. Modular architecture
9. Remote administration
10. Reliable automatic startup
11. Reproducibility
12. Complete technical documentation
13. Git-based version control
14. Educational documentation for a future Udemy course

Avoid unnecessary complexity.

Do not send audio to OpenAI unless explicitly requested.

The default architecture should send text to OpenAI.

---

# 4. Raspberry Pi Target

Target hardware:

* Raspberry Pi 5
* Raspberry Pi OS 64-bit
* ARM64
* Local network connection
* SSH enabled

The Raspberry Pi will initially run without dedicated microphone or speaker hardware.

The browser on the Windows laptop or mobile device will provide:

* microphone input
* speaker output

Later the Raspberry Pi will use:

* USB microphone
* USB speaker

---

# 5. Development Environment

Primary development machine:

```text
Windows laptop
```

Primary tools:

```text
Visual Studio Code
Codex
PowerShell
OpenSSH
Git
GitHub
```

Runtime target:

```text
Raspberry Pi 5
```

The Windows laptop is the development and control environment.

The Raspberry Pi is the execution environment.

---

# 6. Remote Development Rules

All Raspberry Pi installation and configuration should be performed remotely using SSH whenever practical.

Before making changes on the Pi:

1. Verify SSH connectivity.
2. Verify hostname.
3. Verify OS.
4. Verify architecture.
5. Verify available RAM.
6. Verify available disk space.
7. Verify Python version.
8. Verify network connectivity.
9. Verify repository state.
10. Verify currently running application version.

Example checks:

```bash
uname -a
uname -m
cat /etc/os-release
python3 --version
free -h
df -h
hostname
hostname -I
git status
git log -1 --oneline
```

Never assume packages are installed.

Check before installing.

---

# 7. SSH Configuration

Do not hardcode passwords.

Prefer SSH keys.

The preferred SSH alias for this project is:

```text
voicepi
```

Expected Windows SSH usage:

```powershell
ssh voicepi
```

The project must never contain:

* SSH passwords
* private SSH keys
* OpenAI API keys
* Wi-Fi passwords
* GitHub personal access tokens
* other secrets

---

# 8. Phase 0 SSH Bootstrap Is Mandatory

Phase 0 must include a complete SSH setup between the Windows development machine and the Raspberry Pi.

This setup is both:

1. a technical requirement for remote development, and
2. an educational step that must be documented for the future Udemy course.

The agent must guide the user through the SSH setup safely and in a way that can be reproduced later.

---

# 9. Check for Existing SSH Keys on Windows

Before generating a new SSH key, first inspect the Windows SSH directory.

Use:

```powershell
Get-ChildItem $env:USERPROFILE\.ssh
```

Look for files such as:

```text
id_ed25519
id_ed25519.pub
```

If an existing ED25519 key pair is available and appropriate for this project, do not automatically overwrite or replace it.

Never overwrite an existing private key.

If no suitable key exists, generate one.

---

# 10. Generate SSH Key on Windows

Preferred key type:

```text
ED25519
```

Command:

```powershell
ssh-keygen -t ed25519 -C "pi-voice-ai"
```

Preferred default location:

```text
C:\Users\<WINDOWS_USER>\.ssh\id_ed25519
```

This produces:

```text
id_ed25519
id_ed25519.pub
```

Meaning:

```text
id_ed25519
PRIVATE KEY

id_ed25519.pub
PUBLIC KEY
```

The private key must remain on the Windows development machine.

Never copy the private key to:

* Raspberry Pi
* USB drive unless explicitly needed for backup and securely protected
* Git repository
* GitHub
* documentation
* cloud storage without proper encryption

For the Raspberry Pi setup, only the public key should be transferred.

---

# 11. SSH Key Passphrase

If the user creates a passphrase for the SSH key, explain that:

* the passphrase protects the private key
* Windows ssh-agent may be used to avoid retyping it constantly
* the passphrase itself must never be stored in the repository

Do not force a passphrase choice automatically.

---

# 12. Copy Public SSH Key Using a USB Drive

If direct password-based SSH is not yet available, the supported bootstrap method is:

```text
Windows
   ↓
copy id_ed25519.pub
   ↓
USB drive
   ↓
Raspberry Pi
```

Copy only:

```text
id_ed25519.pub
```

to the USB drive.

Do not copy:

```text
id_ed25519
```

as part of the normal setup.

The README and Curso_Step.md must explicitly explain the difference between the public and private key.

---

# 13. Install Public Key on Raspberry Pi

On the Raspberry Pi, create the SSH directory if necessary:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
```

Locate the USB drive and the transferred public key.

Then append the public key to:

```text
~/.ssh/authorized_keys
```

Example:

```bash
cat /path/to/usb/id_ed25519.pub >> ~/.ssh/authorized_keys
```

Then set permissions:

```bash
chmod 600 ~/.ssh/authorized_keys
```

Verify that the file exists:

```bash
ls -la ~/.ssh
```

Optionally inspect the authorized key fingerprints or contents.

Do not expose private keys.

---

# 14. Avoid Duplicate Authorized Keys

Before blindly appending a key, the agent should check whether that same public key is already present.

Avoid adding duplicate entries to:

```text
~/.ssh/authorized_keys
```

If scripting this later, use idempotent logic.

---

# 15. Do Not Disable Password Authentication Yet

During Phase 0:

Do not disable SSH password authentication automatically.

First verify that public-key authentication works reliably.

The safe sequence is:

```text
Install public key
        ↓
Open a new SSH session
        ↓
Verify key authentication
        ↓
Close and reopen
        ↓
Verify again
```

Only after stable key-based access is confirmed should password authentication hardening even be considered.

Do not modify:

```text
/etc/ssh/sshd_config
```

to disable password authentication during the initial setup unless explicitly requested later.

---

# 16. Initial SSH Test from Windows

Before creating the SSH alias, test using the Raspberry Pi IP address or hostname.

Example:

```powershell
ssh <pi-user>@<raspberry-pi-ip>
```

If the connection succeeds, verify:

```powershell
ssh <pi-user>@<raspberry-pi-ip> "hostname"
```

Then verify multiple commands:

```powershell
ssh <pi-user>@<raspberry-pi-ip> "hostname && uname -m && python3 --version"
```

---

# 17. Configure Windows SSH Alias

After direct SSH works, configure:

```text
C:\Users\<WINDOWS_USER>\.ssh\config
```

Preferred entry:

```text
Host voicepi
    HostName <raspberry-pi-ip-or-hostname>
    User <pi-user>
    IdentityFile ~/.ssh/id_ed25519
```

If another private key filename is used, reference that key instead.

Do not place passwords in this file.

---

# 18. Test SSH Alias

Test:

```powershell
ssh voicepi
```

Then test non-interactively:

```powershell
ssh voicepi "hostname"
```

Then run the Phase 0 baseline command:

```powershell
ssh voicepi "hostname && uname -m && python3 --version && free -h && df -h /"
```

The agent must not consider SSH setup complete until the alias works successfully.

---

# 19. SSH Validation Criteria

Phase 0 SSH setup is considered successful when all of the following pass:

```text
SSH_CONNECTION=PASS
SSH_KEY_AUTHENTICATION=PASS
SSH_ALIAS=voicepi
REMOTE_COMMAND_EXECUTION=PASS
```

Do not record secrets.

If the repository is public, avoid documenting private network details unless necessary.

---

# 20. Phase 0 Raspberry Pi Baseline

After SSH connectivity is working, collect the Raspberry Pi baseline.

Commands should include:

```bash
hostname
hostname -I
uname -a
uname -m
cat /etc/os-release
python3 --version
git --version
free -h
df -h /
vcgencmd measure_temp
```

If available, also inspect:

```bash
vcgencmd get_throttled
```

Document relevant hardware and software information.

Do not publish sensitive network details unnecessarily.

---

# 21. Phase 0 Windows Baseline

Document the development environment sufficiently for future recreation.

Record items such as:

```text
Windows version
PowerShell version
OpenSSH availability
Git version
Visual Studio Code
Codex usage
```

Exact machine-specific secrets or identifiers must not be committed.

---

# 22. Remote Command Execution

The agent may execute commands remotely using:

```powershell
ssh voicepi "command"
```

For multiple Linux commands:

```powershell
ssh voicepi "cd ~/pi-voice-ai && source .venv/bin/activate && python -m pytest"
```

For more complex operations, prefer scripts stored in the repository instead of very large inline SSH commands.

---

# 23. Repository Structure

Use approximately:

```text
pi-voice-ai/
│
├── AGENTS.md
├── README.md
├── Curso_Step.md
├── CHANGELOG.md
├── .gitignore
├── .env.example
├── pyproject.toml
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── health.py
│   │   └── signaling.py
│   │
│   ├── audio/
│   │   ├── base.py
│   │   ├── webrtc_input.py
│   │   ├── webrtc_output.py
│   │   ├── usb_input.py
│   │   └── usb_output.py
│   │
│   ├── vad/
│   │   └── service.py
│   │
│   ├── stt/
│   │   ├── base.py
│   │   └── service.py
│   │
│   ├── llm/
│   │   ├── base.py
│   │   └── openai_service.py
│   │
│   ├── tts/
│   │   ├── base.py
│   │   └── service.py
│   │
│   └── conversation/
│       └── manager.py
│
├── web/
│   ├── index.html
│   ├── app.js
│   └── styles.css
│
├── scripts/
│   ├── bootstrap_pi.sh
│   ├── deploy.sh
│   ├── start.sh
│   ├── stop.sh
│   ├── restart.sh
│   ├── healthcheck.sh
│   ├── benchmark.sh
│   └── recreate_pi.sh
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── systemd/
    └── pi-voice-ai.service
```

Keep components replaceable.

---

# 24. AGENTS.md Must Evolve With the Project

AGENTS.md is a living architecture and reconstruction document.

The agent must update this file whenever a significant project decision changes.

Examples:

* new service added
* new dependency introduced
* STT engine changed
* TTS engine changed
* new hardware supported
* environment variable added
* directory structure changed
* deployment procedure changed
* WebRTC architecture changed
* service configuration changed
* security requirement changed
* testing procedure changed
* new integration added

The goal is:

> A future Codex session should be able to read AGENTS.md and understand how the complete project should be built, configured, deployed, tested, and maintained.

Do not let AGENTS.md become obsolete.

---

# 25. README.md

README.md is mandatory and must evolve continuously.

It should describe the project for someone who has never seen it before.

The README should include:

## Overview

Explain:

* what PiVoice AI does
* why it exists
* project goals
* target hardware
* overall architecture

## Windows + Raspberry Pi SSH Setup

Include:

* checking existing SSH keys
* generating ED25519 key
* explanation of public vs private key
* transferring only the public key by USB
* installing authorized_keys
* SSH directory permissions
* testing remote access
* configuring the `voicepi` alias
* troubleshooting common SSH issues

## Architecture

Explain:

```text
Browser / USB Mic
       ↓
WebRTC / Audio Adapter
       ↓
VAD
       ↓
Local STT
       ↓
OpenAI LLM
       ↓
Local TTS
       ↓
Browser / USB Speaker
```

## Installation

Provide complete step-by-step commands.

## Configuration

Explain relevant environment variables.

## Running

Explain:

```text
start
stop
restart
status
logs
```

## Testing

Explain:

* SSH tests
* unit tests
* integration tests
* WebRTC tests
* latency benchmarks

## Troubleshooting

Document real problems encountered during development.

---

# 26. Curso_Step.md

Maintain:

```text
Curso_Step.md
```

This file is specifically intended to help create a future Udemy course.

It should be more educational and detailed than README.md.

README explains how to use and recreate the project.

Curso_Step.md explains how to teach the project.

---

# 27. Mandatory Udemy Lesson — SSH Setup

Phase 0 must generate a detailed lesson section in Curso_Step.md with a working title similar to:

```text
Setting Up Secure SSH Access from Windows to Raspberry Pi 5
```

This lesson must explain:

1. Why SSH is used in the project
2. Why development is performed from Windows
3. Why Raspberry Pi is treated as a remote runtime target
4. Public key vs private key
5. ED25519 basics
6. How to check existing Windows SSH keys
7. How to generate a key safely
8. Which key may be copied
9. Why the private key must remain private
10. How to transfer the public key using a USB drive
11. How to configure `~/.ssh`
12. How to configure `authorized_keys`
13. Linux file permissions
14. How to test the connection
15. How to configure the `voicepi` alias
16. How Codex will use SSH later
17. Security considerations
18. Common SSH errors
19. Troubleshooting steps
20. Expected successful result

---

# 28. Udemy SSH Lesson Expected Demonstration

The course should eventually be able to demonstrate:

```text
Windows Laptop
      |
      | ED25519 private key stays here
      |
      +---------------------------+
                                  |
                                  | authentication
                                  v
                            Raspberry Pi 5
                                  |
                           public key stored in
                           ~/.ssh/authorized_keys
```

The lesson should reinforce:

```text
PRIVATE KEY
Never share

PUBLIC KEY
Safe to install on the remote server
```

---

# 29. Curso_Step.md Must Preserve Real Commands

The SSH lesson should record the real commands used during implementation.

Examples:

```powershell
Get-ChildItem $env:USERPROFILE\.ssh
ssh-keygen -t ed25519 -C "pi-voice-ai"
ssh voicepi
ssh voicepi "hostname"
```

And Raspberry Pi commands:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

Do not invent outputs.

Use actual results where appropriate.

---

# 30. Curso_Step.md Should Capture Real Problems

If an SSH problem occurs during setup, document:

```text
Problem
Cause
Diagnosis
Solution
Verification
```

Examples might include:

* wrong username
* incorrect Raspberry Pi IP
* duplicate host key
* incorrect file permissions
* public key not installed
* Windows private key not found
* hostname resolution issue

Only document problems that were actually encountered.

---

# 31. Git Is Mandatory

Git must be used throughout the project.

Before modifying the project:

```bash
git status
```

After implementing a logical feature:

```bash
git status
git diff
```

Review changes before committing.

---

# 32. GitHub Repository

Repository name:

```text
pi-voice-ai
```

Project display name:

```text
PiVoice AI
```

Recommended GitHub description:

```text
Build a real-time AI voice assistant on Raspberry Pi 5 with local speech-to-text, local text-to-speech, WebRTC, and OpenAI.
```

---

# 33. Git Commit Strategy

Prefer focused commits.

Examples:

```text
docs: add Windows to Raspberry Pi SSH setup
feat: add FastAPI health endpoint
feat: add WebRTC audio transport
feat: add local STT pipeline
feat: add OpenAI streaming client
feat: add local TTS
feat: implement barge-in
feat: add USB audio adapter

fix: handle WebRTC disconnect
fix: improve TTS cancellation

perf: reduce STT latency
perf: optimize TTS chunking
```

---

# 34. GitHub Releases

Create releases at meaningful milestones.

Recommended strategy:

```text
v0.1.0 - Windows, SSH and Raspberry Pi baseline
v0.2.0 - Browser WebRTC audio loopback
v0.3.0 - Local STT
v0.4.0 - OpenAI LLM integration
v0.5.0 - Local TTS
v0.6.0 - Full voice conversation
v0.7.0 - Barge-in
v0.8.0 - Performance optimization
v0.9.0 - USB microphone/speaker
v1.0.0 - Stable complete system
```

---

# 35. Phase 0 — Detailed Checklist

Phase 0 is:

```text
PHASE 0 — WORKSTATION + SSH + RASPBERRY BASELINE
```

The agent must execute or guide the following sequence.

## Phase 0.1 — Validate Windows Environment

Check:

* Windows
* PowerShell
* OpenSSH client
* Git
* VS Code
* Codex project context

---

## Phase 0.2 — Check Existing SSH Keys

Inspect:

```powershell
Get-ChildItem $env:USERPROFILE\.ssh
```

Do not overwrite existing keys.

---

## Phase 0.3 — Generate ED25519 Key If Needed

Use:

```powershell
ssh-keygen -t ed25519 -C "pi-voice-ai"
```

Explain exactly what is created.

---

## Phase 0.4 — Explain Public and Private Keys

Document in README.md and Curso_Step.md:

```text
id_ed25519      = private
id_ed25519.pub  = public
```

---

## Phase 0.5 — Transfer Public Key by USB

Copy only:

```text
id_ed25519.pub
```

to a USB drive.

---

## Phase 0.6 — Install Public Key on Raspberry Pi

Create:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
```

Install public key into:

```text
~/.ssh/authorized_keys
```

Then:

```bash
chmod 600 ~/.ssh/authorized_keys
```

---

## Phase 0.7 — Test Direct SSH

From Windows:

```powershell
ssh <pi-user>@<pi-ip>
```

Then:

```powershell
ssh <pi-user>@<pi-ip> "hostname"
```

---

## Phase 0.8 — Configure `voicepi`

Create or update:

```text
C:\Users\<WINDOWS_USER>\.ssh\config
```

with:

```text
Host voicepi
    HostName <raspberry-pi-ip-or-hostname>
    User <pi-user>
    IdentityFile ~/.ssh/id_ed25519
```

---

## Phase 0.9 — Validate Alias

Run:

```powershell
ssh voicepi
```

Then:

```powershell
ssh voicepi "hostname"
```

Then:

```powershell
ssh voicepi "hostname && uname -m && python3 --version && free -h && df -h /"
```

---

## Phase 0.10 — Collect Raspberry Baseline

Collect:

```bash
hostname
uname -a
uname -m
cat /etc/os-release
python3 --version
git --version
free -h
df -h /
vcgencmd measure_temp
vcgencmd get_throttled
```

where available.

---

## Phase 0.11 — Initialize Project Repository

Create or confirm:

```text
pi-voice-ai
```

Initialize Git if necessary.

---

## Phase 0.12 — Configure GitHub

Configure the project remote.

Do not store tokens in the repository.

---

## Phase 0.13 — Create `.gitignore`

At minimum:

```text
.env
.venv/
__pycache__/
*.pyc
*.key
*.pem
secrets/
private/
```

---

## Phase 0.14 — Create `.env.example`

Create a safe template.

Example:

```text
OPENAI_API_KEY=

AUDIO_MODE=webrtc

APP_HOST=0.0.0.0
APP_PORT=8000

STT_ENGINE=sherpa-whisper
STT_MODEL_DIR=models/sherpa-onnx-whisper-tiny
STT_LANGUAGE=pt
STT_NUM_THREADS=4
STT_MIN_AUDIO_SECONDS=0.5
STT_MAX_AUDIO_SECONDS=30
TTS_ENGINE=piper

LOG_LEVEL=INFO

ENABLE_BARGE_IN=true
ENABLE_PARTIAL_TRANSCRIPTS=true
ENABLE_STREAMING_LLM=true
```

---

## Phase 0.15 — Create Local `.env`

Copy:

```powershell
Copy-Item .env.example .env
```

Never commit `.env`.

---

## Phase 0.16 — Create Documentation

Create/update:

```text
README.md
Curso_Step.md
CHANGELOG.md
AGENTS.md
```

---

## Phase 0.17 — Record Course Material

Curso_Step.md must contain the complete SSH setup lesson.

This is mandatory.

---

## Phase 0.18 — Validate Phase 0

The agent must verify:

```text
SSH key exists
SSH public key installed
ssh voicepi works
remote commands work
Raspberry baseline collected
Git repository initialized
GitHub remote configured
.env.example exists
.env ignored by Git
README.md exists
Curso_Step.md exists
CHANGELOG.md exists
```

---

## Phase 0.19 — Prepare Git Commit

Suggested commit:

```text
chore: initialize PiVoice AI development environment
```

or split documentation into focused commits if appropriate.

---

## Phase 0.20 — Push to GitHub

Push only after:

* reviewing Git status
* ensuring secrets are not staged
* confirming `.env` is ignored

---

## Phase 0.21 — Release v0.1.0

Only create:

```text
v0.1.0
```

after Phase 0 is fully validated.

Release meaning:

```text
Windows development environment
+
SSH key authentication
+
Raspberry Pi baseline
+
Git/GitHub
+
project documentation foundation
```

---

# 36. Phase 1 — Application Foundation

Implement:

* repository structure
* Python virtual environment
* FastAPI
* `/health`
* deployment scripts
* systemd
* structured logging

---

# 37. Phase 2 — WebRTC Audio

Implement:

```text
Browser microphone
        ↓
WebRTC
        ↓
Raspberry Pi
        ↓
WebRTC
        ↓
Browser speaker
```

First objective:

WebRTC audio loopback.

Expected milestone:

```text
v0.2.0
```

---

# 38. Phase 3 — Local STT

Implement:

```text
Browser
 ↓
WebRTC
 ↓
Pi
 ↓
STT
 ↓
Transcript
```

Expected milestone:

```text
v0.3.0
```

---

# 39. Phase 4 — OpenAI LLM

Implement:

```text
Voice
 ↓
STT
 ↓
OpenAI
 ↓
Streaming text response
```

Expected milestone:

```text
v0.4.0
```

---

# 40. Phase 5 — Local TTS

Implement:

```text
Voice
 ↓
STT
 ↓
OpenAI
 ↓
TTS
 ↓
WebRTC
 ↓
Speaker
```

Expected milestone:

```text
v0.5.0
```

---

# 41. Phase 6 — Complete Voice Conversation

Integrate:

* VAD
* STT
* OpenAI LLM
* TTS
* streaming
* conversation state

Expected milestone:

```text
v0.6.0
```

---

# 42. Phase 7 — Barge-In

Implement interruption support.

Expected milestone:

```text
v0.7.0
```

---

# 43. Phase 8 — Performance Optimization

Benchmark:

* STT engines
* model sizes
* TTS engines
* buffering
* chunk size
* WebRTC parameters

Expected milestone:

```text
v0.8.0
```

---

# 44. Phase 9 — USB Audio

Support:

```text
AUDIO_MODE=usb
```

while preserving:

```text
AUDIO_MODE=webrtc
```

Expected milestone:

```text
v0.9.0
```

---

# 45. Phase 10 — Stable Project

Target:

* reproducible setup
* stable WebRTC
* stable USB audio
* local STT
* local TTS
* OpenAI LLM
* streaming
* barge-in
* remote management
* tests
* documentation
* course documentation

Expected milestone:

```text
v1.0.0
```

---

# 46. Final Agent Workflow

For each meaningful task:

```text
Inspect
   ↓
Understand current state
   ↓
Implement
   ↓
Validate
   ↓
Deploy
   ↓
Test Raspberry remotely
   ↓
Check logs
   ↓
Benchmark if relevant
   ↓
Update AGENTS.md
   ↓
Update README.md
   ↓
Update Curso_Step.md
   ↓
Update CHANGELOG.md if required
   ↓
Review Git diff
   ↓
Commit
   ↓
Push
   ↓
Release if milestone reached
```

---

# 47. Definition of Done

A feature is not complete because the code exists.

It is complete when applicable items are satisfied:

1. Code implemented
2. Tests executed
3. Raspberry Pi validation completed
4. Logs reviewed
5. Documentation updated
6. AGENTS.md still reflects reality
7. README.md can reproduce the feature
8. Curso_Step.md can teach the feature
9. Git history is meaningful
10. GitHub source is current
11. Release created when a milestone is reached

---

# 48. Future Udemy Course Goal

Working project name:

```text
PiVoice AI
```

Repository:

```text
pi-voice-ai
```

Working course title:

```text
Raspberry Pi + OpenAI: Build a Local AI Voice Assistant
```

Possible course modules:

```text
Module 1
Project architecture and Raspberry Pi preparation

Module 2
Windows, SSH, SSH keys and remote Raspberry Pi development

Module 3
Git, GitHub and project versioning

Module 4
Python environment and FastAPI

Module 5
Understanding WebRTC

Module 6
Browser microphone and speaker

Module 7
Local Speech-to-Text

Module 8
OpenAI LLM integration

Module 9
Local Text-to-Speech

Module 10
Building the streaming voice pipeline

Module 11
Voice Activity Detection

Module 12
Barge-in and natural conversations

Module 13
Performance optimization

Module 14
USB microphone and speaker

Module 15
Linux systemd deployment

Module 16
RAG and custom assistant knowledge

Module 17
Assistant personalities and use cases

Module 18
Rebuilding PiVoice AI from scratch
```

Update this structure as the real project evolves.

---

# 49. Final Principle

The Raspberry Pi 5 is the execution target.

The Windows laptop is the development and control environment.

Codex should perform as much configuration, installation, deployment, validation, benchmarking, testing, documentation, Git versioning, and troubleshooting remotely over SSH as safely possible.

The browser initially serves as a remote microphone and speaker through WebRTC.

Later, USB audio will be added without changing the core:

```text
VAD
 ↓
STT
 ↓
OpenAI LLM
 ↓
TTS
```

The repository must continuously evolve into a complete, reproducible technical and educational record of the project.

The project is not complete if the code works but the knowledge required to recreate and teach it has been lost.
