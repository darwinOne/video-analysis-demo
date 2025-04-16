import asyncio
import cv2
import os
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaRelay
from av import VideoFrame
import time

# CAMERA_SOURCES = {
#     0 : "rtsp://admin:aery2021!@192.168.45.167:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif",
#     1 : "rtsp://admin:aery2021!@192.168.45.165:554/stream1",
#     2 : "rtsp://admin:aery2021!@192.168.45.168:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif",
#     3 : "rtsp://admin:aery2021!@192.168.45.169:554/stream1"
# }

CAMERA_SOURCES = {
    0: "videos/test.mp4",
    1: "videos/test1.mp4",
    2: "videos/test2.mp4",
    3: "videos/test.mp4",
}

relay = MediaRelay()
pcs = set()

class CameraStreamTrack(VideoStreamTrack):
    def __init__(self, source_path):
        super().__init__()
        self.cap = cv2.VideoCapture(source_path)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera: {source_path}")
        
        # Untuk keperluan hitung lantency dan delay
        # self.source_path = source_path

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Hitung delay
        # capture_time = time.time()
        video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base

        # Attach timestamp to video frame
        # video_frame.metadata["capture_time"] = capture_time

        # Log delay (when delivered by aiortc)
        # self._log_latency(video_frame)

        return video_frame
    
    # def _log_latency(self, video_frame):
    #     now = time.time()
    #     capture_time = video_frame.metadata.get("capture_time", now)
    #     latency_ms = (now - capture_time) * 1000
    #     print(f"[{self.source_path}] Latency: {latency_ms:.2f} ms")

async def index(request):
    return web.FileResponse("static/client.html")

async def offer(request):
    params = await request.json()
    cam_index = int(request.query.get("cam", 0))
    source_path = CAMERA_SOURCES.get(cam_index)

    if not source_path:
        return web.Response(status=404, text="Camera source not found")

    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    pc = RTCPeerConnection()
    pcs.add(pc)

    print(f"Opening camera {cam_index}: {source_path}")
    video_track = CameraStreamTrack(source_path)
    pc.addTrack(relay.subscribe(video_track))

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

async def on_shutdown(app):
    print("Shutting down...")
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

app = web.Application()
app.on_shutdown.append(on_shutdown)
app.router.add_get("/", index)
app.router.add_post("/offer", offer)
app.router.add_static("/static/", path="static")

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
