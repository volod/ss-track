"""Fake PIL.Image: just enough for the worker to hand frames to the fake embedders."""


class Image:
    def __init__(self, mode: str, size: tuple[int, int], data: bytes) -> None:
        self.mode, self.size, self._data = mode, size, bytes(data)

    def tobytes(self) -> bytes:
        return self._data


def frombytes(mode: str, size: tuple[int, int], data: bytes) -> Image:
    return Image(mode, size, data)
