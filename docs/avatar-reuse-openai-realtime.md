# Reusing the reactive 2D avatar with OpenAI Realtime WebRTC

This document describes the avatar that is already implemented in PiVoice AI and a
recommended React + TypeScript extraction for another web chat. Existing behavior
and proposed adaptation are labeled separately.

No API key belongs in browser code. The current application sends its SDP offer to
the trusted backend at `POST /api/realtime/calls`; the backend authenticates the
OpenAI Realtime call and returns only the SDP answer.

## 1. Original source files

The avatar has no image asset and no frontend package dependency.

| File | Existing responsibility |
| --- | --- |
| `web/index.html` | Inline SVG, state caption, and the single remote `<audio>` element. |
| `web/styles.css` | Avatar layout, colors, state classes, blink, float, orbit, listening, thinking, and level animations. |
| `web/app.js` | State selection, Web Audio analysis, mouth animation, WebRTC track attachment, Realtime event handling, interruption, and cleanup. |
| `app/api/realtime.py` | Trusted backend SDP exchange and Realtime session configuration. It keeps the standard API key off the browser. |

The SVG structure below comes from `web/index.html`; only its visible labels are
translated to English for reuse:

```html
<section id="avatar" class="avatar-card idle" aria-labelledby="avatar-state">
  <div class="avatar-stage" aria-hidden="true">
    <span class="avatar-orbit orbit-one"></span>
    <span class="avatar-orbit orbit-two"></span>
    <svg class="ai-avatar" viewBox="0 0 240 240" role="img">
      <defs>
        <linearGradient id="avatar-face-gradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#243447"></stop>
          <stop offset="1" stop-color="#111820"></stop>
        </linearGradient>
        <radialGradient id="avatar-core-gradient">
          <stop offset="0" stop-color="#8ff0a4"></stop>
          <stop offset="1" stop-color="#238636"></stop>
        </radialGradient>
      </defs>
      <circle class="avatar-halo" cx="120" cy="120" r="93"></circle>
      <g class="avatar-head">
        <path class="avatar-antenna" d="M120 47V29"></path>
        <circle class="avatar-antenna-tip" cx="120" cy="24" r="7"></circle>
        <rect class="avatar-ear" x="33" y="94" width="22" height="53" rx="11"></rect>
        <rect class="avatar-ear" x="185" y="94" width="22" height="53" rx="11"></rect>
        <rect class="avatar-face" x="48" y="51" width="144" height="143" rx="55"></rect>
        <path class="avatar-brow left" d="M75 94Q91 84 105 94"></path>
        <path class="avatar-brow right" d="M135 94Q150 84 166 94"></path>
        <g class="avatar-eye left">
          <ellipse cx="91" cy="111" rx="10" ry="13"></ellipse>
          <circle cx="94" cy="107" r="3"></circle>
        </g>
        <g class="avatar-eye right">
          <ellipse cx="150" cy="111" rx="10" ry="13"></ellipse>
          <circle cx="153" cy="107" r="3"></circle>
        </g>
        <circle class="avatar-cheek" cx="75" cy="145" r="8"></circle>
        <circle class="avatar-cheek" cx="166" cy="145" r="8"></circle>
        <ellipse id="avatar-mouth" class="avatar-mouth" cx="120" cy="151" rx="14" ry="3"></ellipse>
        <circle class="avatar-core" cx="120" cy="181" r="7"></circle>
      </g>
    </svg>
    <div class="avatar-level">
      <span></span><span></span><span></span><span></span><span></span>
    </div>
  </div>
  <div class="avatar-caption">
    <strong id="avatar-state">Waiting for connection</strong>
    <span id="avatar-detail">The avatar reacts to remote response audio.</span>
  </div>
</section>

<!-- This is the only audible playback path. -->
<audio id="remote-audio" autoplay muted></audio>
```

The complete avatar-specific CSS from `web/styles.css` is:

