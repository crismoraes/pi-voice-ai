"""HTTP signaling endpoints for browser WebRTC sessions."""

from typing import Literal

from aiortc import RTCSessionDescription
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.stt.base import SpeechToTextUnavailableError
from app.webrtc.manager import (
    AudioDurationError,
    AudioTrackUnavailableError,
    CaptureStateError,
    PeerNotFoundError,
    peer_manager,
)

router = APIRouter(prefix="/api/webrtc", tags=["webrtc"])


class Offer(BaseModel):
    sdp: str
    type: Literal["offer"]


class Answer(BaseModel):
    sdp: str
    type: Literal["answer"]
    peer_id: str


class Transcription(BaseModel):
    text: str
    audio_seconds: float
    processing_seconds: float
    real_time_factor: float


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


@router.post(
    "/peers/{peer_id}/transcription/start",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def start_transcription(peer_id: str) -> None:
    try:
        peer_manager.start_transcription(peer_id)
    except PeerNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WebRTC peer not found") from exc
    except (AudioTrackUnavailableError, CaptureStateError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post(
    "/peers/{peer_id}/transcription/finish",
    response_model=Transcription,
)
async def finish_transcription(peer_id: str) -> Transcription:
    try:
        result = await peer_manager.finish_transcription(peer_id)
    except PeerNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WebRTC peer not found") from exc
    except CaptureStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AudioDurationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except SpeechToTextUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    return Transcription(
        text=result.text,
        audio_seconds=round(result.audio_seconds, 3),
        processing_seconds=round(result.processing_seconds, 3),
        real_time_factor=round(result.real_time_factor, 3),
    )
