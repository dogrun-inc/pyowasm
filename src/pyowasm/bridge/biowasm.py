import js
import json
from pyodide.ffi import to_js

class BiowasmBridge:
    """
    JavaScript側のAioliライブラリを介してWasmバイオ情報学ツールを呼び出すためのブリッジ。
    """

    def __init__(self):
        self.initialized = True

    async def run_tool(self, tool: str, args: str) -> str:
        """
        Wasmツールを実行します。
        """
        py_debug = [
            f"[PY] tool={tool}",
            f"[PY] args={args}",
        ]

        try:
            # 自動マウント用の事前処理 (Python側でFS操作を行う)
            target_file = "input.fasta"
            has_input_file = target_file in args
            py_debug.append(f"[PY] has_input_file={has_input_file}")
            
            if has_input_file:
                try:
                    # Python側からは js.FS が確実に参照できる前提
                    file_data = js.FS.readFile(target_file)
                    js._pyowasm_upload_data = file_data
                    file_size = int(getattr(file_data, "length", 0) or 0)
                    py_debug.append(f"[PY] FS.readFile ok size={file_size}")
                except Exception as e:
                    js.console.error(f"[Pyowasm] Failed to read {target_file} from Python: {str(e)}")
                    py_debug.append(f"[PY] FS.readFile failed: {str(e)}")
            else:
                py_debug.append("[PY] no input.fasta in args")

            # FS.readFileが失敗しても、write_to_vfsで保持した文字列から再構成できるようにする。
            fallback_text = getattr(js, "_pyowasm_upload_text", None)
            if isinstance(fallback_text, str):
                py_debug.append(f"[PY] upload_text fallback exists len={len(fallback_text)}")
            else:
                py_debug.append("[PY] upload_text fallback missing")

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
                    log("start", {{ tool: "{tool}", args: `{args}` }});

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
                            if (typeof importScripts === 'function') {{
                                importScripts('https://biowasm.com/cdn/v3/aioli.js');
                                log("fallback importScripts used");
                            }}
                        }}
                    }}

                    if (typeof globalThis.Aioli !== 'function') {{
                         throw new Error("Aioli could not be loaded as a constructor.");
                    }}

                    // 2. 初期化
                    if (!globalThis._pyowasm_clis) globalThis._pyowasm_clis = {{}};
                    const toolName = "{tool}";
                    if (!globalThis._pyowasm_clis[toolName]) {{
                        log("creating new Aioli instance", toolName);
                        globalThis._pyowasm_clis[toolName] = await new Aioli([toolName]);
                    }}
                    const cli = globalThis._pyowasm_clis[toolName];
                    log("cli ready", !!cli);

                    // 3. マウント処理
                    let commandToExec = `{args}`;
                    const targetFile = "{target_file}";
                    const resolveMountedPath = (value) => {{
                        if (!value) return null;
                        if (typeof value === "string") return value;
                        if (Array.isArray(value)) {{
                            for (const item of value) {{
                                const resolved = resolveMountedPath(item);
                                if (resolved) return resolved;
                            }}
                            return null;
                        }}
                        if (typeof value === "object") {{
                            return value.path || value.mountPath || value.file || value.name || null;
                        }}
                        return null;
                    }};
                    
            if ({'true' if has_input_file else 'false'}) {{
                        let rawData = globalThis._pyowasm_upload_data;
                        if (!rawData) {{
                            const fallbackText = globalThis._pyowasm_upload_text;
                            if (typeof fallbackText === "string") {{
                                rawData = new TextEncoder().encode(fallbackText);
                                log("using text fallback", rawData.length);
                            }}
                        }}
                        if (!rawData) throw new Error("Upload data not found in JS global scope");
                        
                        // Proxyオブジェクト等の可能性を考慮してUint8Arrayに変換
                        const fileData = new Uint8Array(rawData);
                        console.log('[Pyowasm] Mounting file:', targetFile, 'Size:', fileData.length, 'bytes');
                        
                        const blob = new Blob([fileData]);
                        const mountedPaths = await cli.mount([{{
                            name: targetFile,
                            data: blob
                        }}]);

                        log("mountedPaths", mountedPaths);

                        const mountedPath = resolveMountedPath(mountedPaths);
                        if (!mountedPath) {{
                            throw new Error("Aioli mount failed: could not resolve mounted path");
                        }}

                        // 入力ファイル名の全出現箇所をマウント先へ置換
                        commandToExec = commandToExec.split(targetFile).join(mountedPath);
                        log("finalCommand", commandToExec);
                        
                        // メモリ解放
                        delete globalThis._pyowasm_upload_data;
                    }}

                    log("executing", commandToExec);
                    const result = await cli.exec(commandToExec);
                    log("exec completed");
                    return JSON.stringify({{ status: "success", data: result, debug: debugLogs }});

                }} catch (e) {{
                    log("bridgeError", e?.message || String(e));
                    return JSON.stringify({{ status: "error", message: e.message || String(e), debug: debugLogs }});
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
