const startButton = document.querySelector("#start");
const recordButton = document.querySelector("#record");
const stopButton = document.querySelector("#stop");
const statusText = document.querySelector("#status");
const statusDot = document.querySelector("#status-dot");
const errorText = document.querySelector("#error");
const transcriptText = document.querySelector("#transcript-text");
const metricsText = document.querySelector("#metrics");
const assistantText = document.querySelector("#assistant-text");
const assistantMetricsText = document.querySelector("#assistant-metrics");
const remoteAudio = document.querySelector("#remote-audio");
const loopbackCheckbox = document.querySelector("#loopback");
const automaticCheckbox = document.querySelector("#automatic");

let peerConnection = null;
let localStream = null;
let peerId = null;
let capturing = false;
let eventSource = null;
let receivingAutomaticResponse = false;

function setStatus(message, state = "") {
  statusText.textContent = message;
  statusDot.className = `status-dot ${state}`.trim();
}

function waitForIceGatheringComplete(connection) {
  if (connection.iceGatheringState === "complete") {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const handleStateChange = () => {
      if (connection.iceGatheringState === "complete") {
        connection.removeEventListener("icegatheringstatechange", handleStateChange);
        resolve();
      }
    };
    connection.addEventListener("icegatheringstatechange", handleStateChange);
  });
}

async function responseError(response) {
  try {
    const body = await response.json();
    return body.detail ?? `Erro HTTP ${response.status}`;
  } catch {
    return `Erro HTTP ${response.status}`;
  }
}

function parseEventFrame(frame) {
  let eventName = "message";
  const dataLines = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) {
    return null;
  }
  return { eventName, data: JSON.parse(dataLines.join("\n")) };
}

async function streamAssistantResponse(text) {
  assistantText.textContent = "";
  assistantMetricsText.textContent = "";
  setStatus("Consultando a OpenAI…", "connecting");

  const response = await fetch("/api/assistant/responses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error(await responseError(response));
  }
  if (!response.body) {
    throw new Error("O navegador não disponibilizou o fluxo da resposta.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const event = parseEventFrame(frame);
      if (!event) {
        continue;
      }
      if (event.eventName === "delta") {
        assistantText.textContent += event.data.text;
        setStatus("Recebendo resposta…", "connecting");
      } else if (event.eventName === "done") {
        assistantMetricsText.textContent = `${event.data.model} · primeiro texto ${event.data.first_token_seconds.toFixed(2)} s · total ${event.data.total_seconds.toFixed(2)} s`;
      } else if (event.eventName === "error") {
        throw new Error(event.data.message);
      }
    }
    if (done) {
      break;
    }
  }

  if (!assistantText.textContent) {
    assistantText.textContent = "O modelo não retornou texto.";
    setStatus("Pronto para outra frase", "connected");
    return;
  }
  await synthesizeAssistantResponse(assistantText.textContent);
}

async function synthesizeAssistantResponse(text) {
  if (!peerId) {
    return;
  }
  setStatus("Sintetizando voz no Raspberry Pi…", "connecting");
  const response = await fetch(`/api/webrtc/peers/${peerId}/speech`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error(await responseError(response));
  }
  const result = await response.json();
  assistantMetricsText.textContent += ` · voz ${result.processing_seconds.toFixed(2)} s · áudio ${result.audio_seconds.toFixed(2)} s · RTF ${result.real_time_factor.toFixed(2)}`;
  setStatus("Reproduzindo resposta…", "connected");
  await new Promise((resolve) => {
    window.setTimeout(resolve, result.audio_seconds * 1000);
  });
  setStatus("Pronto para outra frase", "connected");
}

async function configureLoopback() {
  if (!peerId) {
    return;
  }
  const response = await fetch(`/api/webrtc/peers/${peerId}/loopback`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled: loopbackCheckbox.checked }),
  });
  if (!response.ok) {
    throw new Error(await responseError(response));
  }
}

async function configureAutomaticConversation() {
  if (!peerId) {
    return;
  }
  const response = await fetch(`/api/webrtc/peers/${peerId}/conversation`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled: automaticCheckbox.checked }),
  });
  if (!response.ok) {
    throw new Error(await responseError(response));
  }
  recordButton.disabled = automaticCheckbox.checked;
}

