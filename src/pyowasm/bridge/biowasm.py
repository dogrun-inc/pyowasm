import js
from pyodide.ffi import to_js

class BiowasmBridge:
    """
    JavaScript側のAioliライブラリを介してWasmバイオ情報学ツールを呼び出すためのブリッジ。
    """

    def __init__(self):
        self.initialized = False
        self._clis = {}

    async def _get_cli(self, tool: str):
        """
        AioliのCLIインスタンスを取得または生成します。
        """
        if tool not in self._clis:
            js.console.log(f"[Pyowasm] Initializing Aioli tool: {tool}")
            try:
                cli = await js.Aioli.new(tool)
                self._clis[tool] = cli
            except Exception as e:
                js.console.error(f"[Pyowasm] Failed to initialize Aioli: {str(e)}")
                raise e
        return self._clis[tool]

    async def run_tool(self, tool: str, args: str) -> str:
        """
        Wasmツールを実行します。
        """
        try:
            cli = await self._get_cli(tool)
            js.console.log(f"[Pyowasm] Executing: {tool} {args}")
            result = await cli.exec(args)
            return str(result)
        except Exception as e:
            error_msg = f"Wasm実行エラー ({tool}): {str(e)}"
            js.console.error(f"[Pyowasm] {error_msg}")
            return error_msg

    def write_to_vfs(self, filename: str, content: str) -> str:
        """
        Python側の文字列データをEmscriptenの仮想FSに書き出します。
        """
        try:
            js.FS.writeFile(filename, content)
            js.console.log(f"[Pyowasm] File written to VFS: {filename} ({len(content)} bytes)")
            return filename
        except Exception as e:
            js.console.error(f"[Pyowasm] Failed to write to VFS: {str(e)}")
            # ローカル環境用（stlite外での動作を考慮）
            import os
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
            with open(filename, "w") as f:
                f.write(content)
            return filename

bridge = BiowasmBridge()