```css
.avatar-card {
  --avatar-accent: #56d364;
  --avatar-accent-rgb: 86, 211, 100;
  --audio-level: 0;
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  align-items: center;
  gap: 24px;
  margin: 8px 0 28px;
  padding: 20px;
  overflow: hidden;
  border: 1px solid rgba(var(--avatar-accent-rgb), .34);
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(var(--avatar-accent-rgb), .11), rgba(13, 17, 23, .92) 64%);
  transition: border-color .25s ease, background .25s ease;
}

.avatar-card.listening { --avatar-accent: #58a6ff; --avatar-accent-rgb: 88, 166, 255; }
.avatar-card.thinking { --avatar-accent: #d29922; --avatar-accent-rgb: 210, 153, 34; }
.avatar-card.speaking { --avatar-accent: #56d364; --avatar-accent-rgb: 86, 211, 100; }
.avatar-card.idle { --avatar-accent: #8c959f; --avatar-accent-rgb: 140, 149, 159; }

.avatar-stage { position: relative; display: grid; place-items: center; width: 180px; height: 180px; }
.ai-avatar { position: relative; z-index: 2; width: 170px; height: 170px; overflow: visible; filter: drop-shadow(0 14px 28px rgba(0, 0, 0, .34)); }
.avatar-halo { fill: rgba(var(--avatar-accent-rgb), .08); stroke: rgba(var(--avatar-accent-rgb), .42); stroke-width: 2; transition: fill .25s ease, stroke .25s ease; }
.avatar-head { transform-origin: 120px 125px; animation: avatar-float 4s ease-in-out infinite; }
.avatar-face { fill: url(#avatar-face-gradient); stroke: var(--avatar-accent); stroke-width: 3; transition: stroke .25s ease; }
.avatar-ear { fill: #212b36; stroke: var(--avatar-accent); stroke-width: 3; }
.avatar-antenna { fill: none; stroke: #8c959f; stroke-width: 5; stroke-linecap: round; }
.avatar-antenna-tip, .avatar-core { fill: url(#avatar-core-gradient); filter: drop-shadow(0 0 8px rgba(var(--avatar-accent-rgb), .7)); }
.avatar-brow { fill: none; stroke: #8c959f; stroke-width: 5; stroke-linecap: round; }
.avatar-eye ellipse { fill: var(--avatar-accent); transform-box: fill-box; transform-origin: center; animation: avatar-blink 5.2s infinite; }
.avatar-eye circle { fill: #f0f6fc; }
.avatar-cheek { fill: rgba(var(--avatar-accent-rgb), .2); }
.avatar-mouth { fill: var(--avatar-accent); filter: drop-shadow(0 0 calc(3px + var(--audio-level) * 8px) rgba(var(--avatar-accent-rgb), .72)); }
.avatar-orbit { position: absolute; inset: 8px; border: 1px solid rgba(var(--avatar-accent-rgb), .2); border-radius: 50%; }
.avatar-orbit::after { content: ""; position: absolute; top: -4px; left: 50%; width: 8px; height: 8px; border-radius: 50%; background: var(--avatar-accent); box-shadow: 0 0 12px rgba(var(--avatar-accent-rgb), .8); }
.orbit-one { animation: avatar-orbit 9s linear infinite; }
.orbit-two { inset: 20px; animation: avatar-orbit 6s linear infinite reverse; opacity: .52; }
.avatar-caption strong, .avatar-caption span { display: block; }
.avatar-caption strong { font-size: 1.12rem; }
.avatar-caption span { margin-top: 7px; color: #8c959f; font-size: .88rem; line-height: 1.5; }
.avatar-level { position: absolute; z-index: 3; bottom: 6px; display: flex; align-items: end; gap: 4px; height: 22px; }
.avatar-level span { width: 4px; height: 5px; border-radius: 4px; background: var(--avatar-accent); opacity: .45; }
.avatar-card.speaking .avatar-level span { animation: avatar-level .62s ease-in-out infinite alternate; opacity: .9; }
.avatar-card.speaking .avatar-level span:nth-child(2), .avatar-card.speaking .avatar-level span:nth-child(4) { animation-delay: -.28s; }
.avatar-card.speaking .avatar-level span:nth-child(3) { animation-delay: -.46s; }
.avatar-card.listening .avatar-halo { animation: avatar-listen 1.5s ease-in-out infinite; }
.avatar-card.thinking .avatar-head { animation: avatar-think 1.7s ease-in-out infinite; }

@media (max-width: 480px) {
  .avatar-card { grid-template-columns: 1fr; text-align: center; }
  .avatar-stage { margin: 0 auto; }
}

@keyframes avatar-float { 50% { transform: translateY(-4px); } }
@keyframes avatar-orbit { to { transform: rotate(360deg); } }
@keyframes avatar-blink { 0%, 45%, 49%, 100% { transform: scaleY(1); } 47% { transform: scaleY(.08); } }
@keyframes avatar-listen { 50% { fill: rgba(var(--avatar-accent-rgb), .16); stroke-width: 4; } }
@keyframes avatar-think { 25% { transform: rotate(-2deg) translateY(-3px); } 75% { transform: rotate(2deg) translateY(-3px); } }
@keyframes avatar-level { to { height: 20px; } }

@media (prefers-reduced-motion: reduce) {
  .avatar-head,
  .avatar-eye ellipse,
  .avatar-orbit,
  .avatar-card .avatar-level span,
  .avatar-card.listening .avatar-halo { animation: none; }
}
```

