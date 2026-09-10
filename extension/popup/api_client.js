/**
 * Social Guard: Robust API Client for Chrome Extension
 * Handles timeouts, network retries, and clean error messages.
 */

const API_BASE_URL = "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 15000;

export class SocialGuardApiClient {
  /**
   * Health check to confirm backend connectivity.
   */
  static async checkHealth() {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (err) {
      clearTimeout(timeoutId);
      console.warn("[Social Guard] Backend offline or unreachable:", err.message);
      return { status: "offline", error: err.message };
    }
  }

  /**
   * Dispatch social media post payload to /analyze endpoint with timeout and 1 safe retry.
   * @param {Object} postPayload Standard AnalysisRequest JSON structure
   * @param {number} retryCount Internal retry counter
   */
  static async analyzePost(postPayload, retryCount = 0) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify(postPayload),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const message = errData.message || `Server returned error (HTTP ${response.status})`;
        throw new Error(message);
      }

      return await response.json();
    } catch (err) {
      clearTimeout(timeoutId);

      // Retry once on transient connection failure or abort
      if (retryCount < 1 && (err.name === "AbortError" || err.message.includes("Failed to fetch"))) {
        console.warn("[Social Guard] Retrying /analyze request once...");
        return await this.analyzePost(postPayload, retryCount + 1);
      }

      if (err.name === "AbortError") {
        throw new Error("Request timed out (15s). The backend took too long to respond.");
      }

      console.error("[Social Guard] /analyze failed:", err);
      throw err;
    }
  }
}
