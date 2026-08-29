
$content = Get-Content -Raw src/lib/api.ts
$replacement = @"
const getSessionId = () => {
  let sessionId = localStorage.getItem("demo_session_id");
  if (!sessionId) {
    sessionId = "demo-" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem("demo_session_id", sessionId);
  }
  return sessionId;
};

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`\${API_URL}\${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Demo-Session-ID": getSessionId(),
      ...(options?.headers || {})
    }
  });
"@
$content = $content -replace "(?s)async function fetchApi<T>\(endpoint: string, options\?: RequestInit\): Promise<T> \{\n  const response = await fetch\(`\$\{API_URL\}\$\{endpoint\}`, \{\n    \.\.\.options,\n    headers: \{\n      `"Content-Type`": `"application/json`",\n      \.\.\.\(options\?\.headers \|\| \{\}\),\n    \},\n  \}\);", $replacement
Set-Content -Path src/lib/api.ts -Value $content

