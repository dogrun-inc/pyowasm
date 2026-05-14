import json
from typing import Any

try:
    import js  # type: ignore
except ImportError:
    js = None  # type: ignore[assignment]

try:
    from pyodide.ffi import to_js  # type: ignore
except ImportError:
    def to_js(value: Any) -> Any:
        """Pyodide 非依存環境向けのフォールバック。"""
        return value

class BiowasmBridge:
    """
    JavaScript側のAioliライブラリを介してWasmバイオ情報学ツールを呼び出すためのブリッジ。
    """

    def __init__(self):
        self.initialized = js is not None
        self._vfs_fallback_notified = False

    def _can_use_js_vfs(self) -> bool:
        """JavaScript 側の VFS API が利用可能か判定する。"""
        if js is None:
            return False
        return hasattr(js, "FS") and hasattr(js.FS, "writeFile")

    @staticmethod
    def is_available() -> bool:
        """Wasm ブリッジが利用可能かどうかを返す。"""
        return js is not None

    @staticmethod
    def supports_runtime_stack_switching() -> bool:
        """現在の JavaScript ランタイムが stack switching をサポートするか判定する。"""
        if js is None:
            return False
        try:
            return bool(js.eval("typeof WebAssembly === 'object' && typeof WebAssembly.Suspending === 'function'"))
        except Exception:
            return False

    @staticmethod
    def unavailable_message() -> str:
        """Wasm 未対応環境で表示するメッセージを返す。"""
        return (
            "この実行環境では Wasm ツールを利用できません。"
            "開発環境の Streamlit 実行では `import js` が利用不可なため、"
            "Wasm 機能（seqtk など）は無効です。"
            "ブラウザ版（index.html / stlite）で実行してください。"
        )

    @staticmethod
    def _quote_cli_arg(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def _format_tool_success_data(data: Any) -> str:
        """Wasm ツールの成功レスポンスを文字列へ正規化する。"""
        if isinstance(data, dict):
            stdout = str(data.get("stdout") or "")
            stderr = str(data.get("stderr") or "")
            exit_code = data.get("exitCode", data.get("code"))

            if exit_code not in (None, 0):
                message = stderr or stdout or str(data)
                return f"Wasm実行エラー: {message}"

            return stdout or stderr or json.dumps(data, ensure_ascii=False)

        return str(data)

    def start_tool_job(self, tool: str, args: str, files: dict[str, str] | None = None) -> str:
        """Wasm ツール実行ジョブを開始し、ジョブIDを返す。"""
        if not self.is_available():
            return f"ERROR:{self.unavailable_message()}"

        tool_js = json.dumps(tool, ensure_ascii=False)
        args_js = json.dumps(args, ensure_ascii=False)
        files_js = json.dumps(files or {}, ensure_ascii=False)
        legacy_upload_js = "true" if (not files and "input.fasta" in args) else "false"

        js_code = f"""
        (() => {{
            if (!globalThis._pyowasm_jobs) globalThis._pyowasm_jobs = {{}};
            const jobId = `job_${{Date.now()}}_${{Math.random().toString(36).slice(2)}}`;
            globalThis._pyowasm_jobs[jobId] = {{ status: "running", debug: [] }};

            (async () => {{
                const debugLogs = [];
                const log = (...items) => {{
                    const line = items
                        .map((item) => {{
                            if (typeof item === "string") return item;
                            try {{
                                return JSON.stringify(item);
                            }} catch (_e) {{
                                return String(item);
                            }}
                        }})
                        .join(" ");
                    debugLogs.push(line);
                    try {{
                        console.log("[Pyowasm][debug]", ...items);
                    }} catch (_e) {{}}
                }};

                try {{
                    const toolName = {tool_js};
                    const rawArgs = {args_js};
                    const filesObj = {files_js};

                    log("start", {{ tool: toolName, args: rawArgs }});

                    if (typeof Aioli === 'undefined') {{
                        const module = await import('https://biowasm.com/cdn/v3/aioli.js');
                        if (module.default) {{
                            globalThis.Aioli = module.default;
                        }}
                    }}

                    if (typeof globalThis.Aioli !== 'function') {{
                         throw new Error("Aioli could not be loaded as a constructor.");
                    }}

                    if (!globalThis._pyowasm_clis) globalThis._pyowasm_clis = {{}};
                    if (!globalThis._pyowasm_clis[toolName]) {{
                        globalThis._pyowasm_clis[toolName] = await new Aioli([toolName]);
                    }}
                    const cli = globalThis._pyowasm_clis[toolName];

                    let commandToExec = rawArgs;
                    const filesToMount = [];

                    for (const [name, content] of Object.entries(filesObj)) {{
                        filesToMount.push({{
                            name: name,
                            data: new Blob([new TextEncoder().encode(content)])
                        }});
                    }}

                    if ({legacy_upload_js} && !filesToMount.some(f => f.name === "input.fasta")) {{
                        const uploadText = globalThis._pyowasm_upload_text;
                        if (typeof uploadText === "string") {{
                            filesToMount.push({{
                                name: "input.fasta",
                                data: new Blob([new TextEncoder().encode(uploadText)])
                            }});
                        }}
                    }}

                    if (filesToMount.length > 0) {{
                        const mountedPaths = await cli.mount(filesToMount);

                        const resolvePath = (val) => {{
                            if (!val) return null;
                            if (typeof val === "string") return val;
                            return val.path || val.mountPath || val.file || val.name || null;
                        }};

                        const tokenizeCommand = (command) => {{
                            const matches = command.match(/[^\\s"']+|"(?:\\\\.|[^"])*"|'(?:\\\\.|[^'])*'/g);
                            return matches || [];
                        }};

                        const normalizeToken = (token) => {{
                            if (token.length >= 2 && token[0] === '"' && token[token.length - 1] === '"') {{
                                return token.slice(1, -1).replace(/\\\\"/g, '"');
                            }}
                            if (token.length >= 2 && token[0] === "'" && token[token.length - 1] === "'") {{
                                return token.slice(1, -1).replace(/\\\\'/g, "'");
                            }}
                            return token;
                        }};

                        const formatPathToken = (path) => (/\\s/.test(path) ? JSON.stringify(path) : path);

                        let commandTokens = tokenizeCommand(commandToExec);
                        for (let i = 0; i < filesToMount.length; i++) {{
                            const originalName = filesToMount[i].name;
                            const mountedPath = resolvePath(mountedPaths[i]);
                            if (mountedPath) {{
                                commandTokens = commandTokens.map((token) =>
                                    normalizeToken(token) === originalName ? formatPathToken(mountedPath) : token
                                );
                            }}
                        }}
                        commandToExec = commandTokens.join(" ");
                    }}

                    const result = await cli.exec(commandToExec);
                    globalThis._pyowasm_jobs[jobId] = {{
                        status: "success",
                        data: result,
                        debug: debugLogs,
                    }};
                }} catch (e) {{
                    globalThis._pyowasm_jobs[jobId] = {{
                        status: "error",
                        message: e?.message || String(e),
                        debug: debugLogs,
                    }};
                }}
            }})();

            return jobId;
        }})()
        """

        try:
            return str(js.eval(js_code))
        except Exception as error:
            return f"ERROR:ジョブ開始に失敗しました: {error}"

    def get_tool_job_result(self, job_id: str) -> dict[str, str]:
        """ジョブ状態を取得し、表示可能な結果へ整形して返す。"""
        if not self.is_available():
            return {"status": "error", "result": self.unavailable_message()}

        job_id_js = json.dumps(job_id, ensure_ascii=False)
        js_code = f"""
        (() => {{
            const job = globalThis._pyowasm_jobs?.[{job_id_js}];
            if (!job) {{
                return JSON.stringify({{ status: "missing" }});
            }}
            return JSON.stringify(job);
        }})()
        """

        try:
            raw = str(js.eval(js_code))
            payload = json.loads(raw)
        except Exception as error:
            return {"status": "error", "result": f"ジョブ状態取得に失敗しました: {error}"}

        status = payload.get("status", "missing")
        debug_logs = payload.get("debug") or []
        trace = "\n".join(f"[JS] {line}" for line in debug_logs)

        if status == "running":
            return {"status": "running", "result": "実行中"}

        if status == "success":
            data = payload.get("data")
            result = self._format_tool_success_data(data)
            if "Wasm実行エラー:" in result and trace:
                result = f"{result}\n\n--- Debug Trace ---\n{trace}"
            return {"status": "success", "result": result}

        if status == "error":
            message = str(payload.get("message") or "unknown error")
            result = f"Wasm実行エラー: {message}"
            if trace:
                result = f"{result}\n\n--- Debug Trace ---\n{trace}"
            return {"status": "error", "result": result}

        return {"status": "missing", "result": "ジョブが見つかりません。"}

    def clear_tool_job(self, job_id: str) -> None:
        """完了したジョブ情報を削除する。"""
        if not self.is_available():
            return

        job_id_js = json.dumps(job_id, ensure_ascii=False)
        js_code = f"""
        (() => {{
            if (globalThis._pyowasm_jobs) {{
                delete globalThis._pyowasm_jobs[{job_id_js}];
            }}
        }})()
        """
        try:
            js.eval(js_code)
        except Exception:
            return

    async def run_tool(self, tool: str, args: str, files: dict[str, str] | None = None) -> str:
        """
        Wasmツールを実行します。
        files: { "filename": "content" } の辞書。Aioliにマウントされます。
        """
        if not self.is_available():
            return self.unavailable_message()

        py_debug = [
            f"[PY] tool={tool}",
            f"[PY] args={args}",
        ]

        # JSに渡すためのファイルデータを一時的にグローバルに配置（eval内で参照するため）
        if files:
            js._pyowasm_files = to_js(files)
        else:
            js._pyowasm_files = None

        try:
            # 入力ファイルの有無を判定
            use_legacy_upload = (not files) and ("input.fasta" in args)
            py_debug.append(f"[PY] has_files={bool(files) or use_legacy_upload}")

            # f-string でJSコードを組み立てる際の注入/構文崩れを防ぐため、
            # 外部入力は JSON 文字列リテラルとして埋め込む。
            tool_js = json.dumps(tool, ensure_ascii=False)
            args_js = json.dumps(args, ensure_ascii=False)
            legacy_upload_js = "true" if use_legacy_upload else "false"

            js_code = f"""
            (async () => {{
                const debugLogs = [];
                const log = (...items) => {{
                    const line = items
                        .map((item) => {{
                            if (typeof item === "string") return item;
                            try {{
                                return JSON.stringify(item);
                            }} catch (_e) {{
                                return String(item);
                            }}
                        }})
                        .join(" ");
                    debugLogs.push(line);
                    try {{
                        console.log("[Pyowasm][debug]", ...items);
                    }} catch (_e) {{}}
                }};

                try {{
                    const toolName = {tool_js};
                    const rawArgs = {args_js};

                    log("start", {{ tool: toolName, args: rawArgs }});

                    // 1. Aioli ロード
                    if (typeof Aioli === 'undefined') {{
                        log("Aioli not found, trying dynamic import");
                        try {{
                            const module = await import('https://biowasm.com/cdn/v3/aioli.js');
                            if (module.default) {{
                                globalThis.Aioli = module.default;
                                log("Aioli resolved from module.default");
                            }} else if (typeof globalThis.Aioli === 'undefined') {{
                                for (const key in module) {{
                                    if (typeof module[key] === 'function') {{
                                        globalThis.Aioli = module[key];
                                        log("Aioli resolved from module key", key);
                                        break;
                                    }}
                                }}
                            }}
                        }} catch (e) {{
                            log("dynamic import failed", e?.message || String(e));
                        }}
                    }}

                    if (typeof globalThis.Aioli !== 'function') {{
                         throw new Error("Aioli could not be loaded as a constructor.");
                    }}

                    // 2. 初期化
                    if (!globalThis._pyowasm_clis) globalThis._pyowasm_clis = {{}};
                    if (!globalThis._pyowasm_clis[toolName]) {{
                        log("creating new Aioli instance", toolName);
                        globalThis._pyowasm_clis[toolName] = await new Aioli([toolName]);
                    }}
                    const cli = globalThis._pyowasm_clis[toolName];
                    log("cli ready", !!cli);

                    // 3. マウント処理
                    let commandToExec = rawArgs;
                    const filesToMount = [];
                    const jsFiles = globalThis._pyowasm_files;

                    if (jsFiles && typeof jsFiles.entries === "function") {{
                        for (const [name, content] of jsFiles.entries()) {{
                            filesToMount.push({{
                                name: name,
                                data: new Blob([new TextEncoder().encode(content)])
                            }});
                        }}
                    }}

                    // レガシー互換: _pyowasm_upload_text を使用
                    if ({legacy_upload_js} && !filesToMount.some(f => f.name === "input.fasta")) {{
                        const uploadText = globalThis._pyowasm_upload_text;
                        if (typeof uploadText === "string") {{
                            filesToMount.push({{
                                name: "input.fasta",
                                data: new Blob([new TextEncoder().encode(uploadText)])
                            }});
                        }}
                    }}

                    if (filesToMount.length > 0) {{
                        log("mounting files", filesToMount.map(f => f.name));
                        const mountedPaths = await cli.mount(filesToMount);
                        log("mountedPaths", mountedPaths);

                        const resolvePath = (val) => {{
                            if (!val) return null;
                            if (typeof val === "string") return val;
                            return val.path || val.mountPath || val.file || val.name || null;
                        }};

                        const tokenizeCommand = (command) => {{
                            const matches = command.match(/[^\\s"']+|"(?:\\\\.|[^"])*"|'(?:\\\\.|[^'])*'/g);
                            return matches || [];
                        }};

                        const normalizeToken = (token) => {{
                            if (token.length >= 2 && token[0] === '"' && token[token.length - 1] === '"') {{
                                return token.slice(1, -1).replace(/\\\\"/g, '"');
                            }}
                            if (token.length >= 2 && token[0] === "'" && token[token.length - 1] === "'") {{
                                return token.slice(1, -1).replace(/\\\\'/g, "'");
                            }}
                            return token;
                        }};

                        const formatPathToken = (path) => {{
                            if (/\\s/.test(path)) {{
                                return JSON.stringify(path);
                            }}
                            return path;
                        }};

                        let commandTokens = tokenizeCommand(commandToExec);

                        for (let i = 0; i < filesToMount.length; i++) {{
                            const originalName = filesToMount[i].name;
                            const mountedPath = resolvePath(mountedPaths[i]);
                            if (mountedPath) {{
                                commandTokens = commandTokens.map((token) =>
                                    normalizeToken(token) === originalName ? formatPathToken(mountedPath) : token
                                );
                            }}
                        }}
                        commandToExec = commandTokens.join(" ");
                        log("finalCommand", commandToExec);
                    }}

                    log("executing", commandToExec);
                    const result = await cli.exec(commandToExec);
                    log("exec completed");
                    return JSON.stringify({{ status: "success", data: result, debug: debugLogs }});

                }} catch (e) {{
                    log("bridgeError", e?.message || String(e));
                    return JSON.stringify({{ status: "error", message: e.message || String(e), debug: debugLogs }});
                }} finally {{
                    // 一時変数のクリア
                    delete globalThis._pyowasm_files;
                }}
            }})()
            """
            
            js_response_json = await js.eval(js_code)
            py_debug.append(f"[PY] js_response_json={js_response_json}")
            response = json.loads(js_response_json)
            js_debug = response.get("debug") or []
            trace = "\n".join(py_debug + [f"[JS] {line}" for line in js_debug])
            
            if response["status"] == "success":
                data = response.get("data")
                if isinstance(data, dict):
                    stdout = str(data.get("stdout") or "")
                    stderr = str(data.get("stderr") or "")
                    exit_code = data.get("exitCode", data.get("code"))

                    if exit_code not in (None, 0):
                        message = stderr or stdout or str(data)
                        return f"Wasm実行エラー: {message}\n\n--- Debug Trace ---\n{trace}"
                    return stdout or stderr or json.dumps(data, ensure_ascii=False)

                return str(data)
            else:
                return f"Wasm実行エラー: {response['message']}\n\n--- Debug Trace ---\n{trace}"
            
        except Exception as e:
            py_debug.append(f"[PY] exception={str(e)}")
            trace = "\n".join(py_debug)
            return f"ブリッジ通信エラー: {str(e)}\n\n--- Debug Trace ---\n{trace}"

    async def smith_waterman(self, query_sequence: str, subject_sequence: str) -> str:
        """
        seq-align の smith_waterman を実行します。
        2 配列を直接引数で渡し、アラインメント結果のテキストを返します。
        """
        command = (
            f"smith_waterman {self._quote_cli_arg(query_sequence)} "
            f"{self._quote_cli_arg(subject_sequence)}"
        )
        return await self.run_tool("seq-align/smith_waterman/2017.10.18", command)

    async def seqtk(self, command: str, files: dict[str, str] | None = None) -> str:
        """
        seqtkを実行します。
        """
        full_command = command.strip()
        if not full_command.startswith("seqtk"):
            full_command = f"seqtk {full_command}"
        return await self.run_tool("seqtk/1.3", full_command, files=files)

    def write_to_vfs(self, filename: str, content: str) -> str:
        """
        Python側の文字列データをEmscriptenの仮想FSに書き出します。
        """
        if not self.is_available():
            import os

            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
            with open(filename, "w", encoding="utf-8") as file_handle:
                file_handle.write(content)
            return filename

        if not self._can_use_js_vfs():
            js._pyowasm_upload_text = content
            if not self._vfs_fallback_notified:
                try:
                    js.console.warn("[Pyowasm] JS VFS (FS.writeFile) が未対応のため、Python側フォールバックを使用します。")
                except Exception:
                    pass
                self._vfs_fallback_notified = True

            import os
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
            with open(filename, "w", encoding="utf-8") as file_handle:
                file_handle.write(content)
            return filename

        try:
            js.FS.writeFile(filename, content)
            js._pyowasm_upload_text = content
            js.console.log(f"[Pyowasm] File written to VFS: {filename} ({len(content)} bytes)")
            return filename
        except Exception as e:
            try:
                js.console.warn(f"[Pyowasm] VFS書き込みに失敗したためフォールバックします: {str(e)}")
            except Exception:
                pass
            js._pyowasm_upload_text = content
            import os
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            return filename

bridge = BiowasmBridge()
