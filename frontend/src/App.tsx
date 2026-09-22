import { useState } from "react";
import type { AssessmentResponse } from "./types";
import { Questionnaire } from "./components/Questionnaire";
import { Results } from "./components/Results";

function App() {
  const [result, setResult] = useState<AssessmentResponse | null>(null);

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: "2rem 1rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>AI 理財顧問 — 投資人風險輪廓</h1>
      {result ? (
        <>
          <Results result={result} />
          <div style={{ marginTop: 24 }}>
            <button
              type="button"
              onClick={() => setResult(null)}
              style={{
                padding: "0.6rem 1.4rem",
                fontSize: "1rem",
                borderRadius: 6,
                border: "1px solid #333",
                background: "#fff",
                cursor: "pointer",
              }}
            >
              重新填寫問卷
            </button>
          </div>
        </>
      ) : (
        <Questionnaire onComplete={setResult} />
      )}
    </main>
  );
}

export default App;
