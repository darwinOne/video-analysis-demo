import asyncio
import cv2
import os
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaRelay
import av
from av import VideoFrame
from av import open as av_open
import time

# CAMERA_SOURCES = {
#      0 : "rtsp://admin:aery2021!@192.168.45.167:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif",
#      1 : "rtsp://admin:aery2021!@192.168.45.165:554/stream1",
#     2 : "rtsp://admin:aery2021!@192.168.45.168:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif",
#     3 : "rtsp://admin:aery2021!@192.168.45.169:554/stream1"
#  }

CAMERA_SOURCES = {
    0: "videos/test.mp4",
    1: "videos/test2.mp4",
    # 2: "videos/test1.mp4",
    # 3: "videos/test2.mp4",
}

relay = MediaRelay()
pcs = set()

camera_tracks = {}

class CameraStreamTrack(VideoStreamTrack):
    def __init__(self, source_path):
        super().__init__()
        self.source_path = source_path
        try:
            self.container = av.open(source_path, options={
                "rtsp_transport": "tcp",    # Force TCP for reliability
                "buffer_size": "1048576",   # 1MB buffer
                "fflags": "nobuffer",
                "flags": "low_delay",
                "stimeout": "5000000",      # 5 seconds timeout in µs
                "max_delay": "500000",      # 0.5 seconds max delay in µs
            })
        except av.AVError as e:
            raise RuntimeError(f"Failed to open camera stream: {e}")

        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "AUTO"      # Enable multi-thread decoding

        self.start_time = time.time()

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        # Read next frame with retry loop
        frame = None
        for packet in self.container.demux(self.stream):
            for f in packet.decode():
                frame = f # always get the latest decode frame
                # break
            if frame:
                break

        if frame is None:
            print(f"[WARN] Stream stuck or ended, rewinding: {self.source_path}")
            # self.container.seek(0)
            try:
                self.container.seek(0, any_frame=False, backward=True)
            except av.AVError as e:
                print(f"[ERROR] Seek failed: {e}")
            return await self.recv()

        # Optional: convert pixel format to avoid FFmpeg warnings
        # frame = frame.to_rgb()

        # Convert only if needed: minimize processing
        # if frame.format.name != "yuv420p":
        #     frame = frame.reformat(format="yuv420p")  # For efficient WebRTC encoding

        # Set timing
        frame.pts = pts
        frame.time_base = time_base

        # Log latency
        now = time.time()
        latency = (now - self.start_time) * 1000
        print(f"[INFO] Frame latency: {latency:.2f} ms")
        self.start_time = now

        return frame

async def index(request):
    return web.FileResponse("static/client.html")

async def offer(request):
    params = await request.json()
    cam_index = int(request.query.get("cam", 0))
    source_path = CAMERA_SOURCES.get(cam_index)

    if not source_path:
        return web.Response(status=404, text="Camera source not found")

    stun_config = RTCConfiguration([
        RTCIceServer(urls=["stun:stun.l.google.com:19302"])
    ])

    pc = RTCPeerConnection(configuration=stun_config)
    pcs.add(pc)

    if cam_index not in camera_tracks:
        print(f"Opening persistent camera {cam_index}: {source_path}")
        camera_tracks[cam_index] = CameraStreamTrack(source_path)

    pc.addTrack(relay.subscribe(camera_tracks[cam_index]))

    await pc.setRemoteDescription(RTCSessionDescription(sdp=params["sdp"], type=params["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

async def on_shutdown(app):
    print("Shutting down...")
    for pc in pcs:
        await pc.close()
    pcs.clear()
   
    for track in camera_tracks.values():
        try:
            if track.container and track.container.closed is False:
                track.container.close()
        except Exception as e:
            print(f"[WARN] Failed to close container: {e}")
    camera_tracks.clear()


app = web.Application()
app.on_shutdown.append(on_shutdown)
app.router.add_get("/", index)
app.router.add_post("/offer", offer)
app.router.add_static("/static/", path="static")

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
