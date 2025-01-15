import os


class FileWithProgress:
    def __init__(self, file_path, pbar):
        self._file_path = file_path
        self._f = open(file_path, "rb")
        self._pbar = pbar

    def __len__(self):
        return os.path.getsize(self._file_path)

    def read(self, size=-1):
        """
        Read up to size bytes from the object and update the progress bar.
        @param size:
        @return:
        """
        data = self._f.read(size)
        if data:
            self._pbar.update(len(data))
        return data

    def close(self):
        if not self._f.closed:
            self._f.close()

    def __iter__(self):
        """
        Iterate over the file and update the progress bar.
        @return:
        """
        for chunk in iter(lambda: self._f.read(1024 * 1024), b""):
            self._pbar.update(len(chunk))
            yield chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