## 2. Existing Web Audio implementation

The current code in `web/app.js` creates a second, silent consumer of the same
remote `MediaStream`. The `<audio>` element remains the only audible consumer.

```text
Remote MediaStream +--> HTMLAudioElement ------------------> speakers
                   |
                   +--> MediaStreamAudioSourceNode
                        --> AnalyserNode
                        --> GainNode(gain = 0)
                        --> AudioContext.destination
```

The complete analysis and cleanup block is:

```js
let avatarAudioContext = null;
let avatarAudioSource = null;
let avatarAnalyser = null;
let avatarSilentGain = null;
let avatarSamples = null;
let avatarFrame = null;
let avatarMouthLevel = 0;

function animateAvatarMouth() {
  if (!avatarAnalyser || !avatarSamples) return;
  avatarAnalyser.getByteTimeDomainData(avatarSamples);
  let energy = 0;
  for (const sample of avatarSamples) {
    const normalized = (sample - 128) / 128;
    energy += normalized * normalized;
  }
  const rms = Math.sqrt(energy / avatarSamples.length);
  const target = Math.min(1, Math.max(0, (rms - 0.008) * 13));
  avatarMouthLevel += (target - avatarMouthLevel) * (target > avatarMouthLevel ? 0.55 : 0.24);
  avatarMouth.setAttribute("rx", (14 - avatarMouthLevel * 2).toFixed(1));
  avatarMouth.setAttribute("ry", (3 + avatarMouthLevel * 12).toFixed(1));
  avatar.style.setProperty("--audio-level", avatarMouthLevel.toFixed(3));
  avatarFrame = requestAnimationFrame(animateAvatarMouth);
}

async function connectAvatarAudio(stream) {
  disconnectAvatarAudio();
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return;
  avatarAudioContext = new AudioContextClass();
  avatarAnalyser = avatarAudioContext.createAnalyser();
  avatarAnalyser.fftSize = 256;
  avatarAnalyser.smoothingTimeConstant = 0.68;
  avatarSamples = new Uint8Array(avatarAnalyser.fftSize);
  avatarAudioSource = avatarAudioContext.createMediaStreamSource(stream);
  avatarAudioSource.connect(avatarAnalyser);
  avatarSilentGain = avatarAudioContext.createGain();
  avatarSilentGain.gain.value = 0;
  avatarAnalyser.connect(avatarSilentGain);
  avatarSilentGain.connect(avatarAudioContext.destination);
  await avatarAudioContext.resume();
  animateAvatarMouth();
}

function disconnectAvatarAudio() {
  if (avatarFrame !== null) cancelAnimationFrame(avatarFrame);
  avatarFrame = null;
  avatarAudioSource?.disconnect();
  avatarAnalyser?.disconnect();
  avatarSilentGain?.disconnect();
  const context = avatarAudioContext;
  avatarAudioContext = null;
  avatarAudioSource = null;
  avatarAnalyser = null;
  avatarSilentGain = null;
  avatarSamples = null;
  avatarMouthLevel = 0;
  avatar.style.setProperty("--audio-level", "0");
  if (context) void context.close().catch(() => {});
}
```

`fftSize = 256` provides 256 unsigned time-domain samples. Each byte is centered at
128, normalized to approximately `[-1, 1]`, squared, averaged, and square-rooted to
produce RMS intensity. Values below `0.008` are treated as noise. The remaining
level is multiplied by 13 and clamped to `[0, 1]`.

Attack and release use different interpolation factors:

- Rising level: `0.55`, so the mouth opens quickly.
- Falling level: `0.24`, so the mouth closes more smoothly.
- Horizontal radius: `14 - level * 2`.
- Vertical radius: `3 + level * 12`.
- CSS `--audio-level` also increases the mouth glow.

### Actual frame rate

