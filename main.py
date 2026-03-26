from fastapi import FastAPI
from video_downloader import VideoDownloaderApp

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


def main():
    video_app = VideoDownloaderApp()
    video_app.protocol("WM_DELETE_WINDOW", video_app.on_closing)
    video_app.mainloop()


if __name__ == "__main__":
    main()
