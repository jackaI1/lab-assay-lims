import { DEFAULT_RECEIVER, type Result } from "./protocol.js";
import { sendDocuments } from "./transfer.js";
chrome.runtime.onMessage.addListener(
  (message: unknown, sender, respond: (result: Result) => void) => {
    if (sender.id !== chrome.runtime.id || !sender.tab || !sender.url) {
      respond({
        ok: false,
        retryable: false,
        error: "Messages must come from the OpenEMR document screen.",
      });
      return false;
    }
    void (async () => {
      try {
        const { receiver = DEFAULT_RECEIVER } =
          await chrome.storage.local.get("receiver");
        respond(await sendDocuments(message, sender.url!, receiver));
      } catch {
        respond({
          ok: false,
          retryable: false,
          error:
            "Could not read settings. Open extension options and save the receiver address.",
        });
      }
    })();
    return true; // Keep Chrome's reply channel open while the asynchronous transfer runs.
  },
);