The existing implementation does **not** enforce 30 fps. It schedules every
`requestAnimationFrame`, usually about 60 fps and potentially 90 or 120 fps on a
high-refresh display. The React extraction below retains `requestAnimationFrame`
but performs analysis at most once every 33.3 ms, which is approximately 30 fps.

Analysis starts only after a remote WebRTC track arrives. It runs during speech and
silence until the session closes. Silence drives the RMS target to zero; the release
filter closes the mouth gradually. `disconnectAvatarAudio()` cancels the frame,
disconnects every node, clears references, resets the level, and closes the
`AudioContext`.

## 3. Existing WebRTC attachment and playback

The relevant `track` handler in `web/app.js` is:

```js
peerConnection.addEventListener("track", async (event) => {
  const remoteStream = event.streams[0] ?? new MediaStream([event.track]);
  remoteAudio.srcObject = remoteStream;
  remoteAudio.muted = false;
  try {
    await connectAvatarAudio(remoteStream);
    await remoteAudio.play();
  } catch (error) {
    errorText.textContent = `The browser blocked playback: ${error.message}`;
  }
});
```

The fallback `new MediaStream([event.track])` is required because `event.streams`
may be empty in streamless WebRTC negotiation.

The Realtime connection uses a data channel named `oai-events`. Microphone audio is
added as a local WebRTC track, response audio arrives as a remote track, and JSON
lifecycle events arrive on the data channel. The browser sends its SDP offer as
`application/sdp` to `/api/realtime/calls` and applies the returned SDP answer.

## 4. Existing states, interruption, and silence

The current avatar has five internal states:

| Avatar state | Meaning | Current trigger examples |
| --- | --- | --- |
| `idle` | Disconnected or unavailable. | Initial load and `closeSession()`. |
| `ready` | Connected and waiting for speech. | Connected status, `output_audio_buffer.stopped`, completed response. |
| `listening` | User speech is active or may begin. | `input_audio_buffer.speech_started`, chained `speech_started`, recording status. |
| `thinking` | Transcription or response generation is active. | Connecting status, `input_audio_buffer.speech_stopped`, STT/LLM events. |
| `speaking` | Remote response playback is active. | `response.output_audio.delta`, `output_audio_buffer.started`, chained TTS playback status. |

The existing state setter resets the mouth whenever the state is not `speaking`:

```js
const avatarStates = {
  idle: ["Waiting for connection", "Connect the microphone to begin."],
  ready: ["Ready to talk", "Speak whenever you are ready."],
  listening: ["Listening", "Detecting your speech in real time."],
  thinking: ["Thinking", "Preparing the response."],
  speaking: ["Speaking", "The mouth follows the remote response audio."],
};

function setAvatarState(state) {
  const [label, detail] = avatarStates[state] || avatarStates.idle;
  avatar.className = `avatar-card ${state}`;
  avatarStateText.textContent = label;
  avatarDetailText.textContent = detail;
  if (state !== "speaking") {
    avatarMouthLevel = 0;
    avatarMouth.setAttribute("rx", "14");
    avatarMouth.setAttribute("ry", "3");
  }
}
```

OpenAI Realtime interruption is configured by the backend with semantic VAD,
`create_response: true`, and `interrupt_response: true`. When the user begins
speaking over a response, the model-side turn detection interrupts output and emits
new input/output lifecycle events. The browser immediately changes to `listening`
on `input_audio_buffer.speech_started`.

The relevant existing backend configuration in `app/api/realtime.py` is:

```py
session = {
    "type": "realtime",
    "model": voice_pipeline.realtime_model,
    "instructions": prompt_control.instructions,
    "output_modalities": ["audio"],
    "max_output_tokens": settings.realtime_max_output_tokens,
    "audio": {
        "input": {
            "turn_detection": {
                "type": "semantic_vad",
                "eagerness": "auto",
                "create_response": True,
                "interrupt_response": True,
            }
        },
        "output": {"voice": voice_pipeline.realtime_voice},
    },
}
```

An explicit full-session close also sends:

```js
realtimeEvents.send(JSON.stringify({ type: "response.cancel" }));
realtimeEvents.send(JSON.stringify({ type: "output_audio_buffer.clear" }));
```

It then closes the peer connection, stops every local microphone track, detaches the
remote audio stream, shuts down avatar analysis, and resets Realtime state. The
chained pipeline receives a separate SSE `interrupted` event and maps it to the
listening state.