function openConversationEvents() {
  if (!peerId) {
    return;
  }
  eventSource?.close();
  eventSource = new EventSource(`/api/webrtc/peers/${peerId}/events`);
  eventSource.addEventListener("ready", () => {
    receivingAutomaticResponse = false;
    setStatus("Ouvindo — fale quando quiser", "connected");
  });
  eventSource.addEventListener("manual", () => {
    setStatus("Conectado — gravação manual", "connected");
  });
  eventSource.addEventListener("speech_started", () => {
    transcriptText.textContent = "Ouvindo…";
    metricsText.textContent = "";
    assistantText.textContent = "Aguardando a transcrição…";
    assistantMetricsText.textContent = "";
    receivingAutomaticResponse = false;
    setStatus("Fala detectada", "recording");
  });
  eventSource.addEventListener("interrupted", (message) => {
    const result = JSON.parse(message.data);
    const phase = result.phase === "playback" ? "reprodução" : "processamento";
    assistantMetricsText.textContent += ` · interrompida durante ${phase}`;
    setStatus("Resposta interrompida — ouvindo", "recording");
  });
  eventSource.addEventListener("speech_ended", () => {
    setStatus("Fim da fala detectado", "connecting");
  });
  eventSource.addEventListener("transcribing", () => {
    setStatus("Transcrevendo no Raspberry Pi…", "connecting");
  });
  eventSource.addEventListener("transcript", (message) => {
    const result = JSON.parse(message.data);
    transcriptText.textContent = result.text || "Nenhuma fala reconhecida.";
    metricsText.textContent = `${result.audio_seconds.toFixed(2)} s de áudio · ${result.processing_seconds.toFixed(2)} s · RTF ${result.real_time_factor.toFixed(2)}`;
    setStatus("Consultando a OpenAI…", "connecting");
  });
  eventSource.addEventListener("assistant_delta", (message) => {
    if (!receivingAutomaticResponse) {
      assistantText.textContent = "";
      receivingAutomaticResponse = true;
    }
    assistantText.textContent += JSON.parse(message.data).text;
    setStatus("Recebendo resposta…", "connecting");
  });
  eventSource.addEventListener("assistant_done", (message) => {
    const result = JSON.parse(message.data);
    assistantMetricsText.textContent = `${result.model} · primeiro texto ${result.first_text_seconds.toFixed(2)} s · total ${result.total_seconds.toFixed(2)} s`;
    setStatus("Sintetizando voz no Raspberry Pi…", "connecting");
  });
  eventSource.addEventListener("tts_chunk", () => {
    setStatus("Reproduzindo resposta…", "connected");
  });
  eventSource.addEventListener("tts_done", (message) => {
    const result = JSON.parse(message.data);
    assistantMetricsText.textContent += ` · voz ${result.processing_seconds.toFixed(2)} s · áudio ${result.audio_seconds.toFixed(2)} s · RTF ${result.real_time_factor.toFixed(2)}`;
    setStatus("Reproduzindo resposta…", "connected");
  });
  eventSource.addEventListener("error", (message) => {
    if (message.data) {
      errorText.textContent = JSON.parse(message.data).message;
      setStatus("Conectado", "connected");
    }
  });
}

async function closeSession({ notifyServer = true } = {}) {
  const closingPeerId = peerId;
  peerId = null;
  capturing = false;
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
  }
  if (localStream) {
    localStream.getTracks().forEach((track) => track.stop());
    localStream = null;
  }
  remoteAudio.srcObject = null;

  if (notifyServer && closingPeerId) {
    try {
      await fetch(`/api/webrtc/peers/${closingPeerId}`, { method: "DELETE" });
    } catch {
      // The server also removes peers when WebRTC closes.
    }
  }

  startButton.disabled = false;
  recordButton.disabled = true;
  recordButton.textContent = "Começar a falar";
  stopButton.disabled = true;
  setStatus("Desconectado");
}

