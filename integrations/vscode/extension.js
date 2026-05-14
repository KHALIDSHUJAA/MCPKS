const vscode = require("vscode");
const childProcess = require("child_process");

function serverUrl() {
  return vscode.workspace.getConfiguration().get("aiMemory.serverUrl") || "http://127.0.0.1:8765";
}

function autoStartEnabled() {
  return vscode.workspace.getConfiguration().get("aiMemory.autoStart") !== false;
}

function startScript() {
  return vscode.workspace.getConfiguration().get("aiMemory.startScript");
}

function rootPath() {
  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  return folder ? folder.uri.fsPath : process.cwd();
}

async function health() {
  try {
    const response = await fetch(`${serverUrl()}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

async function ensureServer() {
  if (await health()) return true;
  if (!autoStartEnabled()) return false;
  const script = startScript();
  if (!script) return false;
  childProcess.spawn(
    "powershell.exe",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
    {
      detached: true,
      stdio: "ignore",
      windowsHide: true
    }
  ).unref();
  for (let attempt = 0; attempt < 8; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 750));
    if (await health()) return true;
  }
  return false;
}

async function post(path, body) {
  await ensureServer();
  const response = await fetch(`${serverUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json();
}

async function retrieveForDocument(document) {
  if (!document || document.isUntitled || document.uri.scheme !== "file") return;
  const query = `${document.fileName}\n${document.getText().slice(0, 4000)}`;
  const result = await post("/retrieve", {
    root: rootPath(),
    query,
    open_files: [document.fileName],
    top_k: 6
  });
  const lines = [`Project: ${result.project_name}`, ""];
  for (const chunk of result.chunks || []) {
    lines.push(`--- ${chunk.layer}: ${chunk.file_path || "memory"} ---`);
    lines.push(chunk.text.slice(0, 1200));
    lines.push("");
  }
  const channel = vscode.window.createOutputChannel("AI Memory");
  channel.clear();
  channel.appendLine(lines.join("\n"));
  channel.show(true);
}

function activate(context) {
  ensureServer().catch(console.error);
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((document) => retrieveForDocument(document).catch(console.error)),
    vscode.workspace.onDidSaveTextDocument((document) => {
      post("/store", {
        root: rootPath(),
        scan_files: true,
        tool: "vscode",
        event: `Saved ${document.fileName}`,
        async_store: true
      }).catch(console.error);
    }),
    vscode.commands.registerCommand("aiMemory.retrieve", () => retrieveForDocument(vscode.window.activeTextEditor?.document))
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