Silence is handled acoustically, not with a timer: the analyser keeps running, RMS
drops below the noise floor, and the mouth closes. Conversation state remains
`speaking` until a lifecycle event such as `output_audio_buffer.stopped` changes it.
This avoids treating natural pauses inside a spoken sentence as the end of output.

## 5. Runtime requirements

Existing implementation requirements:

- A browser with WebRTC, `MediaStream`, Web Audio, SVG, CSS custom properties, and
  `requestAnimationFrame` support.
- HTTPS or `localhost` for microphone capture.
- A remote audio `MediaStream` from the WebRTC peer.
- A user action that begins connection and grants microphone/audio permission.
- One `<audio>` element for audible remote playback.
- No npm dependency, image, font, canvas, WebGL, or server-side rendering library.

Copy the SVG, the avatar CSS block, and the analyser logic. The gradients are defined
inside the SVG, so no external asset path is required.

## 6. Recommended React + TypeScript extraction

The following component keeps animation DOM-local instead of causing approximately
30 React renders per second. Create the `AudioContext` from the same user click that
starts WebRTC, resume it there, and pass it to the avatar.

```tsx
import { useEffect, useRef } from "react";
import "./ReactiveAvatar.css";

export type AvatarState =
  | "idle"
  | "ready"
  | "listening"
  | "thinking"
  | "speaking";

const COPY: Record<AvatarState, readonly [string, string]> = {
  idle: ["Waiting for connection", "Connect the microphone to begin."],
  ready: ["Ready to talk", "Speak whenever you are ready."],
  listening: ["Listening", "Detecting your speech in real time."],
  thinking: ["Thinking", "Preparing the response."],
  speaking: ["Speaking", "The mouth follows the remote response audio."],
};

type Props = {
  state: AvatarState;
  remoteStream: MediaStream | null;
  audioContext: AudioContext | null;
};

export function ReactiveAvatar({ state, remoteStream, audioContext }: Props) {
  const rootRef = useRef<HTMLElement>(null);
  const mouthRef = useRef<SVGEllipseElement>(null);

  useEffect(() => {
    const mouth = mouthRef.current;
    if (state !== "speaking" && mouth) {
      mouth.setAttribute("rx", "14");
      mouth.setAttribute("ry", "3");
      rootRef.current?.style.setProperty("--audio-level", "0");
    }
  }, [state]);

  useEffect(() => {
    const root = rootRef.current;
    const mouth = mouthRef.current;
    if (!remoteStream || !audioContext || !root || !mouth) return;

    const source = audioContext.createMediaStreamSource(remoteStream);
    const analyser = audioContext.createAnalyser();
    const silentGain = audioContext.createGain();
    const samples = new Uint8Array(256);
    const frameInterval = 1000 / 30;
    let lastAnalysisAt = 0;
    let mouthLevel = 0;
    let animationFrame = 0;
    let stopped = false;

    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.68;
    silentGain.gain.value = 0;
    source.connect(analyser);
    analyser.connect(silentGain);
    silentGain.connect(audioContext.destination);

    const animate = (timestamp: number) => {
      if (stopped) return;
      if (timestamp - lastAnalysisAt >= frameInterval) {
        lastAnalysisAt = timestamp;
        analyser.getByteTimeDomainData(samples);
        let energy = 0;
        for (const sample of samples) {
          const normalized = (sample - 128) / 128;
          energy += normalized * normalized;
        }
        const rms = Math.sqrt(energy / samples.length);
        const target = Math.min(1, Math.max(0, (rms - 0.008) * 13));
        const smoothing = target > mouthLevel ? 0.55 : 0.24;
        mouthLevel += (target - mouthLevel) * smoothing;
        mouth.setAttribute("rx", (14 - mouthLevel * 2).toFixed(1));
        mouth.setAttribute("ry", (3 + mouthLevel * 12).toFixed(1));
        root.style.setProperty("--audio-level", mouthLevel.toFixed(3));
      }
      animationFrame = requestAnimationFrame(animate);
    };

    animationFrame = requestAnimationFrame(animate);
    return () => {
      stopped = true;
      cancelAnimationFrame(animationFrame);
      source.disconnect();
      analyser.disconnect();
      silentGain.disconnect();
      root.style.setProperty("--audio-level", "0");
      mouth.setAttribute("rx", "14");
      mouth.setAttribute("ry", "3");
    };
  }, [remoteStream, audioContext]);

  const [label, detail] = COPY[state];
  return (
    <section ref={rootRef} className={`avatar-card ${state}`} aria-labelledby="avatar-state">
      <div className="avatar-stage" aria-hidden="true">
        <span className="avatar-orbit orbit-one" />
        <span className="avatar-orbit orbit-two" />
        <svg className="ai-avatar" viewBox="0 0 240 240" role="img">
          <defs>
            <linearGradient id="avatar-face-gradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#243447" />
              <stop offset="1" stopColor="#111820" />
            </linearGradient>
            <radialGradient id="avatar-core-gradient">
              <stop offset="0" stopColor="#8ff0a4" />
              <stop offset="1" stopColor="#238636" />
            </radialGradient>
          </defs>
          <circle className="avatar-halo" cx="120" cy="120" r="93" />
          <g className="avatar-head">
            <path className="avatar-antenna" d="M120 47V29" />
            <circle className="avatar-antenna-tip" cx="120" cy="24" r="7" />
            <rect className="avatar-ear" x="33" y="94" width="22" height="53" rx="11" />
            <rect className="avatar-ear" x="185" y="94" width="22" height="53" rx="11" />
            <rect className="avatar-face" x="48" y="51" width="144" height="143" rx="55" />
            <path className="avatar-brow left" d="M75 94Q91 84 105 94" />
            <path className="avatar-brow right" d="M135 94Q150 84 166 94" />
            <g className="avatar-eye left"><ellipse cx="91" cy="111" rx="10" ry="13" /><circle cx="94" cy="107" r="3" /></g>
            <g className="avatar-eye right"><ellipse cx="150" cy="111" rx="10" ry="13" /><circle cx="153" cy="107" r="3" /></g>
            <circle className="avatar-cheek" cx="75" cy="145" r="8" />
            <circle className="avatar-cheek" cx="166" cy="145" r="8" />
            <ellipse ref={mouthRef} className="avatar-mouth" cx="120" cy="151" rx="14" ry="3" />
            <circle className="avatar-core" cx="120" cy="181" r="7" />
          </g>
        </svg>
        <div className="avatar-level"><span /><span /><span /><span /><span /></div>
      </div>
      <div className="avatar-caption">
        <strong id="avatar-state">{label}</strong>
        <span>{detail}</span>
      </div>
    </section>
  );
}
```

