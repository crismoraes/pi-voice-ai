"""HTTP signaling endpoints for browser WebRTC sessions."""

from typing import Literal

from aiortc import RTCSessionDescription
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.webrtc.manager import peer_manager

router = APIRouter(prefix="/api/webrtc", tags=["webrtc"])


class Offer(BaseModel):
    sdp: str
    type: Literal["offer"]


class Answer(BaseModel):
    sdp: str
    type: Literal["answer"]
    peer_id: str


@router.post("/offer", response_model=Answer)
async def create_answer(offer: Offer) -> Answer:
    try:
        peer_id, answer = await peer_manager.accept_offer(
            RTCSessionDescription(sdp=offer.sdp, type=offer.type)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid WebRTC offer",
        ) from exc
    return Answer(sdp=answer.sdp, type="answer", peer_id=peer_id)


@router.delete("/peers/{peer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_peer(peer_id: str) -> None:
    await peer_manager.close(peer_id)
