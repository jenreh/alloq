/* Base64 to bytes. The viewers get their file as a base64 prop over the
 * state socket, so no route serves source files. */

import { useMemo } from "react";

/* atob yields one character per byte. A TextEncoder would re-encode as UTF-8
 * and corrupt every byte above 0x7f. */
export function decodeBase64(encoded) {
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/* Keyed on the payload: Reflex re-renders on every state delta and decoding
 * megabytes each time is the only expensive step here. */
export function useDecoded(encoded) {
  return useMemo(() => (encoded ? decodeBase64(encoded) : null), [encoded]);
}

/* Some renderers want an ArrayBuffer rather than a view of one. */
export function useBuffer(encoded) {
  const bytes = useDecoded(encoded);
  return useMemo(() => (bytes ? bytes.buffer : null), [bytes]);
}
