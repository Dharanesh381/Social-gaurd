/**
 * Social Guard: Robust API Client for Chrome Extension (Phase 3)
 * Handles timeouts, network offline state, HTTP 400/422/500, malformed responses,
 * and transient network retries.
 */

const API_BASE_URL = "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 30000;

export class SocialGuardApiError extends Error {
  constructor(message, status = null, errorType = "UnknownError", details = null) {
    super(message);
    this.name = "SocialGuardApiError";
    this.status = status;
    this.errorType = errorType;
    this.details = details;
  }
}

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

      if (!response.ok) {
        return { status: "offline", error: `HTTP ${response.status}` };
      }
      return await response.json();
    } catch (err) {
      clearTimeout(timeoutId);
      console.warn("[Social Guard] Backend offline or unreachable:", err.message);
      return { status: "offline", error: err.message };
    }
  }

  /**
   * Dispatch social media post payload to /analyze endpoint with timeout, strict status handling,
   * and 1 safe retry for transient network dropouts.
   * @param {Object} postPayload Standard AnalysisRequest JSON structure
   * @param {number} retryCount Internal retry counter
   */
  static async analyzePost(postPayload, retryCount = 0) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    let response;
    try {
      response = await fetch(`${API_BASE_URL}/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify(postPayload),
        signal: controller.signal
      });
    } catch (netErr) {
      clearTimeout(timeoutId);

      // Handle abort / timeout
      if (netErr.name === "AbortError") {
        throw new SocialGuardApiError(
          "Request timed out (30s). The backend took too long to complete verification.",
          408,
          "TimeoutError"
        );
      }

      // Safe retry for transient connection glitches
      if (retryCount < 1 && (netErr.message.includes("Failed to fetch") || netErr.message.includes("NetworkError"))) {
        console.warn("[Social Guard] Transient fetch error, retrying /analyze once...");
        return await this.analyzePost(postPayload, retryCount + 1);
      }

      // Backend offline / unreachable
      throw new SocialGuardApiError(
        "Backend offline. Could not connect to FastAPI server at http://localhost:8000. Please ensure the backend is started.",
        null,
        "OfflineError"
      );
    }

    clearTimeout(timeoutId);

    // Parse response body safely
    let responseText = "";
    try {
      responseText = await response.text();
    } catch (readErr) {
      throw new SocialGuardApiError(
        "Failed to read response stream from backend.",
        response.status,
        "StreamError"
      );
    }

    let parsedBody = null;
    if (responseText && responseText.trim().length > 0) {
      try {
        parsedBody = JSON.parse(responseText);
      } catch (jsonErr) {
        // If HTTP status is 200 but body is not valid JSON
        if (response.ok) {
          throw new SocialGuardApiError(
            "Malformed backend response: Received invalid non-JSON payload from server.",
            response.status,
            "MalformedResponseError"
          );
        }
      }
    }

    // Handle HTTP status errors
    if (!response.ok) {
      const status = response.status;

      if (status === 400) {
        const msg = parsedBody?.message || parsedBody?.detail || "Invalid verification request format.";
        throw new SocialGuardApiError(`Bad Request (400): ${msg}`, status, "BadRequestError", parsedBody?.details);
      }

      if (status === 422) {
        // FastAPI / Pydantic validation error format
        let detailMsg = "The incoming payload failed schema validation.";
        const rawDetails = parsedBody?.details || parsedBody?.detail;

        if (Array.isArray(rawDetails)) {
          detailMsg = rawDetails.map(d => {
            const loc = Array.isArray(d.loc) ? d.loc.filter(l => l !== "body").join(".") : "field";
            return `${loc}: ${d.msg || "invalid value"}`;
          }).join("; ");
        } else if (parsedBody?.message) {
          detailMsg = parsedBody.message;
        }

        throw new SocialGuardApiError(
          `Payload validation error (422): ${detailMsg}`,
          status,
          "ValidationError",
          rawDetails
        );
      }

      if (status === 500) {
        const msg = parsedBody?.message || "Internal server error occurred in analysis pipeline.";
        throw new SocialGuardApiError(
          `Internal Server Error (500): ${msg}`,
          status,
          "InternalServerError",
          parsedBody?.details
        );
      }

      // Generic other HTTP errors
      const fallbackMsg = parsedBody?.message || parsedBody?.detail || `HTTP ${status}`;
      throw new SocialGuardApiError(
        `Server returned error (${fallbackMsg})`,
        status,
        "HttpError",
        parsedBody
      );
    }

    // Success response validation
    if (!parsedBody || typeof parsedBody !== "object") {
      throw new SocialGuardApiError(
        "Malformed backend response: Expected JSON object but received empty or null response.",
        response.status,
        "MalformedResponseError"
      );
    }

    return parsedBody;
  }
}