async function toggleCapture() {
  if (!peerId) {
    return;
  }
  errorText.textContent = "";
  recordButton.disabled = true;

  try {
    if (!capturing) {
      const response = await fetch(
        `/api/webrtc/peers/${peerId}/transcription/start`,
        { method: "POST" },
      );
      if (!response.ok) {
        throw new Error(await responseError(response));
      }
      capturing = true;
      transcriptText.textContent = "Ouvindo…";
      metricsText.textContent = "";
      assistantText.textContent = "Aguardando a transcrição…";
      assistantMetricsText.textContent = "";
      recordButton.textContent = "Finalizar e transcrever";
      setStatus("Gravando — fale agora", "recording");
    } else {
      capturing = false;
      recordButton.textContent = "Começar a falar";
      setStatus("Transcrevendo no Raspberry Pi…", "connecting");
      const response = await fetch(
        `/api/webrtc/peers/${peerId}/transcription/finish`,
        { method: "POST" },
      );
      if (!response.ok) {
        throw new Error(await responseError(response));
      }
      const result = await response.json();
      transcriptText.textContent = result.text || "Nenhuma fala reconhecida.";
      metricsText.textContent = `${result.audio_seconds.toFixed(2)} s de áudio · ${result.processing_seconds.toFixed(2)} s · RTF ${result.real_time_factor.toFixed(2)}`;
      if (result.text) {
        await streamAssistantResponse(result.text);
      } else {
        assistantText.textContent = "Nenhuma pergunta foi enviada.";
        setStatus("Pronto para outra frase", "connected");
      }
    }
  } catch (error) {
    capturing = false;
    recordButton.textContent = "Começar a falar";
    errorText.textContent = error.message;
    setStatus("Conectado", "connected");
  } finally {
    recordButton.disabled = !peerId;
  }
}

async function startSession() {
  startButton.disabled = true;
  stopButton.disabled = false;
  errorText.textContent = "";
  setStatus("Solicitando microfone…", "connecting");

  try {
    localStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });

    peerConnection = new RTCPeerConnection({ iceServers: [] });
    localStream.getAudioTracks().forEach((track) => {
      peerConnection.addTrack(track, localStream);
    });

    peerConnection.addEventListener("track", async (event) => {
      remoteAudio.srcObject = event.streams[0] ?? new MediaStream([event.track]);
      remoteAudio.muted = false;
      try {
        await remoteAudio.play();
      } catch (error) {
        errorText.textContent = `O navegador bloqueou a reprodução: ${error.message}`;
      }
    });

    peerConnection.addEventListener("connectionstatechange", () => {
      const state = peerConnection?.connectionState;
      if (state === "connected") {
        recordButton.disabled = automaticCheckbox.checked;
        setStatus(
          automaticCheckbox.checked
            ? "Conectado — iniciando conversa automática"
            : "Conectado — pronto para gravar",
          "connected",
        );
      } else if (["failed", "disconnected", "closed"].includes(state)) {
        if (state === "failed") {
          errorText.textContent = "A conexão WebRTC falhou. Tente novamente.";
        }
        void closeSession();
      } else {
        setStatus(`WebRTC: ${state}`, "connecting");
      }
    });

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    await waitForIceGatheringComplete(peerConnection);

    const response = await fetch("/api/webrtc/offer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(peerConnection.localDescription),
    });
    if (!response.ok) {
      throw new Error(`O servidor recusou a negociação (${response.status})`);
    }

    const answer = await response.json();
    peerId = answer.peer_id;
    await peerConnection.setRemoteDescription({
      sdp: answer.sdp,
      type: answer.type,
    });
    await configureLoopback();
    openConversationEvents();
    setStatus("Ativando conversa…", "connecting");
    await configureAutomaticConversation();
  } catch (error) {
    errorText.textContent = error.message;
    await closeSession();
  }
}

loopbackCheckbox.addEventListener("change", async () => {
  try {
    await configureLoopback();
  } catch (error) {
    errorText.textContent = error.message;
  }
});
automaticCheckbox.addEventListener("change", async () => {
  try {
    await configureAutomaticConversation();
  } catch (error) {
    errorText.textContent = error.message;
  }
});
startButton.addEventListener("click", startSession);
recordButton.addEventListener("click", toggleCapture);
stopButton.addEventListener("click", () => closeSession());
window.addEventListener("pagehide", () => {
  void closeSession();
});