Reuse the CSS from section 1 as `ReactiveAvatar.css`. If more than one avatar can
exist on the same page, use React `useId()` to create unique gradient IDs and update
the two `url(#...)` references; duplicate SVG IDs otherwise collide.

### Parent WebRTC integration

```tsx
const [avatarState, setAvatarState] = useState<AvatarState>("idle");
const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);
const [audioContext, setAudioContext] = useState<AudioContext | null>(null);
const audioRef = useRef<HTMLAudioElement>(null);
const audioContextRef = useRef<AudioContext | null>(null);
const peerRef = useRef<RTCPeerConnection | null>(null);

async function connectFromUserClick() {
  // Create and resume Web Audio while browser user activation is still available.
  const context = new AudioContext();
  await context.resume();
  audioContextRef.current = context;
  setAudioContext(context);

  const pc = new RTCPeerConnection();
  peerRef.current = pc;
  pc.ontrack = async (event) => {
    const stream = event.streams[0] ?? new MediaStream([event.track]);
    setRemoteStream(stream);
    if (audioRef.current) {
      audioRef.current.srcObject = stream;
      audioRef.current.muted = false;
      await audioRef.current.play();
    }
  };

  // Add the microphone track, create the data channel, and perform SDP exchange here.
}

async function disconnect() {
  peerRef.current?.getSenders().forEach((sender) => sender.track?.stop());
  peerRef.current?.close();
  peerRef.current = null;
  setRemoteStream(null);
  if (audioRef.current) audioRef.current.srcObject = null;
  const context = audioContextRef.current;
  audioContextRef.current = null;
  setAudioContext(null);
  await context?.close().catch(() => undefined);
  setAvatarState("idle");
}

return (
  <>
    <ReactiveAvatar
      state={avatarState}
      remoteStream={remoteStream}
      audioContext={audioContext}
    />
    <audio ref={audioRef} autoPlay playsInline />
  </>
);
```

The state value renders the new context prop; the ref gives asynchronous cleanup a
stable handle. Do not create a new context on every render or Realtime event.

Recommended Realtime event mapping:

