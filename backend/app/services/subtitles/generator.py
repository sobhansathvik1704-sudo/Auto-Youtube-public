from datetime import timedelta

import srt

from app.db.models.scene import Scene


def generate_srt_content(scenes: list[Scene]) -> str:
    subtitles = []
    for index, scene in enumerate(scenes, start=1):
        subtitles.append(
            srt.Subtitle(
                index=index,
                start=timedelta(milliseconds=scene.start_ms),
                end=timedelta(milliseconds=scene.end_ms),
                content=scene.on_screen_text or scene.narration_text,
            )
        )
    return srt.compose(subtitles)