const startButton = document.querySelector("#start");
const stopButton = document.querySelector("#stop");
const statusText = document.querySelector("#status");
const statusDot = document.querySelector("#status-dot");
const errorText = document.querySelector("#error");
const remoteAudio = document.querySelector("#remote-audio");

let peerConnection = null;
let localStream = null;
let peerId = null;

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

async function closeSession({ notifyServer = true } = {}) {
  const closingPeerId = peerId;
  peerId = null;

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
      // The browser session is already closed; server cleanup also handles failures.
    }
  }

  startButton.disabled = false;
  stopButton.disabled = true;
  setStatus("Desconectado");
}

async function startSession() {
  startButton.disabled = true;
  stopButton.disabled = false;
  errorText.textContent = "";
  setStatus("Solicitando microfone…", "connecting");

  try {
    localStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
      video: false,
    });

    peerConnection = new RTCPeerConnection({ iceServers: [] });
    localStream.getAudioTracks().forEach((track) => {
      peerConnection.addTrack(track, localStream);
    });

    peerConnection.addEventListener("track", async (event) => {
      remoteAudio.srcObject = event.streams[0] ?? new MediaStream([event.track]);
      try {
        await remoteAudio.play();
      } catch (error) {
        errorText.textContent = `O navegador bloqueou a reprodução: ${error.message}`;
      }
    });

    peerConnection.addEventListener("connectionstatechange", () => {
      const state = peerConnection?.connectionState;
      if (state === "connected") {
        setStatus("Conectado — fale no microfone", "connected");
      } else if (["failed", "disconnected", "closed"].includes(state)) {
        if (state === "failed") {
          errorText.textContent = "A conexão WebRTC falhou. Tente iniciar novamente.";
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
    setStatus("Conectando áudio…", "connecting");
  } catch (error) {
    errorText.textContent = error.message;
    await closeSession();
  }
}

startButton.addEventListener("click", startSession);
stopButton.addEventListener("click", () => closeSession());
window.addEventListener("pagehide", () => {
  void closeSession();
});
