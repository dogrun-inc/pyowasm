import js
import os
from typing import Optional

class VFSManager:
    """
    PythonとWasm（Emscripten FS）間のファイル同期を管理するクラス。
    """

    @staticmethod
    def write_to_vfs(filename: str, content: str) -> str:
        """
        Python側の文字列データをWasm環境の仮想ファイルシステムに書き出します。
        """
        try:
            # ブラウザ環境（stlite/Pyodide）では js.FS が利用可能
            js.FS.writeFile(filename, content)
            js.console.log(f"[Pyowasm/VFS] File written: {filename} ({len(content)} bytes)")
            return filename
        except AttributeError:
            # ローカル環境用フォールバック
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
            with open(filename, "w") as f:
                f.write(content)
            return filename

    @staticmethod
    def read_from_vfs(filename: str) -> str:
        """
        Wasm環境の仮想ファイルシステムからデータを読み込みます。
        """
        try:
            data = js.FS.readFile(filename, {"encoding": "utf8"})
            return str(data)
        except AttributeError:
            # ローカル環境用フォールバック
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    return f.read()
            raise FileNotFoundError(f"File not found in VFS: {filename}")