```ts
function applyRealtimeEvent(event: { type: string }) {
  switch (event.type) {
    case "session.created":
    case "output_audio_buffer.stopped":
    case "response.done":
      setAvatarState("ready");
      break;
    case "input_audio_buffer.speech_started":
      setAvatarState("listening");
      break;
    case "input_audio_buffer.speech_stopped":
    case "response.created":
      setAvatarState("thinking");
      break;
    case "output_audio_buffer.started":
    case "response.output_audio.delta":
      setAvatarState("speaking");
      break;
  }
}
```

Use events for semantic state and RMS only for mouth movement. Do not infer the
whole conversation state from amplitude because output may contain pauses and quiet
phonemes.

## 7. Known limitations and adaptation cautions

### Autoplay and suspended AudioContext

Browsers may reject `audio.play()` or leave `AudioContext.state === "suspended"`
when playback does not follow a user gesture. Start the session from a click or tap,
create/resume the context there, catch `play()` rejection, and display an explicit
“Enable audio” action when required. Microphone capture also requires HTTPS or
localhost.

### Duplicate playback

Keep exactly one audible path. In this design the `<audio>` element is audible and
the Web Audio branch ends in `GainNode(0)`. Never connect the analyser directly to
the destination at normal gain while the `<audio>` element is also playing. An
alternative design can make Web Audio the only playback path, but then remove or
mute the `<audio>` element deliberately.

### Reconnection and stale resources

The current page closes the session on `failed`, `disconnected`, or `closed`; it does
not perform ICE restart or automatic backoff reconnection. A new application should
use a monotonically increasing connection generation or an `AbortController` so a
late `track`, SDP answer, or data-channel event from an old peer cannot attach to the
new avatar. Run cleanup before replacing a stream, and close old tracks, nodes,
frames, data channels, and contexts.

### State ordering

WebRTC audio and data-channel events travel on separate channels. A lifecycle event
can arrive slightly before or after audible media. Let the analyser control only the
mouth, keep `output_audio_buffer.started/stopped` as the primary speaking state, and
make every transition idempotent.

### Silence and interruption

The current amplitude threshold is fixed. Different output gains or devices may
need a calibrated noise floor. Do not end a response merely because RMS reaches
zero for a short interval. Interruption should be controlled by Realtime VAD/events
and output cancellation, while silence only closes the mouth.

### Performance

The existing 256-sample RMS calculation is small and runs entirely in the browser.
The original loop follows display refresh; the React version caps analysis near
30 fps. Direct SVG mutations avoid React reconciliation at animation rate. Pause or
cancel the animation when the page is hidden if the application keeps long-lived
background sessions. Preserve `prefers-reduced-motion` for decorative animation;
mouth movement may remain because it conveys live speech, but this can also be made
user-configurable.

### React Strict Mode

Development Strict Mode runs effects through an extra setup/cleanup cycle. The hook
must disconnect only nodes it created and must tolerate cleanup more than once. Keep
the peer connection and session lifecycle in a dedicated owner rather than inside
the presentational avatar component.

### Server security

Keep the standard OpenAI API key on a trusted server. The browser should use the
unified SDP endpoint or a short-lived client secret. Do not place standard keys,
tokens, `.env` values, or session credentials in React source, browser storage, or
the built bundle.

## 8. Validation checklist

1. Start from a user click over HTTPS or localhost.
2. Confirm there is one remote `<audio>` element and no audible Web Audio branch.
3. Confirm the mouth stays closed during remote silence.
4. Confirm speech opens the mouth without visible jitter.
5. Confirm `speech_started` moves to listening and interrupts active output.
6. Confirm `speech_stopped` or `response.created` moves to thinking.
7. Confirm output start/stop moves between speaking and ready.
8. Disconnect and verify microphone tracks stop, the peer closes, the RAF is
   cancelled, nodes disconnect, the stream detaches, and the context closes.
9. Reconnect several times and check that only one analyser and one audible stream
   remain.
10. Test autoplay recovery, reduced motion, a 120 Hz display, a background tab, and
    a failed or disconnected peer.

## 9. Official references

- [OpenAI Realtime WebRTC guide](https://developers.openai.com/api/docs/guides/voice-webrtc?voice-api=realtime)
- [OpenAI Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations)
- [MDN: Web Audio API](https://developer.mozilla.org/docs/Web/API/Web_Audio_API)
- [MDN: RTCPeerConnection track event](https://developer.mozilla.org/docs/Web/API/RTCPeerConnection/track_event)
