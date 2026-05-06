import js
import json
from pyodide.ffi import to_js

class BiowasmBridge:
    """
    JavaScript側のAioliライブラリを介してWasmバイオ情報学ツールを呼び出すためのブリッジ。
    """

    def __init__(self):
        self.initialized = True

    async def run_tool(self, tool: str, args: str, files: dict[str, str] = None) -> str:
        """
        Wasmツールを実行します。
        files: { "filename": "content" } の辞書。Aioliにマウントされます。
        """
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
                            const matches = command.match(/[^\s"']+|"(?:\\.|[^"])*"|'(?:\\.|[^'])*'/g);
                            return matches || [];
                        }};

                        const normalizeToken = (token) => {{
                            if (token.length >= 2 && token[0] === '"' && token[token.length - 1] === '"') {{
                                return token.slice(1, -1).replace(/\\"/g, '"');
                            }}
                            if (token.length >= 2 && token[0] === "'" && token[token.length - 1] === "'") {{
                                return token.slice(1, -1).replace(/\\'/g, "'");
                            }}
                            return token;
                        }};

                        let commandTokens = tokenizeCommand(commandToExec);

                        for (let i = 0; i < filesToMount.length; i++) {{
                            const originalName = filesToMount[i].name;
                            const mountedPath = resolvePath(mountedPaths[i]);
                            if (mountedPath) {{
                                commandTokens = commandTokens.map((token) =>
                                    normalizeToken(token) === originalName ? JSON.stringify(mountedPath) : token
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

    async def makeblastdb(self, fasta_content: str, db_name: str = "mydb", db_type: str = "prot") -> str:
        """
        配列データをデータベース化します。
        """
        input_file = f"{db_name}.fasta"
        # BLAST+ (blast/2.11.0) を使用
        command = f"makeblastdb -in {input_file} -dbtype {db_type} -out {db_name}"
        return await self.run_tool("blast/2.11.0", command, files={input_file: fasta_content})

    async def blastp(self, query_content: str, db_name: str, options: str = "-outfmt 6") -> str:
        """
        BLASTP検索を実行します。
        TSV形式（-outfmt 6）で結果を回収します。
        """
        query_file = "query.fasta"
        # 同一の Aioli インスタンス（blast/2.11.0）を再利用することで、
        # makeblastdb で作成された DB ファイルが worker 側の VFS に残っていることを期待します。
        command = f"blastp -query {query_file} -db {db_name} {options}"
        return await self.run_tool("blast/2.11.0", command, files={query_file: query_content})

    async def seqtk(self, command: str, files: dict[str, str] = None) -> str:
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
        try:
            js.FS.writeFile(filename, content)
            js._pyowasm_upload_text = content
            js.console.log(f"[Pyowasm] File written to VFS: {filename} ({len(content)} bytes)")
            return filename
        except Exception as e:
            js.console.error(f"[Pyowasm] Failed to write to VFS: {str(e)}")
            js._pyowasm_upload_text = content
            import os
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
            with open(filename, "w") as f:
                f.write(content)
            return filename

bridge = BiowasmBridge()
