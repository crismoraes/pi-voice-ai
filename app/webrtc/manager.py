"""Lifecycle management for browser WebRTC peer connections."""

import asyncio
import logging
from uuid import uuid4

from aiortc import RTCPeerConnection, RTCSessionDescription

logger = logging.getLogger("pi_voice_ai.webrtc")


class PeerConnectionManager:
    """Create, track and close WebRTC audio loopback peers."""

    def __init__(self) -> None:
        self._peers: dict[str, RTCPeerConnection] = {}

    @property
    def active_peer_count(self) -> int:
        return len(self._peers)

    async def accept_offer(
        self,
        session_description: RTCSessionDescription,
    ) -> tuple[str, RTCSessionDescription]:
        peer_id = uuid4().hex
        peer_connection = RTCPeerConnection()
        self._peers[peer_id] = peer_connection

        @peer_connection.on("track")
        def on_track(track) -> None:
            logger.info(
                "WEBRTC_TRACK_RECEIVED",
                extra={"peer_id": peer_id, "kind": track.kind},
            )
            if track.kind == "audio":
                peer_connection.addTrack(track)

        @peer_connection.on("connectionstatechange")
        async def on_connection_state_change() -> None:
            state = peer_connection.connectionState
            logger.info(
                "WEBRTC_CONNECTION_STATE",
                extra={"peer_id": peer_id, "state": state},
            )
            if state == "connected":
                logger.info("WEBRTC_CONNECTED", extra={"peer_id": peer_id})
            elif state in {"failed", "closed"}:
                await self.close(peer_id)

        try:
            await peer_connection.setRemoteDescription(session_description)
            answer = await peer_connection.createAnswer()
            await peer_connection.setLocalDescription(answer)
        except Exception:
            logger.exception("WEBRTC_NEGOTIATION_FAILED", extra={"peer_id": peer_id})
            await self.close(peer_id)
            raise

        local_description = peer_connection.localDescription
        if local_description is None:
            await self.close(peer_id)
            raise RuntimeError("WebRTC answer was not created")
        return peer_id, local_description

    async def close(self, peer_id: str) -> bool:
        peer_connection = self._peers.pop(peer_id, None)
        if peer_connection is None:
            return False
        await peer_connection.close()
        logger.info("WEBRTC_DISCONNECTED", extra={"peer_id": peer_id})
        return True

    async def close_all(self) -> None:
        peer_ids = tuple(self._peers)
        if peer_ids:
            await asyncio.gather(*(self.close(peer_id) for peer_id in peer_ids))


peer_manager = PeerConnectionManager()
